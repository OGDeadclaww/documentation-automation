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

    system = validate_and_choose_system(csv_file, extract_system_from_csv)
    if not system:
        messagebox.showerror("Błąd", "Nie podano systemu - przerywam.")
        return

    # Ścieżki wyjściowe
    output_views = os.path.join(PROJECTS_IMAGES, project_name, "views")
    output_profiles = os.path.join(IMAGES_DB, vendor_key, "profiles", system)
    output_hardware = os.path.join(IMAGES_DB, vendor_key, "hardware")

    os.makedirs(output_views, exist_ok=True)
    os.makedirs(output_profiles, exist_ok=True)
    os.makedirs(output_hardware, exist_ok=True)

    print(f"\n📁 Zapisuję do:")
    print(f"  Views:    {output_views}")
    print(f"  Profiles: {output_profiles}")
    print(f"  Hardware: {output_hardware}\n")

    # KROK 1: Rzuty
    print("[KROK 1/4] Przetwarzanie rzutów...")
    prefix = get_project_prefix_from_met(met_file)
    positions = get_positions_from_csv(csv_file)
    print(f"✓ Znaleziono {len(positions)} pozycji")
    rk_images = get_rk_images_from_html(rk_html)
    print(f"✓ Znaleziono {len(rk_images)} obrazków w RK.html")
    rename_views(positions, rk_images, rk_images_dir, prefix, output_views)

    # KROK 2: Profile
    print("\n[KROK 2/4] Przetwarzanie profili...")
    rename_profiles_from_lp_html(lp_html, lp_images_dir, output_profiles, vendor_profile)
    additional = extract_additional_profiles_from_csv(csv_file, vendor_profile)
    if additional:
        print(f"⚠️ Profile dodatkowe w CSV: {', '.join(sorted(additional))}")

    # KROK 3: Parsowanie okuć
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
        "system": system,
        "positions": len(positions),
        "hardware": len(hardware_codes),
    })

    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)

    messagebox.showinfo(
        "Sukces!",
        f"Obrazki przetworzone!\n\n"
        f"Projekt: {project_name}\n"
        f"System: {system}\n"
        f"Pozycje: {len(positions)}\n"
        f"Okucia: {len(hardware_codes)}"
    )


if __name__ == "__main__":
    main()