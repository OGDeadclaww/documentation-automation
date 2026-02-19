# doc_generator.py
import re
import os
import json
import glob
import datetime
from jinja2 import Environment, FileSystemLoader

# Importy z Twoich modułów
from vendors import get_vendor_by_key
from csv_parser import (
    get_positions_with_systems,
    get_data_for_position,
)
from config import (
    PROJECTS_IMAGES,
    CATALOGS_PATH,
    ZLECENIA_LOCAL,
    JOB_PATH_LOCAL,
    DOCUMENTATION_PROJECTS_PATH,
    RELATIVE_DEPTH_TO_BASE,
)
from gui import select_file, select_folder, select_vendor
from db_builder import build_product_db


# ==========================================
# KONFIGURACJA ŚCIEŻEK
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mapowanie vendor_key → nazwa folderu w Katalogi/ (PascalCase)
VENDOR_CATALOG_FOLDERS = {
    "reynaers": "Reynaers",
    "aluprof": "Aluprof",
    "yawal": "Yawal",
    "aliplast": "Aliplast",
}

# Typy dokumentów — etykieta, metoda detekcji
# (prefix nazwy dla PDF, rozszerzenie dla reszty)
DOC_PATTERNS = {
    "LP": {"label": "Lista produkcyjna", "type": "prefix", "ext": ".pdf"},
    "LC": {"label": "Lista cięcia", "type": "prefix", "ext": ".pdf"},
    "Rys": {"label": "Rysunek", "type": "prefix", "ext": ".pdf"},
    "RK": {"label": "Rysunek konstrukcyjny", "type": "prefix", "ext": ".pdf"},
}
DOC_EXTENSIONS = {
    ".dwg": "Rysunek .DWG",
    ".met": "Plik .MET",
    ".rey": "Plik .REY",
    ".ali": "Plik .ALI",
}
# Rozszerzenia ignorowane dla plików LP/LC (żeby nie łapać .html/.csv gdy chcemy tylko .pdf)
PDF_ONLY_PREFIXES = {"LP", "LC", "Rys", "RK"}


# ==========================================
# HELPERS — ŚCIEŻKI
# ==========================================


def _url_encode(path_str: str) -> str:
    """Zamienia spacje na %20 w ścieżce."""
    return path_str.replace(" ", "%20")


def _file_date(filepath: str) -> str:
    """Zwraca datę modyfikacji pliku w formacie DD.MM.YYYY."""
    try:
        ts = os.path.getmtime(filepath)
        return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
    except Exception:
        return datetime.datetime.now().strftime("%d.%m.%Y")


def _local_to_relative(
    local_path: str,
    md_output_dir: str,
) -> str:
    """
    Zamienia bezwzględną ścieżkę lokalną na relatywną względem folderu MD.

    Przykład:
      local_path   = C:/Users/pawel/Desktop/Zlecenia/Lukasz/Belgia/P220667/LP.pdf
      md_output_dir = Z:/Pawel_Pisarski/Dokumentacja/projects/2025-xx_Projekt/

      Logika: wycinamy wspólny suffix "Zlecenia/Lukasz/Belgia/P220667/LP.pdf"
              i budujemy RELATIVE_DEPTH_TO_BASE + /Zlecenia/...
    """
    # Normalizuj separatory
    local_norm = local_path.replace("\\", "/")

    # Wycinamy dysk i prefix lokalny do "Zlecenia"
    # ZLECENIA_LOCAL = C:/Users/pawel/Desktop/Zlecenia
    zlecenia_local_norm = ZLECENIA_LOCAL.replace("\\", "/")

    if local_norm.lower().startswith(zlecenia_local_norm.lower()):
        # suffix = Lukasz_Kukulka/Belgia/P220667/LP.pdf
        suffix = local_norm[len(zlecenia_local_norm) :].lstrip("/")
        rel = f"{RELATIVE_DEPTH_TO_BASE}/Zlecenia/{suffix}"
        return _url_encode(rel)

    # Fallback: zwróć bezwzględną ścieżkę lokalną z URL encoding
    return _url_encode(local_norm)


def _local_to_network_relative(
    local_path: str,
) -> str:
    """
    Zamienia ścieżkę lokalną (C:/Users/pawel/Desktop/Zlecenia/...)
    na sieciową relatywną (../../../Zlecenia/...).

    Logika identyczna jak _local_to_relative ale używa głębokości
    wynikającej z miejsca pliku MD.
    """
    return _local_to_relative(local_path, "")


