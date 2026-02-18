from vendors import clean


def normalize_key(code):
    """
    Usuwa spacje i białe znaki.
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
    # Kolejność: utf-8 (bo czasem excel tak zapisuje), potem cp1250 (windows PL)
    encodings = ["utf-8", "cp1250", "latin2"]

    for encoding in encodings:
        try:
            with open(zm_csv_path, "r", encoding=encoding) as f:
                lines = f.readlines()
            # Test czy polskie znaki są ok (np. 'Ilość')
            sample = "".join(lines[:10])
            if "Ilo" in sample and "" not in sample:
                break
        except Exception:
            continue

    if not lines:
        print("❌ Nie udało się wczytać pliku ZM (błąd kodowania).")
        return {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. Wykrywanie Sekcji
        # Szukamy "czystych" słów kluczowych w linii
        # Format w ZM: ;Profile;;;;;
        parts = line.split(";")
        if len(parts) > 1 and parts[1] in SECTION_MAP:
            current_section = SECTION_MAP[parts[1]]
            continue

        if not current_section:
            continue

        # 2. Parsowanie Danych
        # Format ZM: ;Kod;Opis;;;Jednostka;...
        if len(parts) < 3:
            continue

        # Kod w kolumnie 1, Opis w 2
        raw_code = clean(parts[1])
        desc = clean(parts[2])
        unit = clean(parts[5]) if len(parts) > 5 else ""

        # Normalizacja klucza
        key = normalize_key(raw_code)

        # Walidacja
        if len(key) < 3 or "Kodelementu" in key or "Razem:" in key:
            continue

        db[key] = {
            "original_code": raw_code,
            "type": current_section,
            "desc": desc,
            "unit": unit,
        }

    print(f"✅ Zbudowano bazę produktów: {len(db)} elementów.")
    return db
