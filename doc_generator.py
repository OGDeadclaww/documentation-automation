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
    parse_hardware_from_csv,
    get_data_for_position,
)
from config import PROJECTS_IMAGES, BASE_PATH
from gui import select_file, select_folder, select_vendor
from db_builder import build_product_db

# KONFIGURACJA ŚCIEŻEK
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def render_markdown(context, output_filename="Dokumentacja.md"):
    """Renderuje szablon Jinja2 do pliku MD."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    try:
        template = env.get_template("project_doc.md.j2")
    except Exception as e:
        print(f"❌ Błąd ładowania szablonu: {e}")
        return

    rendered = template.render(context)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, output_filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✅ Wygenerowano dokumentację: {os.path.abspath(out_path)}")
    _update_project_index(context)


# ==========================================
# MODUŁY POMOCNICZE (Data Providers)
# ==========================================


def _get_view_for_position(project_name, pos_num):
    """
    Szuka pliku graficznego rzutu dla danej pozycji.
    Zwraca ścieżkę relatywną dla Markdowna.
    """
    # Ścieżka fizyczna do folderu z rzutami
    views_dir = os.path.join(PROJECTS_IMAGES, project_name, "views")

    # Szukamy pliku, który kończy się na 'Poz_{X}.jpg'
    # Dzięki temu prefix (np. 'P220667_') nie ma znaczenia, skrypt sam go znajdzie.
    pattern = os.path.join(views_dir, f"*Poz_{pos_num}.jpg")
    found_files = glob.glob(pattern)

    if found_files:
        # Bierzemy pierwszy pasujący plik
        full_path = found_files[0]
        filename = os.path.basename(full_path)
        # Markdown potrzebuje ścieżki względnej z folderu 'output' do 'projects_images'
        # Zakładamy strukturę:
        # /Dokumentacja/scripts/output (tu powstaje MD)
        # /Dokumentacja/projects_images (tu są zdjęcia)
        # ⚠️ URL Encoding dla Markdown
        # project_name może zawierać spacje (np. "Produkcja Beddeleem")
        safe_project_name = project_name.replace(" ", "%20")

        return f"../../projects_images/{safe_project_name}/views/{filename}"

    return "../../logo.png"  # Placeholder jeśli brak zdjęcia (lub pusta ścieżka)


def _parse_project_name(folder_name):
    """
    Rozbija nazwę folderu na części (Klient, Numer, Opis).
    Input: "2025-18-12_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    """
    # 1. Usuwamy datę z początku (RRRR-MM-DD_ lub podobne formaty)
    # Obsługuje 2025-12-18, 2025-18-12, z podkreślnikiem lub spacją
    name_clean = re.sub(r"^\d{4}[-.]\d{2}[-.]\d{2}[_ ]?", "", folder_name).strip()

    # 2. Szukamy numeru projektu (P + 5-6 cyfr)
    match = re.search(r"\b(P\d{5,6})\b", name_clean)

    if match:
        number = match.group(1)
        parts = name_clean.split(number)

        # To co przed numerem (np. "Produkcja Beddeleem_ ")
        client = parts[0].strip(" _-")

        # To co po numerze (np. " BMEIA AUSTRIA")
        desc = parts[1].strip(" _-") if len(parts) > 1 else ""

        return {"client": client, "number": number, "desc": desc}
    else:
        # Fallback: Cała nazwa jako Klient, brak numeru
        return {"client": name_clean, "number": "", "desc": ""}


def _normalize_reynaers_code(code):
    """
    Zamienia sufiks koloru na XX.
    Np. 108.0081.59 7021-2 -> 108.0081.XX
    """
    parts = code.split(".")
    if len(parts) >= 3:
        # Zastępujemy ostatnią część XX
        return f"{parts[0]}.{parts[1]}.XX"
    return code


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
            if vendor_key == "reynaers":
                sys_folder = sys_name.lower()
                img_filename = f"{display_code}.jpg"
            else:
                sys_folder = sys_name.lower().replace(" ", "")
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

        if prof["quantity"]:
            grouped[display_code]["quantities"].append(prof["quantity"])
        if prof["dimensions"]:
            grouped[display_code]["dimensions"].append(prof["dimensions"])
        if prof["location"] and prof["location"] != "—":
            grouped[display_code]["locations"].append(prof["location"])

    processed_profiles = []
    for code, data in grouped.items():
        # Zachowanie kolejności unikalnych lokalizacji (A, B, A..B zamiast losowo)
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