def _build_job_links() -> tuple[str, str]:
    """
    Zwraca tuple (link_lokalny, link_sieciowy) dla folderu JOB.
    Oba kończą się na nazwie folderu Lotti/ (bez konkretnego pliku).
    """
    local_norm = JOB_PATH_LOCAL.replace("\\", "/")
    # network_norm = JOB_PATH_NETWORK.replace("\\", "/")

    # Sieciowy relatywny: JOB jest w Z:\ więc
    # Z:\Pawel_Pisarski\Dokumentacja\projects\FOLDER\Dokumentacja.md
    # ../../.. = Pawel_Pisarski, ale JOB jest w Z:\ nie w Pawel_Pisarski
    # więc ../../../../JOB/Lotti/
    job_network_rel = "../../../../JOB/Lotti/"

    local_link = _url_encode(f"{local_norm}/")
    network_link = _url_encode(job_network_rel)

    return local_link, network_link


# ==========================================
# HELPERS — SKANOWANIE DOKUMENTÓW
# ==========================================


def _scan_project_documents(doc_folder: str) -> list[dict]:
    """
    Skanuje folder projektu w poszukiwaniu dokumentów:
      - PDF z prefixem: LP, LC, Rys, RK
      - Pliki: .dwg, .met, .rey, .ali

    Zwraca listę słowników gotowych dla kontekstu Jinja2.
    Nie zwraca plików JOB — te są generowane osobno.
    """
    if not doc_folder or not os.path.isdir(doc_folder):
        return []

    found = []
    seen_labels = set()  # zapobiega duplikatom tego samego typu

    try:
        entries = os.listdir(doc_folder)
    except PermissionError:
        print(f"⚠️ Brak dostępu do folderu: {doc_folder}")
        return []

    for filename in sorted(entries):
        filepath = os.path.join(doc_folder, filename)

        if not os.path.isfile(filepath):
            continue

        name_lower = filename.lower()
        ext = os.path.splitext(filename)[1].lower()
        name_no_ext = os.path.splitext(filename)[0]

        label = None
        matched = False

        # --- Sprawdź rozszerzenia binarne (.dwg, .met, .rey, .ali) ---
        if ext in DOC_EXTENSIONS:
            label = DOC_EXTENSIONS[ext]
            matched = True

        # --- Sprawdź prefixy PDF ---
        elif ext == ".pdf":
            for prefix, meta in DOC_PATTERNS.items():
                # Akceptujemy: LP_, LP-, LP (spacja), Lista produkcyjna, Lista cięcia
                if name_no_ext.upper().startswith(
                    prefix.upper()
                ) or name_lower.startswith(
                    meta["label"].lower().split()[0]  # "lista", "rysunek"
                ):
                    label = meta["label"]
                    matched = True
                    break

        if not matched:
            continue

        # Unikamy duplikatów (np. dwa pliki LP_)
        label_key = label
        if label_key in seen_labels:
            # Dodaj numer jeśli duplikat
            count = sum(1 for s in seen_labels if s.startswith(label_key))
            label = f"{label} ({count + 1})"
        seen_labels.add(label_key)

        date_str = _file_date(filepath)
        rel_link = _local_to_relative(filepath, "")

        found.append(
            {
                "name": label,
                "date": date_str,
                "path": rel_link,
                "local": True,
            }
        )

    return found


