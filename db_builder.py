# db_builder.py
from vendors import clean


def normalize_key(code):
    """
    Usuwa spacje z kodu, aby ułatwić dopasowanie między różnymi plikami CSV.
    Np. "008.3114.69 W:59 7047" -> "008.3114.69W:597047"
    """
    if not code:
        return ""
    return code.replace(" ", "").strip()


def build_product_db(zm_csv_path: str) -> dict:
    """
    Buduje bazę wiedzy o produktach na podstawie pliku Zamówienie Materiałów (ZM_dane.csv).
    Kluczem jest kod BEZ SPACJI.
    """
    db = {}
    current_section = None  # 'profile', 'hardware'

    SECTION_MAP = {
        "Profile": "profile",
        "Akcesoria": "hardware",
        "Uszczelki": "hardware",
        "Okucia": "hardware",
    }

    # Wczytywanie z detekcją kodowania
    lines = []
    for encoding in ("cp1250", "utf-8"):
        try:
            with open(zm_csv_path, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()
            break
        except Exception:
            continue

    if not lines:
        print("❌ Nie udało się wczytać pliku ZM.")
        return {}

    for line in lines:
        line = line.strip()

        # 1. Wykrywanie Sekcji (szukamy słów kluczowych w surowej linii)
        found_section = False
        for key, val in SECTION_MAP.items():
            # Sekcje w ZM są specyficzne: ;Profile;;;;;
            if f";{key};" in line:
                current_section = val
                found_section = True
                break

        if found_section or not current_section:
            continue

        # 2. Parsowanie
        parts = line.split(";")
        if len(parts) < 3:
            continue

        # Kod w kolumnie 1, Opis w 2 (indeksy 0-based: 0=puste, 1=Kod)
        raw_code = clean(parts[1])
        desc = clean(parts[2])
        unit = clean(parts[5]) if len(parts) > 5 else ""

        # Normalizacja klucza
        key = normalize_key(raw_code)

        # Walidacja
        if len(key) < 3 or "Kodelementu" in key:
            continue

        db[key] = {
            "original_code": raw_code,
            "type": current_section,
            "desc": desc,
            "unit": unit,
        }

    print(f"✅ Zbudowano bazę produktów: {len(db)} elementów.")
    return db