def _get_hardware_for_position(hardware_raw, pos_num, vendor_key):
    """
    Filtruje globalną listę okuć dla konkretnej pozycji.
    Zwraca listę słowników gotowych dla Jinja2.
    """
    pos_hardware = []

    # Konwersja szukanego numeru na string (np. 1 -> "1")
    target_pos_str = str(pos_num).strip()

    for code, details in hardware_raw.items():
        # Pobieramy zbiór pozycji przypisanych do tego okucia
        # Konwertujemy każdy element zbioru na string i czyścimy białe znaki
        assigned_positions = {str(p).strip() for p in details.get("positions", [])}

        if target_pos_str in assigned_positions:
            # Okucie należy do tej pozycji!

            # Budujemy ścieżkę do obrazka
            # Uwaga: Kod okucia może zawierać spacje, w URL zamieniamy na %20
            safe_code = code.replace(" ", "%20")
            img_path = f"../../images_db/{vendor_key}/hardware/{safe_code}.jpg"

            # Generujemy ID do linkowania w checkliście (bez spacji)
            checklist_id = f"{code.replace(' ', '_')}_{pos_num}"

            pos_hardware.append(
                {
                    "code": code,
                    "desc": details.get("desc", "Okucie"),
                    "quantity": "Wg listy",  # Ilość per pozycja wymagałaby głębszego parsowania
                    "image_path": img_path,
                    "catalog_link": "#",
                    "checklist_id": checklist_id,
                }
            )

    return pos_hardware


# ==========================================
# GŁÓWNA LOGIKA (Controller)
# ==========================================


def prepare_context(csv_file, zm_file, project_folder_name, vendor_key):
    print(f"⚙️  Generowanie danych dla: {project_folder_name}...")

    vendor_cls = get_vendor_by_key(vendor_key)

    # 1. Parsowanie Nazwy Projektu (Metadata)
    proj_info = _parse_project_name(project_folder_name)

    # 2. Ścieżka do PDF (Puppeteer)
    # Ścieżka: BASE_PATH/projects/{FOLDER}/{FOLDER}.pdf
    pdf_dir = os.path.join(BASE_PATH, "projects", project_folder_name)
    pdf_filename = f"{project_folder_name}.pdf"
    # Puppeteer wymaga forward slashy w JSON/YAML
    pdf_output_path = os.path.join(pdf_dir, pdf_filename).replace("\\", "/")

    # 3. Budowanie Bazy Wiedzy
    product_db = build_product_db(zm_file)

    # 4. Dane z CSV (LP)
    systems_map = get_positions_with_systems(csv_file)
    # hardware_raw używamy teraz tylko globalnie, jeśli chcemy listę wszystkich okuć w projekcie
    # Ale doc_generator pobiera okucia per pozycja w pętli niżej.
    # Możemy pobrać globalne statystyki dla sekcji "Tabela Okuć i Akcesoriów" na początku dok.
    # Używamy starego parsera hardware_raw (dla statystyk) lub iterujemy po product_db.
    # Dla uproszczenia: zostawiamy starą metodę hardware_raw dla tabeli zbiorczej.
    hardware_raw = parse_hardware_from_csv(csv_file, vendor_cls)

    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")

    # 5. Inicjalizacja kontekstu
    context = {
        # Nagłówek
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
        "documents": [
            {
                "name": "Lista produkcyjna",
                "date": timestamp,
                "path": f"../../{os.path.basename(csv_file)}",
            }
        ],
        "catalogs": [],
        "instructions": [],
    }

    # Tabela zbiorcza okuć (Global)
    for code, details in hardware_raw.items():
        # Pobieramy opis z Bazy Wiedzy, jeśli dostępny
        clean_code = code.replace(" ", "")
        desc = (
            product_db[clean_code]["desc"]
            if (product_db and clean_code in product_db)
            else details.get("desc", "")
        )

        img_path = f"../../images_db/{vendor_key}/hardware/{code}.jpg"

        context["global_hardware"].append(
            {
                "code": code,
                "desc": desc,
                "image_path": img_path.replace(" ", "%20"),
                "catalog_link": "#",
                "status": "🟡 0/0",
                "notes": "",
            }
        )

    # Pętla po Systemach i Pozycjach
    for sys_name, positions in systems_map.items():
        system_entries = []

        for pos_num in positions:
            # Moduły pomocnicze
            view_path = _get_view_for_position(project_folder_name, pos_num)

            # Profile (z użyciem DB)
            profiles = _get_profiles_for_position(
                csv_file, pos_num, vendor_key, vendor_cls, sys_name, product_db
            )

            # Hardware (z użyciem DB i LP)
            # Uwaga: _get_hardware_for_position korzystało ze starego hardware_raw.
            # Powinniśmy użyć get_data_for_position (nowego parsera), żeby wziąć hardware przypisany do pozycji w CSV!
            # To ważna zmiana spójności.

            # Pobieramy WSZYSTKO (profile i hardware) z nowego parsera dla tej pozycji
            pos_data_new = get_data_for_position(
                csv_file, pos_num, vendor_cls, product_db
            )

            # Przetwarzanie Hardware z nowego parsera (tak jak Profile)
            hardware_list = []
            for hw in pos_data_new["hardware"]:
                safe_code = hw["code"].replace(" ", "%20")
                checklist_id = f"{hw['code'].replace(' ', '_')}_{pos_num}"

                hardware_list.append(
                    {
                        "code": hw["code"],
                        "desc": hw["desc"],
                        "quantity": hw["quantity"],  # Teraz mamy ilość per pozycja!
                        "image_path": f"../../images_db/{vendor_key}/hardware/{safe_code}.jpg",
                        "catalog_link": "#",
                        "checklist_id": checklist_id,
                    }
                )

            notes_placeholder = f"__BALOON_NOTES_PLACEHOLDER__POZ_{pos_num}__"

            system_entries.append(
                {
                    "number": pos_num,
                    "view_image_path": view_path,
                    "profiles": profiles,
                    "hardware": hardware_list,  # Używamy nowej listy z ilościami!
                    "construction_notes": notes_placeholder,
                }
            )

        context["systems_data"][sys_name] = system_entries

    return context


