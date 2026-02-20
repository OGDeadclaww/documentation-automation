# debug_parser.py

# Importy z Twojego projektu
from gui import select_file
from parsers.vendors import get_vendor_by_key
from parsers.db_builder import build_product_db
from parsers.csv_parser import get_data_for_position


def run_debug():
    print("🐞 DEBUG MODE: Testowanie parsera CSV")

    # 1. Wybierz pliki (Klikając)
    lp_path = select_file("CSV", "Wybierz plik LP_dane.csv (ten z pozycjami)")
    if not lp_path:
        return

    zm_path = select_file("CSV", "Wybierz plik ZM_dane.csv (baza wiedzy)")
    # zm_path jest opcjonalne, ale zalecane dla Reynaers

    pos_num = input("Podaj numer pozycji do sprawdzenia (np. 1): ").strip()
    vendor_key = "reynaers"  # Lub input, jeśli chcesz zmieniać

    # 2. Budowanie bazy
    db = {}
    if zm_path:
        print("   🏗️  Budowanie bazy produktów...")
        db = build_product_db(zm_path)

    # 3. Uruchomienie parsera
    print(f"   🔍 Parsowanie pozycji {pos_num}...")
    vendor_cls = get_vendor_by_key(vendor_key)
    result = get_data_for_position(lp_path, pos_num, vendor_cls, product_db=db)

    # 4. Wyświetlenie wyników
    print("\n" + "=" * 60)
    print(f"WYNIKI DLA POZYCJI {pos_num}")
    print("=" * 60)

    print(f"\n📂 PROFILE ({len(result['profiles'])}):")
    print(f"{'KOD':<20} | {'ILOŚĆ':<10} | {'WYMIAR':<30} | OPIS")
    print("-" * 100)
    for p in result["profiles"]:
        print(
            f"{p['code']:<20} | {p['quantity']:<10} | {p['dimensions']:<30} | {p['desc']}"
        )

    print(f"\n🔩 OBRÓBKI/HARDWARE ({len(result['hardware'])}):")
    print("-" * 100)
    for h in result["hardware"]:
        print(f"{h['code']:<20} | {h['quantity']:<10} | {h['desc']}")

    print("\n✅ Koniec testu.")


if __name__ == "__main__":
    run_debug()