def _select_designer_and_find_project(project_number: str) -> str | None:
    """
    Flow:
      1. Odczytuje podfoldery ZLECENIA_LOCAL → lista projektantów
      2. Użytkownik wybiera projektanta z okna dialogowego (select_folder w folderze Zlecenia)
      3. W folderze projektanta szuka podfolderu pasującego do numeru projektu
      4. Jeśli znajdzie → zwraca pełną ścieżkę
      5. Jeśli nie → manual select_folder
    """
    import tkinter as tk
    from tkinter import simpledialog

    # Odczytaj projektantów
    try:
        designers = [
            d
            for d in os.listdir(ZLECENIA_LOCAL)
            if os.path.isdir(os.path.join(ZLECENIA_LOCAL, d))
        ]
    except Exception as e:
        print(f"⚠️ Nie można odczytać {ZLECENIA_LOCAL}: {e}")
        return select_folder("Wybierz folder z dokumentacją projektu")

    if not designers:
        return select_folder("Wybierz folder z dokumentacją projektu")

    # Okno wyboru projektanta
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    designer = simpledialog.askstring(
        "Wybierz projektanta",
        f"Projektanci ({ZLECENIA_LOCAL}):\n\n"
        + "\n".join(f"  {i+1}. {d}" for i, d in enumerate(designers))
        + "\n\nWpisz nazwę projektanta (lub zostaw puste = wybierz manualnie):",
        parent=root,
    )
    root.destroy()

    if not designer:
        return select_folder("Wybierz folder z dokumentacją projektu")

    # Znajdź pasujący folder projektanta (case-insensitive)
    designer_match = next(
        (d for d in designers if d.lower() == designer.strip().lower()),
        None,
    )
    if not designer_match:
        # Spróbuj częściowe dopasowanie
        designer_match = next(
            (d for d in designers if designer.strip().lower() in d.lower()),
            None,
        )

    if not designer_match:
        print(f"⚠️ Nie znaleziono projektanta: {designer}")
        return select_folder("Wybierz folder z dokumentacją projektu")

    designer_path = os.path.join(ZLECENIA_LOCAL, designer_match)
    print(f"📁 Projektant: {designer_match}")

    # Szukaj folderu projektu rekurencyjnie (max 2 poziomy)
    candidates = _find_project_folder(designer_path, project_number, max_depth=2)

    if len(candidates) == 1:
        print(f"✅ Znaleziono folder dokumentacji: {candidates[0]}")
        return candidates[0]

    elif len(candidates) > 1:
        # Kilka pasujących — zapytaj
        root2 = tk.Tk()
        root2.withdraw()
        root2.attributes("-topmost", True)

        choice = simpledialog.askstring(
            "Wybierz folder projektu",
            f"Znaleziono kilka folderów dla {project_number}:\n\n"
            + "\n".join(f"  {i+1}. {c}" for i, c in enumerate(candidates))
            + "\n\nWpisz numer:",
            parent=root2,
        )
        root2.destroy()

        try:
            idx = int(choice.strip()) - 1
            return candidates[idx]
        except Exception:
            return select_folder("Wybierz folder z dokumentacją projektu")

    else:
        print(f"⚠️ Nie znaleziono folderu dla {project_number} w {designer_path}")
        return select_folder("Wybierz folder z dokumentacją projektu")


def _find_project_folder(
    base_path: str, project_number: str, max_depth: int = 2
) -> list[str]:
    """
    Rekurencyjnie szuka folderu zawierającego numer projektu w nazwie.
    Zwraca listę pasujących ścieżek.
    """
    candidates = []
    pn_lower = project_number.lower()

    def _walk(path, depth):
        if depth > max_depth:
            return
        try:
            for entry in os.scandir(path):
                if entry.is_dir(follow_symlinks=False):
                    if pn_lower in entry.name.lower():
                        candidates.append(entry.path)
                    else:
                        _walk(entry.path, depth + 1)
        except PermissionError:
            pass

    _walk(base_path, 0)
    return candidates


# ==========================================
# HELPERS — KATALOGI SYSTEMOWE
# ==========================================


