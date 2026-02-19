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


def _local_to_relative(local_path: str, is_local: bool = True) -> str:
    """
    Zwraca ścieżkę w zależności od typu linku.

    Args:
        local_path: pełna ścieżka do pliku
        is_local: True = zwróć bezwzględną ścieżkę C:/, False = zwróć relatywną sieciową

    Returns:
        - Jeśli is_local=True:  C:/Users/pawel/Desktop/Zlecenia/...
        - Jeśli is_local=False: ../../../Zlecenia/... (relatywna od MD)
    """
    # Normalizuj separatory
    local_norm = local_path.replace("\\", "/")
    zlecenia_local_norm = ZLECENIA_LOCAL.replace("\\", "/")

    # --- LOKALNY: Zwróć bezwzględną ścieżkę C:/ ---
    if is_local:
        return _url_encode(local_norm)

    # --- SIECIOWY: Zwróć relatywną ścieżkę ../../../ ---
    if local_norm.lower().startswith(zlecenia_local_norm.lower()):
        # suffix = Lukasz_Kukulka/Belgia/P220667/LP.pdf
        suffix = local_norm[len(zlecenia_local_norm) :].lstrip("/")
        rel = f"{RELATIVE_DEPTH_TO_BASE}/Zlecenia/{suffix}"
        return _url_encode(rel)

    # Fallback: URL-encoded bezwzględna ścieżka lokalna
    return _url_encode(local_norm)


# ==========================================
# HELPERS — SKANOWANIE DOKUMENTÓW
# ==========================================


