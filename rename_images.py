# rename_images.py
"""
Główny skrypt orkiestrujący przetwarzanie obrazków.
"""
import os
from tkinter import messagebox

from config import BASE_PATH, PROJECTS_IMAGES, IMAGES_DB
from auth import check_authorization, log_audit
from vendors import clean
from gui import (
    select_vendor,
    select_file,
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
    extract_additional_profiles_from_csv,
)
from html_processor import (
    get_rk_images_from_html,
    rename_views,
    rename_profiles_from_lp_html,
    build_hardware_mapping_from_lp_html,
    rename_hardware,
)


def main():
    print("=" * 60)
    print("REORGANIZACJA BAZY OBRAZKÓW (NOWA STRUKTURA)")
    print("=" * 60)

    check_authorization()

    # [0/7] Dostawca
    print("\n[0/7] Wybierz dostawcę profili...")
    vendor_profile = select_vendor()
    if not vendor_profile:
        messagebox.showerror("Błąd", "Nie wybrano dostawcy.")
        return
    vendor_key = vendor_profile.KEY
    print(f"✓ Wybrano: {vendor_profile.NAME}\n")

    # [1/7] Projekt
    print("[1/7] Wybierz projekt...")
    projects_folder = os.path.join(BASE_PATH, "projects")
    project_name = select_project_from_list(projects_folder)
    if not project_name:
        messagebox.showerror("Błąd", "Nie wybrano projektu.")
        return
    print(f"✓ Wybrano: {project_name}\n")

    # [2/7] Plik MET
    print("[2/7] Wybierz plik .MET...")
    met_file = select_file("MET", "Wybierz plik .MET")
    if not met_file:
        return
    print(f"✓ Wybrano: {os.path.basename(met_file)}\n")

    # [3/7] Plik CSV
    print("[3/7] Wybierz plik CSV...")
    csv_file = select_file("CSV", "Wybierz plik LP_dane.csv")
    if not csv_file:
        return
    print(f"✓ Wybrano: {os.path.basename(csv_file)}\n")
    print("    Wykrywanie koloru projektu...")
    detected_colors = extract_color_codes_from_csv(csv_file)
    confirm_detected_colors(detected_colors)

    # [4/7] RK HTML
    print("[4/7] Wybierz plik RK_images.html...")
    rk_html = select_file("HTML", "Wybierz RK_images.html")
    if not rk_html:
        return
    print(f"✓ Wybrano: {os.path.basename(rk_html)}\n")

    # [5/7] RK folder
    print("[5/7] Wybierz folder RK_images.files...")
    rk_images_dir = select_folder("Wybierz folder RK_images.files")
    if not rk_images_dir:
        return
    print(f"✓ Wybrano: {os.path.basename(rk_images_dir)}\n")

    # [6/7] LP HTML
    print("[6/7] Wybierz plik LP_images.html...")
    lp_html = select_file("HTML", "Wybierz LP_images.html")
    if not lp_html:
        return
    print(f"✓ Wybrano: {os.path.basename(lp_html)}\n")

    # [7/7] LP folder
    print("[7/7] Wybierz folder LP_images.files...")
    lp_images_dir = select_folder("Wybierz folder LP_images.files")
    if not lp_images_dir:
        return
    print(f"✓ Wybrano: {os.path.basename(lp_images_dir)}\n")

    # Przetwarzanie
    print("=" * 60)
    print(f"PRZETWARZANIE - Dostawca: {vendor_profile.NAME}")
    print("=" * 60)

    # Wykryj WSZYSTKIE systemy w CSV
    from csv_parser import get_positions_with_systems
    systems_map = get_positions_with_systems(csv_file)
    
    if not systems_map:
        # Fallback - stara logika
        system = validate_and_choose_system(csv_file, extract_system_from_csv)
        if not system:
            messagebox.showerror("Błąd", "Nie podano systemu.")
            return
        positions = get_positions_from_csv(csv_file)
        systems_map = {system: positions}
    
    print(f"\n📋 Wykryte systemy:")
    for sys_name, pos_list in systems_map.items():
        print(f"   {sys_name}: Poz. {', '.join(pos_list)}")

    # Wspólne ścieżki
    output_views = os.path.join(PROJECTS_IMAGES, project_name, "views")
    output_hardware = os.path.join(IMAGES_DB, vendor_key, "hardware")
    os.makedirs(output_views, exist_ok=True)
    os.makedirs(output_hardware, exist_ok=True)

    # KROK 1: Rzuty (wspólne dla wszystkich systemów)
    print("\n[KROK 1/4] Przetwarzanie rzutów...")
    prefix = get_project_prefix_from_met(met_file)
    all_positions = []
    for pos_list in systems_map.values():
        all_positions.extend(pos_list)
    print(f"✓ Znaleziono {len(all_positions)} pozycji łącznie")
    rk_images = get_rk_images_from_html(rk_html)
    print(f"✓ Znaleziono {len(rk_images)} obrazków w RK.html")
    rename_views(all_positions, rk_images, rk_images_dir, prefix, output_views)

    # KROK 2: Profile (osobny folder per system)
    print("\n[KROK 2/4] Przetwarzanie profili...")
    for sys_name in systems_map.keys():
        output_profiles = os.path.join(IMAGES_DB, vendor_key, "profiles", sys_name)
        os.makedirs(output_profiles, exist_ok=True)
        print(f"\n  📁 System: {sys_name} → {output_profiles}")
        rename_profiles_from_lp_html(
            lp_html, lp_images_dir, output_profiles, vendor_profile
        )

    # KROK 3: Okucia
    print("\n[KROK 3/4] Parsowanie okuć z CSV...")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)
    print(f"✓ Znaleziono {len(hardware_codes)} kodów okuć")

    # KROK 4: Kopiowanie okuć
    print("\n[KROK 4/4] Przetwarzanie okuć...")
    code_to_srcfile = build_hardware_mapping_from_lp_html(
        lp_html, lp_images_dir, vendor_profile
    )
    rename_hardware(hardware_codes, code_to_srcfile, lp_images_dir, output_hardware)

    # Audit
    log_audit("IMAGES_PROCESSED", {
        "project": project_name,
        "vendor": vendor_key,
        "systems": list(systems_map.keys()),
        "positions": len(all_positions),
        "hardware": len(hardware_codes),
    })

    # Podsumowanie
    systems_text = ", ".join(systems_map.keys())
    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)
    messagebox.showinfo(
        "Sukces!",
        f"Obrazki przetworzone!\n\n"
        f"Projekt: {project_name}\n"
        f"Systemy: {systems_text}\n"
        f"Pozycje: {len(all_positions)}\n"
        f"Okucia: {len(hardware_codes)}"
    )


if __name__ == "__main__":
    main()