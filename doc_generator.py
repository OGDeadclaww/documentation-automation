# doc_generator.py
import os
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
from config import PROJECTS_IMAGES

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
        return f"../../projects_images/{project_name}/views/{filename}"

    return "../../logo.png"  # Placeholder jeśli brak zdjęcia (lub pusta ścieżka)


def _get_profiles_for_position(csv_path, pos_num, vendor_key, vendor_cls, sys_name):
    """
    Pobiera i przetwarza profile dla pozycji.
    """
    raw_data = get_data_for_position(csv_path, pos_num, vendor_cls)
    processed_profiles = []

    for prof in raw_data["profiles"]:
        code_raw = prof["code"]

        # Logika ścieżek obrazków (Vendor specific)
        if vendor_key == "reynaers":
            sys_folder = sys_name.lower()
            img_filename = f"{code_raw}.jpg"
        else:
            # Aluprof
            sys_folder = sys_name.lower().replace(" ", "")
            img_filename = f"{code_raw}.jpg"

        # Ścieżka do bazy zdjęć
        img_path = f"../../images_db/{vendor_key}/profiles/{sys_folder}/{img_filename}"

        prof["image_path"] = img_path
        processed_profiles.append(prof)

    return processed_profiles


def _get_hardware_for_position(hardware_raw, pos_num, vendor_key):
    """
    Filtruje globalną listę okuć dla konkretnej pozycji.
    """
    pos_hardware = []
    for code, details in hardware_raw.items():
        if pos_num in details["positions"]:
            # Ścieżka do zdjęcia okucia
            img_path = f"../../images_db/{vendor_key}/hardware/{code}.jpg"

            pos_hardware.append(
                {
                    "code": code,
                    "desc": details.get("desc", "Okucie"),
                    "quantity": "Wg listy",  # TODO: Parsowanie ilości z CSV
                    "image_path": img_path,
                    "catalog_link": "#",
                    "checklist_id": f"{code.replace(' ', '_')}_{pos_num}",  # Unikalne ID do linków
                }
            )
    return pos_hardware


# ==========================================
# GŁÓWNA LOGIKA (Controller)
# ==========================================


def prepare_context(csv_file, project_name, vendor_key):
    """
    Główny kontroler - zbiera dane z modułów i pakuje w słownik dla Jinja2.
    """
    print(f"⚙️  Generowanie danych dla: {project_name}...")

    vendor_cls = get_vendor_by_key(vendor_key)

    # 1. Dane podstawowe
    systems_map = get_positions_with_systems(csv_file)
    hardware_raw = parse_hardware_from_csv(csv_file, vendor_cls)
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")

    # 2. Inicjalizacja kontekstu
    context = {
        "project_name": project_name,
        "project_id": "PXXXXXX - BEDDELEEM",  # TODO: Wyciągnąć z nazwy pliku lub .met
        "logo_path": "../../logo.png",
        "pdf_output_path": f"Z:/Projekty/{project_name}/{project_name}.pdf",
        "generation_date": timestamp,
        "author": os.getlogin(),
        "systems": list(systems_map.keys()),
        "systems_data": {},
        "global_hardware": [],
        # Sekcje dokumentacyjne (na razie mocki lub proste linki)
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

    # 3. Przetwarzanie Okuć (Tabela zbiorcza)
    for code, details in hardware_raw.items():
        context["global_hardware"].append(
            {
                "code": code,
                "desc": details.get("desc", ""),
                "image_path": f"../../images_db/{vendor_key}/hardware/{code}.jpg",
                "catalog_link": "#",
                "status": "🟡 0/0",
                "notes": "",
            }
        )

    # 4. Przetwarzanie Systemów i Pozycji (Pętla główna)
    for sys_name, positions in systems_map.items():
        system_entries = []

        for pos_num in positions:
            # Używamy modułów pomocniczych!
            view_path = _get_view_for_position(project_name, pos_num)
            profiles = _get_profiles_for_position(
                csv_file, pos_num, vendor_key, vendor_cls, sys_name
            )
            hardware = _get_hardware_for_position(hardware_raw, pos_num, vendor_key)

            # Placeholder na "Uwagi do konstrukcji"
            # Baloon notes placeholder to tekst, który ewentualnie podmienisz
            # innym skryptem lub zostawisz do ręcznej edycji
            notes_placeholder = f"__BALOON_NOTES_PLACEHOLDER__POZ_{pos_num}__"

            system_entries.append(
                {
                    "number": pos_num,
                    "view_image_path": view_path,
                    "profiles": profiles,
                    "hardware": hardware,
                    "construction_notes": notes_placeholder,
                }
            )

        context["systems_data"][sys_name] = system_entries

    return context


if __name__ == "__main__":
    # Test manualny - ustaw tu prawdziwą ścieżkę do CSV
    # np. Z:/Projekty/2026/.../LP_dane.csv

    csv_path = input("Podaj ścieżkę do pliku CSV (lub Enter dla LP_dane.csv): ").strip()
    if not csv_path:
        csv_path = "LP_dane.csv"

    project_name = input("Podaj nazwę projektu (folder w projects_images): ").strip()
    if not project_name:
        project_name = "Test_Project"

    vendor = input("Podaj dostawcę (aluprof/reynaers): ").strip().lower()
    if not vendor:
        vendor = "aluprof"

    if os.path.exists(csv_path):
        ctx = prepare_context(csv_path, project_name, vendor)
        render_markdown(ctx)
    else:
        print(f"❌ Plik nie istnieje: {csv_path}")