def _select_designer_and_find_project(project_number: str) -> str | None:
    """
    Flow:
      1. Odczytuje podfoldery ZLECENIA_LOCAL → lista projektantów
      2. Użytkownik wybiera projektanta z okna dialogowego (z scrollbarem)
      3. W folderze projektanta szuka podfolderu pasującego do numeru projektu
      4. Jeśli znajdzie → zwraca pełną ścieżkę
      5. Jeśli nie → manual select_folder
    """
    import tkinter as tk
    from tkinter import Listbox, Scrollbar, SINGLE

    # Odczytaj projektantów
    try:
        designers = sorted(
            [
                d
                for d in os.listdir(ZLECENIA_LOCAL)
                if os.path.isdir(os.path.join(ZLECENIA_LOCAL, d))
            ]
        )
    except Exception as e:
        print(f"⚠️ Nie można odczytać {ZLECENIA_LOCAL}: {e}")
        return select_folder("Wybierz folder z dokumentacją projektu")

    if not designers:
        return select_folder("Wybierz folder z dokumentacją projektu")

    # Okno z Listbox (scrollable + clickable)
    root = tk.Tk()
    root.title("Wybór projektanta")
    root.geometry("400x300")
    root.attributes("-topmost", True)

    label = tk.Label(
        root,
        text=f"Wybierz projektanta ({ZLECENIA_LOCAL}):",
        wraplength=380,
        justify=tk.LEFT,
    )
    label.pack(pady=10, padx=10)

    # Frame dla Listbox + Scrollbar
    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    scrollbar = Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(
        frame,
        yscrollcommand=scrollbar.set,
        height=10,
        width=50,
        selectmode=SINGLE,
        font=("Arial", 10),
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    # Dodaj projektantów do Listbox
    for designer in designers:
        listbox.insert(tk.END, designer)

    selected_designer = None

    def on_select():
        nonlocal selected_designer
        selection = listbox.curselection()
        if selection:
            selected_designer = designers[selection[0]]
            root.destroy()

    def on_cancel():
        root.destroy()

    # Przyciski
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    ok_btn = tk.Button(button_frame, text="OK", command=on_select, width=10)
    ok_btn.pack(side=tk.LEFT, padx=5)

    cancel_btn = tk.Button(button_frame, text="Anuluj", command=on_cancel, width=10)
    cancel_btn.pack(side=tk.LEFT, padx=5)

    root.mainloop()

    if not selected_designer:
        return select_folder("Wybierz folder z dokumentacją projektu")

    designer_path = os.path.join(ZLECENIA_LOCAL, selected_designer)
    print(f"📁 Projektant: {selected_designer}")

    # Szukaj folderu projektu rekurencyjnie (max 2 poziomy)
    candidates = _find_project_folder(designer_path, project_number, max_depth=2)

    if len(candidates) == 1:
        print(f"✅ Znaleziono folder dokumentacji: {candidates[0]}")
        return candidates[0]

    elif len(candidates) > 1:
        # Kilka pasujących — zapytaj z Listbox
        root2 = tk.Tk()
        root2.title("Wybór folderu projektu")
        root2.geometry("500x300")
        root2.attributes("-topmost", True)

        label2 = tk.Label(
            root2,
            text=f"Znaleziono kilka folderów dla {project_number}.\nWybierz właściwy:",
            wraplength=480,
            justify=tk.LEFT,
        )
        label2.pack(pady=10, padx=10)

        frame2 = tk.Frame(root2)
        frame2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar2 = Scrollbar(frame2)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

        listbox2 = Listbox(
            frame2,
            yscrollcommand=scrollbar2.set,
            height=10,
            width=60,
            selectmode=SINGLE,
            font=("Arial", 9),
        )
        listbox2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.config(command=listbox2.yview)

        for i, cand in enumerate(candidates):
            # Pokaż tylko basename dla czytelności
            display = os.path.basename(cand)
            listbox2.insert(tk.END, display)
            # Store full path jako tag
            listbox2.itemconfig(i, {"bg": "white"})

        selected_path = None

        def on_select2():
            nonlocal selected_path
            selection = listbox2.curselection()
            if selection:
                selected_path = candidates[selection[0]]
                root2.destroy()

        def on_cancel2():
            root2.destroy()

        button_frame2 = tk.Frame(root2)
        button_frame2.pack(pady=10)

        ok_btn2 = tk.Button(button_frame2, text="OK", command=on_select2, width=10)
        ok_btn2.pack(side=tk.LEFT, padx=5)

        cancel_btn2 = tk.Button(
            button_frame2, text="Anuluj", command=on_cancel2, width=10
        )
        cancel_btn2.pack(side=tk.LEFT, padx=5)

        root2.mainloop()

        if selected_path:
            return selected_path
        else:
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


def _get_catalog_status(date_obj: datetime.datetime) -> tuple[str, str]:
    """
    Zwraca (status_icon, status_text) na podstawie różnicy dat.

    - Do 3 miesięcy:   🟢 Aktualny
    - 3-6 miesięcy:    🟡 Do weryfikacji
    - Powyżej 6 mcy:   🔴 Nieaktualny
    """
    now = datetime.datetime.now()
    delta_days = (now - date_obj).days

    if delta_days <= 90:  # ~3 miesiące
        return "🟢", "Aktualny"
    elif delta_days <= 180:  # ~6 miesięcy
        return "🟡", "Do weryfikacji"
    else:
        return "🔴", "Nieaktualny"


def _find_system_catalog(vendor_key: str, sys_name: str) -> dict | None:
    """
    Szuka katalogu systemowego PDF dla danego dostawcy i systemu.
    Status zależy od świeżości (3msc/6msc).
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

    # Status zależy od świeżości
    status_icon, status_text = _get_catalog_status(date_obj)

    # Relatywna ścieżka do katalogu
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
        "status_icon": status_icon,
        "status_text": status_text,
    }


def _find_hardware_catalog_page(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> str:
    """
    Szuka strony katalogowej (PDF) dla konkretnego okucia.

    Struktura:
      Katalogi/{Vendor}/{SYS_NAME_UPPERCASE}/{hw_code}*.pdf

    Zwraca relatywną ścieżkę MD lub '#' jeśli nie znaleziono.
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        print(f"⚠️ Vendor '{vendor_key}' nie znaleziony w VENDOR_CATALOG_FOLDERS")
        return "#"

    sys_folder = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder)

    print(f"🔍 Szukam w: {hw_dir}")
    print(f"   Kod: {hw_code}")

    if not os.path.isdir(hw_dir):
        print(f"⚠️ Katalog nie istnieje: {hw_dir}")
        return "#"

    # Normalizuj kod: zamień spacje na _ dla porównania
    code_normalized = hw_code.replace(" ", "_").replace(".", "").lower()

    print(f"   Kod znormalizowany: {code_normalized}")

    # Szukaj pliku zaczynającego się od kodu
    try:
        all_files = os.listdir(hw_dir)
        print(f"   Pliki w folderze: {all_files[:5]}...")  # Pokaż pierwsze 5

        candidates = [
            f
            for f in all_files
            if os.path.isfile(os.path.join(hw_dir, f))
            and os.path.splitext(f)[1].lower() == ".pdf"
            and f.lower().replace("_", "").replace(".", "").startswith(code_normalized)
        ]

        print(f"   Znalezieni kandydaci: {candidates}")

    except PermissionError:
        print(f"⚠️ Brak dostępu do: {hw_dir}")
        return "#"

    if not candidates:
        print(f"❌ Brak pasującego pliku dla: {hw_code}")
        return "#"

    # Bierz pierwszy pasujący
    filename = candidates[0]
    print(f"✅ Wybrany plik: {filename}")

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
        return f"../../projects_images/{safe_project_name}/views/{filename}"

    return "../../logo.png"  # Placeholder jeśli brak rzutu


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
                f"../../images_db/{vendor_key}/profiles/{sys_folder}/{img_filename}"
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

    proj_out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, project_folder_name)
    pdf_filename = f"{project_folder_name}.pdf"
    pdf_output_path = os.path.join(proj_out_dir, pdf_filename).replace("\\", "/")

    product_db = build_product_db(zm_file)
    systems_map = get_positions_with_systems(csv_file)
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")

    # --- DOKUMENTY ---
    documents = _build_documents_list(doc_folder, project_folder_name, timestamp)

    # --- KATALOGI SYSTEMOWE ---
    catalogs = []
    for sys_name in systems_map.keys():
        cat = _find_system_catalog(vendor_key, sys_name)
        if cat:
            catalogs.append(cat)
        else:
            catalogs.append(
                {
                    "name": sys_name.upper(),
                    "date": "—",
                    "path": "#",
                    "status_icon": "⚪",
                    "status_text": "Brak katalogu",
                }
            )

    # --- KONTEKST BAZOWY ---
    context = {
        "project_folder_name": project_folder_name,
        "project_client": proj_info["client"],
        "project_number": proj_info["number"],
        "project_desc": proj_info["desc"],
        "logo_path": "../../logo.png",
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

    # --- PĘTLA PO SYSTEMACH I POZYCJACH ---
    for sys_name, positions in systems_map.items():
        system_entries = []

        for pos_num in positions:
            view_path = _get_view_for_position(project_folder_name, pos_num)

            # --- PROFILE ---
            profiles = _get_profiles_for_position(
                csv_file, pos_num, vendor_key, vendor_cls, sys_name, product_db
            )

            # --- HARDWARE (OBRÓBKI) ---
            pos_data = get_data_for_position(csv_file, pos_num, vendor_cls, product_db)
            hardware_list = []

            for hw in pos_data["hardware"]:
                raw_code = hw["code"]
                desc = hw["desc"]
                normalized_code = vendor_cls.parse_profile_code(raw_code)
                display_code = normalized_code if normalized_code else raw_code

                # Dodaj do globalnej mapy
                if display_code not in all_hardware_map:
                    all_hardware_map[display_code] = {
                        "desc": desc,
                        "sys_name": sys_name,
                    }

                safe_code = display_code.replace(" ", "%20")
                checklist_id = f"{display_code.replace(' ', '_')}_{pos_num}"

                # --- NOWA LOGIKA: Wylicz link + sprawdź istnienie pliku ---
                catalog_link, file_exists = _build_hardware_catalog_link(
                    vendor_key, sys_name, display_code
                )

                # Status: ikona + tekst
                status_icon = "✅" if file_exists else "🔴"
                status_text = "" if file_exists else "Brak w katalogu"

                hardware_list.append(
                    {
                        "code": display_code,
                        "desc": desc,
                        "quantity": hw["quantity"],
                        "image_path": f"../../images_db/{vendor_key}/hardware/{safe_code}.jpg",
                        "catalog_link": catalog_link,
                        "file_exists": file_exists,
                        "status_icon": status_icon,
                        "status_text": status_text,
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

    # --- GLOBALNA TABELA OKUĆ ---
    for code, meta in sorted(all_hardware_map.items()):
        desc = meta["desc"]
        sys_name = meta["sys_name"]
        img_path = f"../../images_db/{vendor_key}/hardware/{code}.jpg"

        # Wylicz link + sprawdź istnienie
        catalog_link, file_exists = _build_hardware_catalog_link(
            vendor_key, sys_name, code
        )

        status_icon = "✅" if file_exists else "🔴"
        status_text = "Katalog OK" if file_exists else "Brak w katalogu"

        context["global_hardware"].append(
            {
                "code": code,
                "desc": desc,
                "image_path": img_path.replace(" ", "%20"),
                "catalog_link": catalog_link,
                "file_exists": file_exists,
                "status": f"{status_icon} {status_text}",
                "notes": "",
            }
        )

    return context


def _extract_date_from_filename(filename: str, folder_name: str = "") -> str:
    """
    Wyciąga datę z nazwy pliku w formacie DD.MM.YYYY.

    Szuka wzorców:
      - DD-MM-YY (np. 2-12-25, 23-01-26)
      - DD-MM-YYYY (np. 23-01-2026)
      - DD.MM.YY (np. 2.12.25)
      - DD.MM.YYYY (np. 23.01.2026)
      - YYYY-MM-DD (np. 2025-12-02)

    Jeśli nie znaleziona w pliku → szuka w nazwie folderu projektu.
    Fallback: dzisiejsza data.

    Zwraca: DD.MM.YYYY
    """

    # --- OPCJA 1: Szukaj w nazwie pliku ---

    # Pattern: DD-MM-YY lub DD-MM-YYYY
    match = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", filename)
    if match:
        day, month, year = match.groups()
        day, month = int(day), int(month)
        year = int(year)

        # Konwersja YY → YYYY (jeśli < 100)
        if year < 100:
            year = 2000 + year if year <= 50 else 1900 + year

        try:
            date_obj = datetime.datetime(year, month, day)
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass  # Niedozwolona data, spróbuj inny pattern

    # Pattern: DD.MM.YY lub DD.MM.YYYY
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", filename)
    if match:
        day, month, year = match.groups()
        day, month = int(day), int(month)
        year = int(year)

        if year < 100:
            year = 2000 + year if year <= 30 else 1900 + year

        try:
            date_obj = datetime.datetime(year, month, day)
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass

    # Pattern: YYYY-MM-DD (ISO format)
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", filename)
    if match:
        year, month, day = match.groups()
        try:
            date_obj = datetime.datetime(int(year), int(month), int(day))
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass

    # --- OPCJA 2: Szukaj w nazwie folderu projektu ---
    if folder_name:
        # Pattern folder: 2025-18-12_xxx lub 2026-01-23_xxx
        match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", folder_name)
        if match:
            year, month, day = match.groups()
            try:
                date_obj = datetime.datetime(int(year), int(month), int(day))
                return date_obj.strftime("%d.%m.%Y")
            except ValueError:
                pass

    # --- FALLBACK: Dzisiejsza data ---
    return datetime.datetime.now().strftime("%d.%m.%Y")


def _scan_project_documents(
    doc_folder: str, project_folder_name: str = ""
) -> list[dict]:
    """
    Skanuje folder projektu — zwraca dokumenty z podziałem:
    - type='network_local':  LP/LC/DWG — link lokalny (C:\)
    - type='network_remote': LP/LC/DWG — link sieciowy (Z:\)
    - type='local_only':     .met/.rey/.ali — link lokalny
    """
    if not doc_folder or not os.path.isdir(doc_folder):
        return []

    found = []
    seen_types = {}

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

        # --- SKIP: Recover files dla DWG ---
        if ext == ".dwg" and "recover" in name_lower:
            print(f"⏭️  Pomijam plik recover: {filename}")
            continue

        label = None
        doc_type = None
        only_local = False

        # --- Rozszerzenia binarne ---
        if ext == ".dwg":
            label = "Rysunek .DWG"
            doc_type = "DWG"
            only_local = False
        elif ext in (".met", ".rey", ".ali"):
            if ext == ".met":
                label = "Plik .MET"
                doc_type = "MET"
            elif ext == ".rey":
                label = "Plik .REY"
                doc_type = "REY"
            else:
                label = "Plik .ALI"
                doc_type = "ALI"
            only_local = True

        # --- Prefixy PDF ---
        elif ext == ".pdf":
            if name_no_ext.upper().startswith("LP") or name_lower.startswith(
                "lista produkcyjna"
            ):
                label = "Lista Produkcyjna"
                doc_type = "LP"
            elif name_no_ext.upper().startswith("LC") or name_lower.startswith(
                "lista cięcia"
            ):
                label = "Lista Cięcia"
                doc_type = "LC"
            elif name_no_ext.upper().startswith("RYS") or name_lower.startswith(
                "rysunek"
            ):
                label = "Rysunek"
                doc_type = "RYS"
            elif name_no_ext.upper().startswith("RK") or name_lower.startswith(
                "rysunek konstrukcyjny"
            ):
                label = "Rysunek Konstrukcyjny"
                doc_type = "RK"
            only_local = False

        if not label:
            continue

        date_str = _extract_date_from_filename(filename, project_folder_name)

        # Unikaj duplikatów
        if doc_type not in seen_types:
            seen_types[doc_type] = 0
        else:
            seen_types[doc_type] += 1
            label = f"{label} ({seen_types[doc_type] + 1})"

        seen_types[doc_type] += 1

        # --- TYLKO LOKALNY: .met, .rey, .ali ---
        if only_local:
            local_link = _local_to_relative(filepath, is_local=True)
            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": local_link,
                    "type": "local_only",
                }
            )
        else:
            # --- LOKALNY + SIECIOWY: LP, LC, Rys, RK, DWG ---
            local_link = _local_to_relative(filepath, is_local=True)
            network_link = _local_to_relative(filepath, is_local=False)

            # Wiersz LOKALNY (dysk C:\)
            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": local_link,
                    "type": "network_local",  # ← NOWY TYP
                }
            )

            # Wiersz SIECIOWY (dysk Z:\)
            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": network_link,
                    "type": "network_remote",  # ← NOWY TYP
                }
            )

    return found


