# doc_generator.py
import os
import datetime
from jinja2 import Environment, FileSystemLoader

from vendors import get_vendor_by_key
from csv_parser import (
    get_positions_with_systems,
    extract_system_from_csv,
    parse_hardware_from_csv,
    get_data_for_position
)

# KONFIGURACJA
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

def prepare_context(csv_file, project_name, vendor_key):
    """
    Adapter: Zamienia dane z CSV na słownik dla Jinja2.
    """
    print(f"⚙️ Przetwarzanie danych dla projektu: {project_name} ({vendor_key})...")
    
    vendor_cls = get_vendor_by_key(vendor_key)
    
    # 1. Pobieramy strukturę systemów i pozycji
    systems_map = get_positions_with_systems(csv_file)
    
    # 2. Pobieramy okucia (Globalnie)
    hardware_raw = parse_hardware_from_csv(csv_file, vendor_cls)
    
    # 3. Budujemy Context
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")
    
    context = {
        "project_name": project_name,
        "project_id": "Raport Generowany Automatycznie",
        "logo_path": "../../logo.png",
        "pdf_output_path": f"Z:/Projekty/{project_name}/{project_name}.pdf",
        "generation_date": timestamp,
        "author": os.getlogin(),
        
        "systems": list(systems_map.keys()),
        "systems_data": {},
        "global_hardware": [],
        
        # Mocki dla sekcji, których jeszcze nie parsujemy z plików
        "documents": [
            {"name": "Lista produkcyjna (CSV)", "date": timestamp, "path": f"../../{os.path.basename(csv_file)}"}
        ],
        "catalogs": [], 
        "instructions": []
    }

    # -- Przetwarzanie Okuć Globalnych --
    for code, details in hardware_raw.items():
        # Obrazek: ../../images_db/aluprof/hardware/CODE.jpg
        img_path = f"../../images_db/{vendor_key}/hardware/{code}.jpg"
        
        context["global_hardware"].append({
            "code": code,
            "desc": details.get("desc", "Okucie systemowe"),
            "image_path": img_path,
            "catalog_link": "#", 
            "status": "🟡",
            "notes": ""
        })

    # -- Przetwarzanie Systemów i Pozycji --
    for sys_name, positions in systems_map.items():
        system_entries = []
        
        for pos_num in positions:
            print(f"   Reading Pos {pos_num}...")
            
            # Pobieramy szczegóły pozycji z CSV
            pos_details = get_data_for_position(csv_file, pos_num, vendor_cls)
            
            # Budujemy ścieżkę do rzutu (View)
            # Uwaga: prefix projektu trzeba by wyciągnąć z .met, tu zakładamy uproszczenie
            view_path = f"../../projects_images/{project_name}/views/{project_name}_Poz_{pos_num}.jpg"

            # Profile - mapujemy obrazki
            processed_profiles = []
            for prof in pos_details["profiles"]:
                code_raw = prof["code"]
                
                # Logika ścieżek zależna od dostawcy
                if vendor_key == "reynaers":
                    # Reynaers ma foldery systemowe (np. masterline-8)
                    # A pliki to np. 008.3144.XX.jpg
                    # Upewniamy się, że system w ścieżce jest poprawny (małe litery)
                    sys_folder = sys_name.lower()
                    img_filename = f"{code_raw}.jpg"
                else:
                    # Aluprof: K12345X.jpg
                    sys_folder = sys_name.lower().replace(" ", "") # np mb-70
                    img_filename = f"{code_raw}.jpg"

                prof["image_path"] = f"../../images_db/{vendor_key}/profiles/{sys_folder}/{img_filename}"
                processed_profiles.append(prof)

            # Okucia dla pozycji - filtrujemy globalną listę
            pos_hardware = []
            for code, details in hardware_raw.items():
                if pos_num in details["positions"]:
                    pos_hardware.append({
                        "code": code,
                        "desc": details.get("desc", ""),
                        "quantity": "Wg listy", # CSV parser musiałby zliczać to dokładnie
                        "image_path": f"../../images_db/{vendor_key}/hardware/{code}.jpg",
                        "catalog_link": "#"
                    })

            system_entries.append({
                "number": pos_num,
                "view_image_path": view_path,
                "profiles": processed_profiles,
                "hardware": pos_hardware
            })
            
        context["systems_data"][sys_name] = system_entries

    return context

if __name__ == "__main__":
    # Test manualny
    TEST_CSV = "LP_dane.csv"
    TEST_PROJECT = "Test_Project"
    TEST_VENDOR = "aluprof" # lub 'reynaers'
    
    if os.path.exists(TEST_CSV):
        ctx = prepare_context(TEST_CSV, TEST_PROJECT, TEST_VENDOR)
        render_markdown(ctx)
    else:
        print(f"❌ Brak pliku {TEST_CSV} w folderze scripts.")
        print("   Skopiuj tam plik CSV, aby przetestować generator.")