def _find_system_catalog(vendor_key: str, sys_name: str) -> dict | None:
    """
    Szuka katalogu systemowego PDF dla danego dostawcy i systemu.

    Konwencja nazwy pliku:
      {sys_name_lower}_{DD.MM.YYYY}.pdf
      Przykład: mb-77hs_23.01.2026.pdf

    Jeśli jest kilka wersji → bierze najnowszy wg daty w nazwie,
    fallback: data modyfikacji pliku.

    Zwraca słownik:
      {"name": str, "path": str, "date": str, "status_icon": str, "status_text": str}
    lub None jeśli nie znaleziono.
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return None

    catalog_dir = os.path.join(CATALOGS_PATH, vendor_folder)
    if not os.path.isdir(catalog_dir):
        print(f"⚠️ Brak folderu katalogów: {catalog_dir}")
        return None

    sys_lower = sys_name.lower()

    # Szukaj plików pasujących do systemu
    pattern = os.path.join(catalog_dir, f"{sys_lower}*.pdf")
    matches = glob.glob(pattern, recursive=False)

    # Jeśli brak wyników — spróbuj bez separatora (tolerancja nazw)
    if not matches:
        all_pdfs = glob.glob(os.path.join(catalog_dir, "*.pdf"))
        matches = [p for p in all_pdfs if sys_lower in os.path.basename(p).lower()]

    if not matches:
        print(f"⚠️ Brak katalogu dla systemu '{sys_name}' w {catalog_dir}")
        return None

    # Wybierz najnowszy (po dacie w nazwie lub modyfikacji)
    def _extract_date(filepath):
        name = os.path.basename(filepath)
        # Szukaj wzorca DD.MM.YYYY w nazwie
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", name)
        if m:
            try:
                return datetime.datetime(
                    int(m.group(3)), int(m.group(2)), int(m.group(1))
                )
            except ValueError:
                pass
        return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

    best = max(matches, key=_extract_date)
    date_obj = _extract_date(best)
    date_str = date_obj.strftime("%d.%m.%Y")

    # Relatywna ścieżka do katalogu
    # MD jest w: Z:\Pawel_Pisarski\Dokumentacja\projects\FOLDER\Dokumentacja.md
    # Katalogi są w: Z:\Pawel_Pisarski\Katalogi\...
    # ../../../Katalogi/Reynaers/mb-77hs_23.01.2026.pdf
    best_norm = best.replace("\\", "/")
    catalogs_norm = CATALOGS_PATH.replace("\\", "/")

    if best_norm.lower().startswith(catalogs_norm.lower()):
        suffix = best_norm[len(catalogs_norm) :].lstrip("/")
        rel_path = _url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}")
    else:
        rel_path = _url_encode(best_norm)

    return {
        "name": sys_name.upper(),
        "date": date_str,
        "path": rel_path,
        "status_icon": "🟡",
        "status_text": "Do weryfikacji",
    }


def _find_hardware_catalog_page(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> str:
    """
    Szuka strony katalogowej (PDF) dla konkretnego okucia.

    Struktura:
      Katalogi/{Vendor}/{SYS_NAME_UPPER}/{hw_code}*.pdf

    Dopasowanie po kodzie (case-insensitive, ignoruje opis po _).
    Zwraca relatywną ścieżkę MD lub '#' jeśli nie znaleziono.
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return "#"

    # Podfolder systemu — UPPERCASE zgodnie z konwencją
    sys_folder = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder)

    if not os.path.isdir(hw_dir):
        return "#"

    # Normalizuj kod: zamień spacje na _ dla porównania
    code_normalized = hw_code.replace(" ", "_").replace(".", ".").lower()

    # Szukaj pliku zaczynającego się od kodu
    try:
        candidates = [
            f
            for f in os.listdir(hw_dir)
            if os.path.isfile(os.path.join(hw_dir, f))
            and os.path.splitext(f)[1].lower() == ".pdf"
            and f.lower().startswith(code_normalized)
        ]
    except PermissionError:
        return "#"

    if not candidates:
        # Spróbuj bez normalizacji (tolerancja)
        code_alt = hw_code.replace(" ", "").lower()
        try:
            candidates = [
                f
                for f in os.listdir(hw_dir)
                if os.path.isfile(os.path.join(hw_dir, f))
                and os.path.splitext(f)[1].lower() == ".pdf"
                and f.lower()
                .replace("_", "")
                .replace(".", "")
                .startswith(code_alt.replace("_", "").replace(".", ""))
            ]
        except PermissionError:
            return "#"

    if not candidates:
        return "#"

    # Bierz pierwszy pasujący
    filename = candidates[0]
    rel_path = (
        f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/" f"{vendor_folder}/{sys_folder}/{filename}"
    )
    return _url_encode(rel_path)


# ==========================================
# RENDER
# ==========================================


def _strip_date_from_folder_name(folder_name: str) -> str:
    """
    Usuwa datę z początku nazwy folderu projektu.
    Input:  "2025-18-12_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    Output: "Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    """
    cleaned = re.sub(r"^\d{4}[-.]\d{2}[-.]\d{2}[_ ]?", "", folder_name).strip()
    return cleaned


