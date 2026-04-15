# rename_images.py
"""
Główny skrypt orkiestrujący przetwarzanie obrazków.
Wersja z automatycznym wykrywaniem plików w folderze źródłowym.
Obsługuje rozszerzenia: .MET (Aluprof), .REY (Reynaers), .ALI (Aliplast).
"""

import glob
import os
from tkinter import messagebox

from auth import check_authorization, log_audit
from config import BASE_PATH, IMAGES_DB, PROJECTS_IMAGES
from core.versioning import get_clean_system_name
from gui.gui import (
    confirm_detected_colors,
    get_project_prefix_from_met,
    select_folder,
    select_project_from_list,
    select_vendor,
    validate_and_choose_system,
)
from html_processor import (
    build_hardware_mapping_from_lp_html,
    get_rk_images_from_html,
    rename_hardware,
    rename_profiles_from_lp_html,
    rename_views,
)
from parsers.csv_parser import (
    extract_color_codes_from_csv,
    extract_system_from_csv,
    get_positions_from_csv,
    get_positions_with_systems,
    get_profile_codes_by_system,
    parse_hardware_from_csv,
)
from parsers.vendors import VENDOR_PROFILES


def find_file_by_pattern(folder, pattern, description):
    """Pomocnicza funkcja do szukania pliku wg wzorca."""
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        return None
    # Jeśli znaleziono wiele, bierzemy pierwszy
    filename = os.path.basename(files[0])
    print(f"   ✓ Znaleziono {description}: {filename}")
    return files[0]


def find_folder_by_pattern(folder, pattern, description):
    """Pomocnicza funkcja do szukania folderu wg wzorca."""
    paths = glob.glob(os.path.join(folder, pattern))
    dirs = [p for p in paths if os.path.isdir(p)]
    if not dirs:
        return None
    dirname = os.path.basename(dirs[0])
    print(f"   ✓ Znaleziono {description}: {dirname}")
    return dirs[0]


def auto_detect_vendor(csv_file, meta_file):
    """
    Próbuje wykryć dostawcę na podstawie systemu w CSV
    oraz rozszerzenia pliku meta (.REY, .ALI).
    """
    print("   🔍 Analiza danych w celu wykrycia dostawcy...")

    # 1. Sprawdzenie po rozszerzeniu pliku
    if meta_file:
        ext = os.path.splitext(meta_file)[1].lower()
        if ext == ".rey":
            return VENDOR_PROFILES["reynaers"]
        if ext == ".ali":
            # Zakładamy, że Aliplast używa parsera Aluprof (zgodnie z vendors.py)
            return VENDOR_PROFILES["aliplast"]

    # 2. Analiza CSV (System)
    sys_name = extract_system_from_csv(csv_file)
    if not sys_name:
        systems_map = get_positions_with_systems(csv_file)
        if systems_map:
            sys_name = list(systems_map.keys())[0]

    if not sys_name:
        return None

    sys_lower = sys_name.lower()

    if "mb-" in sys_lower:
        return VENDOR_PROFILES["aluprof"]
    if any(x in sys_lower for x in ["masterline", "cs-", "cp-", "slimline", "hi-finity"]):
        return VENDOR_PROFILES["reynaers"]
    if "aliplast" in sys_lower:
        return VENDOR_PROFILES["aliplast"]

    return None


