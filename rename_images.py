# rename_images.py
"""
Główny skrypt orkiestrujący przetwarzanie obrazków.
Wersja z automatycznym wykrywaniem plików w folderze źródłowym.
"""
import os
import glob
from tkinter import messagebox

from config import BASE_PATH, PROJECTS_IMAGES, IMAGES_DB
from auth import check_authorization, log_audit
from vendors import VENDOR_PROFILES
from gui import (
    select_vendor,
    select_project_from_list,
    select_folder,
    get_project_prefix_from_met,
    validate_and_choose_system,
    confirm_detected_colors,
)
from csv_parser import (
    get_positions_from_csv,
    extract_system_from_csv,
    extract_color_codes_from_csv,
    parse_hardware_from_csv,
    get_profile_codes_by_system,
    get_positions_with_systems,
)
from html_processor import (
    get_rk_images_from_html,
    rename_views,
    rename_profiles_from_lp_html,
    build_hardware_mapping_from_lp_html,
    rename_hardware,
)

def find_file_by_pattern(folder, pattern, description):
    """Pomocnicza funkcja do szukania pliku wg wzorca."""
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        return None
    # Jeśli znaleziono wiele, preferuj ten najnowszy lub najkrótszy?
    # Bierzemy pierwszy pasujący.
    print(f"   ✓ Znaleziono {description}: {os.path.basename(files[0])}")
    return files[0]

def find_folder_by_pattern(folder, pattern, description):
    """Pomocnicza funkcja do szukania folderu wg wzorca."""
    paths = glob.glob(os.path.join(folder, pattern))
    dirs = [p for p in paths if os.path.isdir(p)]
    if not dirs:
        return None
    print(f"   ✓ Znaleziono {description}: {os.path.basename(dirs[0])}")
    return dirs[0]

def auto_detect_vendor(csv_file):
    """Próbuje wykryć dostawcę na podstawie systemu w CSV."""
    print("   🔍 Analiza CSV w celu wykrycia dostawcy...")
    
    # Próbujemy znaleźć system (np. "mb-86", "masterline-8")
    sys_name = extract_system_from_csv(csv_file)
    
    if not sys_name:
        # Fallback: szukamy systemów w pozycjach
        systems_map = get_positions_with_systems(csv_file)
        if systems_map:
            sys_name = list(systems_map.keys())[0]

    if not sys_name:
        return None

    sys_lower = sys_name.lower()

    # Logika mapowania system -> dostawca
    if "mb-" in sys_lower:
        return VENDOR_PROFILES["aluprof"]
    if "masterline" in sys_lower or "cs-" in sys_lower or "cp-" in sys_lower or "slimline" in sys_lower or "hi-finity" in sys_lower:
        return VENDOR_PROFILES["reynaers"]
    if "aliplast" in sys_lower: # przykładowo
        return VENDOR_PROFILES["aliplast"]
    
    return None