def render_markdown(context, output_filename=None):
    """Renderuje szablon Jinja2 do pliku MD w folderze projektu."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    try:
        template = env.get_template("project_doc.md.j2")
    except Exception as e:
        print(f"❌ Błąd ładowania szablonu: {e}")
        return

    rendered = template.render(context)

    if output_filename is None:
        proj_folder = context.get("project_folder_name", "Dokumentacja")
        clean_name = _strip_date_from_folder_name(proj_folder)
        output_filename = f"{clean_name}.md"

    proj_folder_name = context.get("project_folder_name", "projekt")
    out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, proj_folder_name)
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, output_filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✅ Wygenerowano dokumentację: {os.path.abspath(out_path)}")
    print(f"📄 Nazwa pliku: {output_filename}")
    _update_project_index(context)


# ==========================================
# MODUŁY POMOCNICZE (Data Providers)
# ==========================================


def _get_view_for_position(project_name, pos_num):
    """
    Szuka pliku graficznego rzutu dla danej pozycji.
    Zwraca ścieżkę relatywną dla Markdowna.
    """
    views_dir = os.path.join(PROJECTS_IMAGES, project_name, "views")
    pattern = os.path.join(views_dir, f"*Poz_{pos_num}.jpg")
    found_files = glob.glob(pattern)

    if found_files:
        full_path = found_files[0]
        filename = os.path.basename(full_path)
        safe_project_name = project_name.replace(" ", "%20")
        return f"{RELATIVE_DEPTH_TO_BASE}/projects_images/{safe_project_name}/views/{filename}"

    return f"{RELATIVE_DEPTH_TO_BASE}/logo.png"


def _parse_project_name(folder_name):
    """
    Rozbija nazwę folderu na części (Klient, Numer, Opis).
    Input: "2025-18-12_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    """
    name_clean = re.sub(r"^\d{4}[-.]\d{2}[-.]\d{2}[_ ]?", "", folder_name).strip()
    match = re.search(r"\b(P\d{5,6})\b", name_clean)

    if match:
        number = match.group(1)
        parts = name_clean.split(number)
        client = parts[0].strip(" _-")
        desc = parts[1].strip(" _-") if len(parts) > 1 else ""
        return {"client": client, "number": number, "desc": desc}
    else:
        return {"client": name_clean, "number": "", "desc": ""}


def _get_profiles_for_position(
    csv_path, pos_num, vendor_key, vendor_cls, sys_name, product_db
):
    raw_data = get_data_for_position(csv_path, pos_num, vendor_cls, product_db)
    grouped = {}

    for prof in raw_data["profiles"]:
        raw_code = prof["code"]
        normalized_code = vendor_cls.parse_profile_code(raw_code)
        display_code = normalized_code if normalized_code else raw_code

        if display_code not in grouped:
            sys_folder = sys_name.upper()
            img_filename = f"{display_code}.jpg"
            img_path = (
                f"{RELATIVE_DEPTH_TO_BASE}/images_db"
                f"/{vendor_key}/profiles/{sys_folder}/{img_filename}"
            )

            grouped[display_code] = {
                "code": display_code,
                "desc": prof["desc"],
                "image_path": img_path.replace(" ", "%20"),
                "quantities": [],
                "dimensions": [],
                "locations": [],
            }
        else:
            if not grouped[display_code]["desc"] and prof["desc"]:
                grouped[display_code]["desc"] = prof["desc"]

        if prof["quantity"]:
            grouped[display_code]["quantities"].append(prof["quantity"])
        if prof["dimensions"]:
            grouped[display_code]["dimensions"].append(prof["dimensions"])
        if prof["location"] and prof["location"] != "—":
            grouped[display_code]["locations"].append(prof["location"])

    processed_profiles = []
    for code, data in grouped.items():
        unique_locs = list(dict.fromkeys(data["locations"]))
        processed_profiles.append(
            {
                "code": code,
                "desc": data["desc"],
                "image_path": data["image_path"],
                "quantity": "<br>".join(data["quantities"]),
                "dimensions": "<br>".join(data["dimensions"]),
                "location": "<br>".join(unique_locs) if unique_locs else "—",
            }
        )

    return processed_profiles


# ==========================================
# GŁÓWNA LOGIKA (Controller)
# ==========================================