def _update_project_index(context):
    index_path = os.path.join(BASE_PATH, "projects", "project_index.json")

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except json.JSONDecodeError:
            index = {}
    else:
        index = {}

    proj_num = context["project_number"] or "UNKNOWN"

    # 1. Zbieramy Okucia (z listy globalnej)
    hardware_used = set()
    for hw in context["global_hardware"]:
        hardware_used.add(hw["code"])

    # 2. Zbieramy Profile (musimy przejść przez systemy i pozycje)
    profiles_used = set()
    for sys_name, positions in context["systems_data"].items():
        for pos in positions:
            for prof in pos["profiles"]:
                # Używamy kodu "display" (z XX), bo jest bardziej generyczny
                profiles_used.add(prof["code"])

    entry = {
        "date": context["generation_date"],
        "client": context["project_client"],
        "desc": context["project_desc"],
        "folder": os.path.basename(os.path.dirname(context["pdf_output_path"])),
        "systems": context["systems"],
        "stats": {
            "hardware_count": len(hardware_used),
            "profiles_count": len(profiles_used),
        },
        "hardware_codes": sorted(list(hardware_used)),
        "profile_codes": sorted(list(profiles_used)),  # <--- NOWOŚĆ
    }

    index[proj_num] = entry

    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"💾 Zaktualizowano indeks projektów: {index_path}")
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać indeksu: {e}")


if __name__ == "__main__":
    print("🚀 Tryb Interaktywny Generatora Dokumentacji")

    # 1. Wybierz CSV (zamiast wpisywać ścieżkę)
    csv_path = select_file("CSV", "Wybierz plik LP_dane.csv (Ilości)")
    if not csv_path:
        print("❌ Anulowano wybór pliku.")
        exit()
    # 1b. Wybierz CSV (ZM) - NOWOŚĆ
    zm_path = select_file("CSV", "Wybierz plik ZM_dane.csv (Baza Wiedzy)")
    if not zm_path:
        print("❌ Anulowano wybór pliku ZM.")
        exit()

    # 2. Wybierz Projekt (Folder ze zdjęciami)
    # Zamiast wpisywać nazwę folderu ręcznie, po prostu go wskaż
    base_proj_dir = os.path.join(PROJECTS_IMAGES)  # Z config.py
    print(f"📂 Wybierz folder projektu w: {base_proj_dir}")
    project_dir = select_folder("Wybierz folder projektu (zrzuty)")

    if not project_dir:
        print("❌ Anulowano wybór projektu.")
        exit()

    project_name = os.path.basename(project_dir)
    print(f"✅ Wybrano projekt: {project_name}")

    # 3. Wybierz Dostawcę
    vendor_profile = select_vendor()
    if not vendor_profile:
        print("❌ Anulowano wybór dostawcy.")
        exit()

    vendor_key = vendor_profile.KEY
    print(f"✅ Wybrano dostawcę: {vendor_key}")

    # Uruchom generator
    if os.path.exists(csv_path):
        ctx = prepare_context(csv_path, zm_path, project_name, vendor_key)
        render_markdown(ctx)
    else:
        print(f"❌ Plik nie istnieje: {csv_path}")