def main():
    print("=" * 60)
    print("REORGANIZACJA BAZY OBRAZKÓW (AUTO-WYKRYWANIE)")
    print("=" * 60)

    check_authorization()

    # [1] Wybierz folder źródłowy
    print("\n[1/3] Wybierz folder z wyeksportowanymi plikami (źródło)...")
    source_dir = select_folder("Wybierz folder z plikami (.MET/.REY, CSV, HTML)")
    if not source_dir:
        print("Anulowano.")
        return

    print(f"📂 Źródło: {source_dir}\n")

    # --- Automatyczne szukanie plików ---

    # 1. Plik projektu (MET / REY / ALI)
    meta_file = find_file_by_pattern(source_dir, "*.met", "Plik Aluprof (.MET)")
    if not meta_file:
        meta_file = find_file_by_pattern(source_dir, "*.rey", "Plik Reynaers (.REY)")
    if not meta_file:
        meta_file = find_file_by_pattern(source_dir, "*.ali", "Plik Aliplast (.ALI)")

    # 2. Plik CSV
    csv_file = find_file_by_pattern(source_dir, "*dane*.csv", "Plik CSV")
    if not csv_file:
        csv_file = find_file_by_pattern(source_dir, "*.csv", "Plik CSV (alt)")

    # 3. HTML i foldery
    rk_html = find_file_by_pattern(source_dir, "*RK*images.html", "RK HTML")
    rk_dir = find_folder_by_pattern(source_dir, "*RK*images.files", "RK Folder")

    lp_html = find_file_by_pattern(source_dir, "*LP*images.html", "LP HTML")
    lp_dir = find_folder_by_pattern(source_dir, "*LP*images.files", "LP Folder")

    # Weryfikacja braków
    missing = []
    if not meta_file:
        missing.append("Plik projektu (.MET / .REY / .ALI)")
    if not csv_file:
        missing.append("Plik CSV (dane)")
    if not rk_html:
        missing.append("RK_images.html")
    if not rk_dir:
        missing.append("Folder RK_images.files")
    if not lp_html:
        missing.append("LP_images.html")
    if not lp_dir:
        missing.append("Folder LP_images.files")

    if missing:
        msg = "Nie znaleziono następujących plików w wybranym folderze:\n- " + "\n- ".join(missing)
        messagebox.showerror("Braki w plikach", msg)
        return

    # [2] Wykrywanie dostawcy
    print("\n[2/3] Wykrywanie dostawcy...")
    vendor_profile = auto_detect_vendor(csv_file, meta_file)

    if vendor_profile:
        print(f"✓ Wykryto dostawcę: {vendor_profile.NAME}")
    else:
        print("⚠️ Nie udało się wykryć dostawcy automatycznie.")
        vendor_profile = select_vendor()
        if not vendor_profile:
            return

    vendor_key = vendor_profile.KEY

    # Wykrywanie kolorów
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

    # --- PRZETWARZANIE ---
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

    print("\n📋 Wykryte systemy:")
    for sys_name, pos_list in systems_map.items():
        print(f"   {sys_name}: Poz. {', '.join(pos_list)}")

    output_views = os.path.join(PROJECTS_IMAGES, project_name, "views")
    output_hardware = os.path.join(IMAGES_DB, vendor_key, "hardware")
    os.makedirs(output_views, exist_ok=True)
    os.makedirs(output_hardware, exist_ok=True)

    # KROK 1: Rzuty
    print("\n[KROK 1/4] Przetwarzanie rzutów...")
    # Funkcja get_project_prefix_from_met powinna działać też dla .REY/.ALI
    # pod warunkiem, że wewnątrz struktura jest tekstowa lub nazwa pliku jest kluczowa.
    prefix = get_project_prefix_from_met(meta_file)

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

        # --- ZMIANA: CZYŚCIMY NAZWĘ SYSTEMU TAK SAMO JAK W DOC_GENERATOR ---
        clean_sys_name = get_clean_system_name(sys_name).upper()
        # -------------------------------------------------------------------

        output_profiles = os.path.join(IMAGES_DB, vendor_key, "profiles", clean_sys_name)
        os.makedirs(output_profiles, exist_ok=True)

        print(f"\n  📁 System: {clean_sys_name} ({len(profile_codes)} profili)")
        for code in sorted(profile_codes):
            print(f"     {code}")

        rename_profiles_from_lp_html(
            lp_html,
            lp_dir,
            output_profiles,
            vendor_profile,
            allowed_codes=profile_codes,
        )

    # KROK 3: Okucia
    print("\n[KROK 3/4] Parsowanie okuć z CSV...")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)

    # KROK 4: Kopiowanie okuć
    print("\n[KROK 4/4] Przetwarzanie okuć...")
    code_to_srcfile = build_hardware_mapping_from_lp_html(lp_html, lp_dir, vendor_profile)
    rename_hardware(hardware_codes, code_to_srcfile, lp_dir, output_hardware)

    # Audit
    log_audit(
        "IMAGES_PROCESSED",
        {
            "project": project_name,
            "vendor": vendor_key,
            "source_dir": source_dir,
            "meta_file": os.path.basename(meta_file),
            "systems": list(systems_map.keys()),
            "positions": len(all_positions),
            "hardware": len(hardware_codes),
        },
    )

    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)
    systems_text = ", ".join(systems_map.keys())
    messagebox.showinfo(
        "Sukces!",
        f"Obrazki przetworzone!\n\n"
        f"Projekt: {project_name}\n"
        f"Dostawca: {vendor_profile.NAME}\n"
        f"Plik: {os.path.basename(meta_file)}\n"
        f"Systemy: {systems_text}\n"
        f"Pozycje: {len(all_positions)}\n"
        f"Okucia: {len(hardware_codes)}",
    )


if __name__ == "__main__":
    main()