def prepare_context(
    csv_file: str,
    zm_file: str,
    project_folder_name: str,
    vendor_key: str,
    doc_folder: str,
) -> dict:

    print(f"⚙️  Generowanie danych dla: {project_folder_name}...")

    vendor_cls = get_vendor_by_key(vendor_key)
    proj_info = _parse_project_name(project_folder_name)

    # Ścieżka wyjściowa PDF (Puppeteer)
    proj_out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, project_folder_name)
    pdf_filename = f"{project_folder_name}.pdf"
    pdf_output_path = os.path.join(proj_out_dir, pdf_filename).replace("\\", "/")

    product_db = build_product_db(zm_file)
    systems_map = get_positions_with_systems(csv_file)
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")

    # ------------------------------------------------------------------
    # DOKUMENTY — skanuj folder dokumentacji
    # ------------------------------------------------------------------
    documents = _build_documents_list(doc_folder, timestamp)

    # ------------------------------------------------------------------
    # KATALOGI SYSTEMOWE — znajdź dla każdego wykrytego systemu
    # ------------------------------------------------------------------
    catalogs = []
    for sys_name in systems_map.keys():
        cat = _find_system_catalog(vendor_key, sys_name)
        if cat:
            catalogs.append(cat)
        else:
            # Dodaj pusty placeholder
            catalogs.append(
                {
                    "name": sys_name.upper(),
                    "date": "—",
                    "path": "#",
                    "status_icon": "🔴",
                    "status_text": "Brak katalogu",
                }
            )

    # ------------------------------------------------------------------
    # KONTEKST BAZOWY
    # ------------------------------------------------------------------
    context = {
        "project_folder_name": project_folder_name,
        "project_client": proj_info["client"],
        "project_number": proj_info["number"],
        "project_desc": proj_info["desc"],
        "logo_path": f"{RELATIVE_DEPTH_TO_BASE}/logo.png",
        "pdf_output_path": pdf_output_path,
        "generation_date": timestamp,
        "author": os.getlogin(),
        "systems": list(systems_map.keys()),
        "systems_data": {},
        "global_hardware": [],
        "documents": documents,
        "catalogs": catalogs,
        "instructions": [],
    }

    all_hardware_map = {}

    # ------------------------------------------------------------------
    # PĘTLA PO SYSTEMACH
    # ------------------------------------------------------------------
    for sys_name, positions in systems_map.items():
        system_entries = []

        for pos_num in positions:
            view_path = _get_view_for_position(project_folder_name, pos_num)

            profiles = _get_profiles_for_position(
                csv_file, pos_num, vendor_key, vendor_cls, sys_name, product_db
            )

            pos_data = get_data_for_position(csv_file, pos_num, vendor_cls, product_db)
            hardware_list = []

            for hw in pos_data["hardware"]:
                raw_code = hw["code"]
                desc = hw["desc"]
                normalized_code = vendor_cls.parse_profile_code(raw_code)
                display_code = normalized_code if normalized_code else raw_code

                if display_code not in all_hardware_map:
                    all_hardware_map[display_code] = {
                        "desc": desc,
                        "sys_name": sys_name,
                    }

                safe_code = display_code.replace(" ", "%20")
                checklist_id = f"{display_code.replace(' ', '_')}_{pos_num}"

                # Szukaj strony katalogowej
                catalog_page = _find_hardware_catalog_page(
                    vendor_key, sys_name, display_code
                )

                hardware_list.append(
                    {
                        "code": display_code,
                        "desc": desc,
                        "quantity": hw["quantity"],
                        "image_path": (
                            f"{RELATIVE_DEPTH_TO_BASE}/images_db"
                            f"/{vendor_key}/hardware/{safe_code}.jpg"
                        ),
                        "catalog_link": catalog_page,
                        "checklist_id": checklist_id,
                    }
                )

            hardware_list.sort(key=lambda x: x["code"])
            notes_placeholder = f"__BALOON_NOTES_PLACEHOLDER__POZ_{pos_num}__"

            system_entries.append(
                {
                    "number": pos_num,
                    "view_image_path": view_path,
                    "profiles": profiles,
                    "hardware": hardware_list,
                    "construction_notes": notes_placeholder,
                }
            )

        context["systems_data"][sys_name] = system_entries

    # ------------------------------------------------------------------
    # GLOBALNA TABELA OKUĆ
    # ------------------------------------------------------------------
    for code, meta in sorted(all_hardware_map.items()):
        desc = meta["desc"]
        sys_name = meta["sys_name"]
        img_path = (
            f"{RELATIVE_DEPTH_TO_BASE}/images_db" f"/{vendor_key}/hardware/{code}.jpg"
        )
        catalog_page = _find_hardware_catalog_page(vendor_key, sys_name, code)

        context["global_hardware"].append(
            {
                "code": code,
                "desc": desc,
                "image_path": img_path.replace(" ", "%20"),
                "catalog_link": catalog_page,
                "status": "🟡 0/0",
                "notes": "",
            }
        )

    return context