def main():
    print("=" * 60)
    print("REORGANIZACJA BAZY OBRAZKÓW (AUTO-WYKRYWANIE)")
    print("=" * 60)

    check_authorization()

    # [1] Wybierz folder źródłowy z plikami
    print("\n[1/3] Wybierz folder z wyeksportowanymi plikami (źródło)...")
    source_dir = select_folder("Wybierz folder z plikami (.MET, .CSV, .HTML)")
    if not source_dir:
        print("Anulowano.")
        return

    print(f"📂 Źródło: {source_dir}\n")

    # Automatyczne szukanie plików
    met_file = find_file_by_pattern(source_dir, "*.met", "Plik MET")
    csv_file = find_file_by_pattern(source_dir, "*dane*.csv", "Plik CSV") # Zazwyczaj LP_dane.csv
    if not csv_file:
         # Fallback jeśli nazwa inna
         csv_file = find_file_by_pattern(source_dir, "*.csv", "Plik CSV (alternatywny)")

    rk_html = find_file_by_pattern(source_dir, "*RK*images.html", "RK HTML")
    rk_dir = find_folder_by_pattern(source_dir, "*RK*images.files", "RK Folder")
    
    lp_html = find_file_by_pattern(source_dir, "*LP*images.html", "LP HTML")
    lp_dir = find_folder_by_pattern(source_dir, "*LP*images.files", "LP Folder")

    # Weryfikacja braków
    missing = []
    if not met_file: missing.append("Plik .MET")
    if not csv_file: missing.append("Plik CSV (dane)")
    if not rk_html: missing.append("RK_images.html")
    if not rk_dir: missing.append("Folder RK_images.files")
    if not lp_html: missing.append("LP_images.html")
    if not lp_dir: missing.append("Folder LP_images.files")

    if missing:
        msg = "Nie znaleziono następujących plików w wybranym folderze:\n- " + "\n- ".join(missing)
        messagebox.showerror("Braki w plikach", msg)
        return

    # [2] Wykrywanie dostawcy
    print("\n[2/3] Wykrywanie dostawcy...")
    vendor_profile = auto_detect_vendor(csv_file)
    
    if vendor_profile:
        print(f"✓ Wykryto dostawcę: {vendor_profile.NAME}")
    else:
        print("⚠️ Nie udało się wykryć dostawcy automatycznie.")
        vendor_profile = select_vendor() # Manualny wybór
        if not vendor_profile:
            return

    vendor_key = vendor_profile.KEY

    # Wykrywanie kolorów (potwierdzenie usera)
    print("    Wykrywanie koloru projektu...")
    detected_colors = extract_color_codes_from_csv(csv_file)
    confirm_detected_colors(detected_colors)

    # [3] Projekt docelowy
    print("\n[3/3] Wybierz projekt docelowy (gdzie zapisać zdjęcia)...")
    projects_folder = os.path.join(BASE_PATH, "projects")
    project_name = select_project_from_list(projects_folder)
    if not project_name:
        messagebox.showerror("Błąd", "Nie wybrano projektu.")
        return
    print(f"✓ Projekt docelowy: {project_name}\n")


    # Przetwarzanie (reszta logiki bez zmian)
    print("=" * 60)
    print(f"PRZETWARZANIE - Dostawca: {vendor_profile.NAME}")
    print("=" * 60)

    # Wykryj systemy
    systems_map = get_positions_with_systems(csv_file)
    if not systems_map:
        system = validate_and_choose_system(csv_file, extract_system_from_csv)
        if not system:
            messagebox.showerror("Błąd", "Nie podano systemu.")
            return
        positions = get_positions_from_csv(csv_file)
        systems_map = {system: positions}
    
    print(f"\n📋 Wykryte systemy:")
    for sys_name, pos_list in systems_map.items():
        print(f"   {sys_name}: Poz. {', '.join(pos_list)}")

    output_views = os.path.join(PROJECTS_IMAGES, project_name, "views")
    output_hardware = os.path.join(IMAGES_DB, vendor_key, "hardware")
    os.makedirs(output_views, exist_ok=True)
    os.makedirs(output_hardware, exist_ok=True)

    # KROK 1: Rzuty
    print("\n[KROK 1/4] Przetwarzanie rzutów...")
    prefix = get_project_prefix_from_met(met_file)
    all_positions = []
    for pos_list in systems_map.values():
        all_positions.extend(pos_list)
    
    rk_images = get_rk_images_from_html(rk_html)
    rename_views(all_positions, rk_images, rk_dir, prefix, output_views)

    # KROK 2: Profile
    print("\n[KROK 2/4] Przetwarzanie profili...")
    profiles_by_system = get_profile_codes_by_system(csv_file, vendor_profile)

    for sys_name in systems_map.keys():
        profile_codes = profiles_by_system.get(sys_name, set())
        output_profiles = os.path.join(IMAGES_DB, vendor_key, "profiles", sys_name)
        os.makedirs(output_profiles, exist_ok=True)

        print(f"\n  📁 System: {sys_name} ({len(profile_codes)} profili)")
        for code in sorted(profile_codes):
            print(f"     {code}")

        rename_profiles_from_lp_html(
            lp_html, lp_dir, output_profiles, vendor_profile,
            allowed_codes=profile_codes
        )

    # KROK 3: Okucia
    print("\n[KROK 3/4] Parsowanie okuć z CSV...")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)
    
    # KROK 4: Kopiowanie okuć
    print("\n[KROK 4/4] Przetwarzanie okuć...")
    code_to_srcfile = build_hardware_mapping_from_lp_html(
        lp_html, lp_dir, vendor_profile
    )
    rename_hardware(hardware_codes, code_to_srcfile, lp_dir, output_hardware)

    # Audit
    log_audit("IMAGES_PROCESSED", {
        "project": project_name,
        "vendor": vendor_key,
        "source_dir": source_dir,
        "systems": list(systems_map.keys()),
        "positions": len(all_positions),
        "hardware": len(hardware_codes),
    })

    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)
    systems_text = ", ".join(systems_map.keys())
    messagebox.showinfo(
        "Sukces!",
        f"Obrazki przetworzone!\n\n"
        f"Projekt: {project_name}\n"
        f"Dostawca: {vendor_profile.NAME}\n"
        f"Systemy: {systems_text}\n"
        f"Pozycje: {len(all_positions)}\n"
        f"Okucia: {len(hardware_codes)}"
    )

if __name__ == "__main__":
    main()