def _build_documents_list(
    doc_folder: str, project_folder_name: str, timestamp: str
) -> list[dict]:
    """
    Buduje listę dokumentów z folderu projektu + wiersze JOB.

    Args:
        doc_folder: ścieżka do folderu z dokumentacją
        project_folder_name: nazwa folderu projektu (do fallback na datę)
        timestamp: bieżąca data dla JOB (format DD.MM.YYYY)
    """
    documents = []

    # Skanuj folder (przekaż project_folder_name dla fallback)
    scanned = _scan_project_documents(doc_folder, project_folder_name)
    documents.extend(scanned)

    # Dodaj wiersze JOB
    job_links = _build_job_links(timestamp)
    documents.extend(job_links)

    return documents


def _build_job_links(timestamp: str) -> list[dict]:
    """
    Zwraca wiersze dla JOB (lokalny i sieciowy).
    """
    local_norm = JOB_PATH_LOCAL.replace("\\", "/")
    job_network_rel = "../../../../JOB/Lotti/"

    local_link = _url_encode(f"{local_norm}/")
    network_link = _url_encode(job_network_rel)

    return [
        {
            "name": "Plik JOB",
            "date": timestamp,
            "path": local_link,
            "type": "network_local",  # ← LOKALNY (dysk C:\)
        },
        {
            "name": "Plik JOB",
            "date": timestamp,
            "path": network_link,
            "type": "network_remote",  # ← SIECIOWY (dysk Z:\)
        },
    ]