def _build_documents_list(doc_folder: str, timestamp: str) -> list[dict]:
    """
    Buduje listę dokumentów z folderu projektu + wiersze JOB.
    """
    documents = []

    # Skanuj folder
    scanned = _scan_project_documents(doc_folder)
    documents.extend(scanned)

    # Wiersze JOB (placeholdery)
    local_link, network_link = _build_job_links()

    documents.append(
        {
            "name": "Plik JOB (dysk lokalny C:\\)",
            "date": timestamp,
            "path": local_link,
        }
    )
    documents.append(
        {
            "name": "Plik JOB (dysk sieciowy Z:\\)",
            "date": timestamp,
            "path": network_link,
        }
    )

    return documents


# ==========================================
# INDEKS PROJEKTÓW
# ==========================================


def _update_project_index(context):
    index_path = os.path.join(DOCUMENTATION_PROJECTS_PATH, "project_index.json")

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except json.JSONDecodeError:
            index = {}
    else:
        index = {}

    proj_num = context["project_number"] or "UNKNOWN"

    usage_by_system = {}
    all_hardware = set()
    all_profiles = set()

    for sys_name, positions in context["systems_data"].items():
        if sys_name not in usage_by_system:
            usage_by_system[sys_name] = {"profiles": set(), "hardware": set()}

        for pos in positions:
            for prof in pos["profiles"]:
                usage_by_system[sys_name]["profiles"].add(prof["code"])
                all_profiles.add(prof["code"])
            for hw in pos["hardware"]:
                usage_by_system[sys_name]["hardware"].add(hw["code"])
                all_hardware.add(hw["code"])

    usage_json = {
        sys: {
            "profiles": sorted(list(data["profiles"])),
            "hardware": sorted(list(data["hardware"])),
        }
        for sys, data in usage_by_system.items()
    }

    index[proj_num] = {
        "date": context["generation_date"],
        "client": context["project_client"],
        "desc": context["project_desc"],
        "folder": context["project_folder_name"],
        "systems": context["systems"],
        "stats": {
            "hardware_count": len(all_hardware),
            "profiles_count": len(all_profiles),
        },
        "usage_by_system": usage_json,
    }

    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"💾 Zaktualizowano indeks projektów: {index_path}")
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać indeksu: {e}")


# ==========================================
# MAIN — TRYB INTERAKTYWNY
# ==========================================

if __name__ == "__main__":
    print("🚀 Tryb Interaktywny Generatora Dokumentacji")

    # 1. Wybierz CSV (ilości)
    csv_path = select_file("CSV", "Wybierz plik LP_dane.csv (Ilości)")
    if not csv_path:
        print("❌ Anulowano wybór pliku CSV.")
        exit()

    # 2. Wybierz CSV (baza wiedzy ZM)
    zm_path = select_file("CSV", "Wybierz plik ZM_dane.csv (Baza Wiedzy)")
    if not zm_path:
        print("❌ Anulowano wybór pliku ZM.")
        exit()

    # 3. Wybierz folder projektu (zdjęcia rzutów)
    base_proj_dir = PROJECTS_IMAGES
    print(f"📂 Wybierz folder projektu (rzuty) w: {base_proj_dir}")
    project_dir = select_folder("Wybierz folder projektu (zrzuty)")
    if not project_dir:
        print("❌ Anulowano wybór projektu.")
        exit()

    project_name = os.path.basename(project_dir)
    print(f"✅ Wybrano projekt: {project_name}")

    # 4. Wybierz dostawcę
    vendor_profile = select_vendor()
    if not vendor_profile:
        print("❌ Anulowano wybór dostawcy.")
        exit()

    vendor_key = vendor_profile.KEY
    print(f"✅ Wybrano dostawcę: {vendor_key}")

    # 5. Znajdź folder dokumentacji (LP, LC, DWG, MET)
    proj_info = _parse_project_name(project_name)
    proj_number = proj_info.get("number", "")

    print(f"\n📂 Szukam folderu dokumentacji dla: {proj_number}")
    doc_folder = _select_designer_and_find_project(proj_number)

    if not doc_folder:
        print("⚠️ Nie wybrano folderu dokumentacji — sekcja Dokumentacja będzie pusta.")
        doc_folder = ""
    else:
        print(f"✅ Folder dokumentacji: {doc_folder}")

    # 6. Uruchom generator
    if os.path.exists(csv_path):
        ctx = prepare_context(csv_path, zm_path, project_name, vendor_key, doc_folder)
        render_markdown(ctx)
    else:
        print(f"❌ Plik nie istnieje: {csv_path}")