def _build_hardware_catalog_link(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> tuple[str, bool]:
    """
    Wylicza link do PDF okucia w katalogu.

    Logika:
    1. Szukaj rzeczywistego pliku pasującego do kodu
    2. Jeśli znajdziesz → zwróć link do niego (file_exists=True)
    3. Jeśli nie → zwróć fallback {kod}_obrobka.pdf (file_exists=False)

    Konwencja fallback: {kod}_obrobka.pdf
    Przykład: 87122404_obrobka.pdf

    Zwraca:
        (link_relatywny, czy_plik_istnieje)

    Przykłady zwrotu:
        ("../../../Katalogi/Aluprof/MB-70/8712_2404_Sruba_RC4.pdf", True)   # Found
        ("../../../Katalogi/Aluprof/MB-70/87122404_obrobka.pdf", False)      # Fallback
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        print(f"⚠️  Vendor '{vendor_key}' nie znaleziony")
        return "#", False

    sys_folder_upper = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder_upper)

    # Jeśli folder nie istnieje — zwróć fallback
    if not os.path.isdir(hw_dir):
        print(f"⚠️  Folder nie istnieje: {hw_dir}")
        code_normalized = hw_code.replace(" ", "_")
        fallback_filename = f"{code_normalized}_obrobka.pdf"
        rel_link = (
            f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/"
            f"{vendor_folder}/{sys_folder_upper}/{fallback_filename}"
        )
        return _url_encode(rel_link), False

    # Normalizuj kod do szukania: usuń spacje, zamień . na nic
    code_search = hw_code.replace(" ", "").replace(".", "").lower()

    # Szukaj PDF-a pasującego do kodu
    try:
        all_files = os.listdir(hw_dir)
        pdf_files = [f for f in all_files if f.lower().endswith(".pdf")]

        # Szukamy pliku zaczynającego się od znormalizowanego kodu
        matching_files = [
            f
            for f in pdf_files
            if f.lower().replace("_", "").replace(".", "").startswith(code_search)
        ]

        if matching_files:
            # Znaleźliśmy plik! Zwróć link do niego
            found_filename = matching_files[0]
            rel_link = (
                f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/"
                f"{vendor_folder}/{sys_folder_upper}/{found_filename}"
            )
            print(f"✅ Znaleziony: {hw_code} → {found_filename}")
            return _url_encode(rel_link), True

    except PermissionError:
        print(f"⚠️  Brak dostępu do: {hw_dir}")

    # Nie znaleziono — zwróć fallback
    code_normalized = hw_code.replace(" ", "_")
    fallback_filename = f"{code_normalized}_obrobka.pdf"
    rel_link = (
        f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/"
        f"{vendor_folder}/{sys_folder_upper}/{fallback_filename}"
    )
    print(f"⚠️  Brak pliku (fallback): {hw_code} → {fallback_filename}")
    return _url_encode(rel_link), False


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

    csv_path = select_file("CSV", "Wybierz plik LP_dane.csv (Ilości)")
    if not csv_path:
        print("❌ Anulowano wybór pliku CSV.")
        exit()

    zm_path = select_file("CSV", "Wybierz plik ZM_dane.csv (Baza Wiedzy)")
    if not zm_path:
        print("❌ Anulowano wybór pliku ZM.")
        exit()

    base_proj_dir = PROJECTS_IMAGES
    print(f"📂 Wybierz folder projektu (rzuty) w: {base_proj_dir}")
    project_dir = select_folder("Wybierz folder projektu (zrzuty)")
    if not project_dir:
        print("❌ Anulowano wybór projektu.")
        exit()

    project_name = os.path.basename(project_dir)
    print(f"✅ Wybrano projekt: {project_name}")

    vendor_profile = select_vendor()
    if not vendor_profile:
        print("❌ Anulowano wybór dostawcy.")
        exit()

    vendor_key = vendor_profile.KEY
    print(f"✅ Wybrano dostawcę: {vendor_key}")

    # TYMCZASOWE: Wybór manual zamiast _select_designer_and_find_project
    print("\n📂 Wybierz folder z dokumentacją projektu")
    doc_folder = select_folder("Wybierz folder z dokumentacją projektu")

    if not doc_folder:
        print("⚠️ Nie wybrano folderu dokumentacji — sekcja Dokumentacja będzie pusta.")
        doc_folder = ""
    else:
        print(f"✅ Folder dokumentacji: {doc_folder}")

    if os.path.exists(csv_path):
        ctx = prepare_context(csv_path, zm_path, project_name, vendor_key, doc_folder)
        render_markdown(ctx)
    else:
        print(f"❌ Plik nie istnieje: {csv_path}")
