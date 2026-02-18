# db_builder.py
from vendors import clean


def build_product_db(zm_csv_path: str) -> dict:
    """
    Buduje bazę wiedzy o produktach na podstawie pliku Zamówienie Materiałów (ZM_dane.csv).
    Rozpoznaje sekcje: Profile, Akcesoria, Uszczelki, Okucia.
    Zwraca słownik:
    {
        "KOD_PRODUKTU": {
            "type": "profile" | "hardware",
            "desc": "Opis z pliku ZM",
            "unit": "szt" | "m" | "sztanga"
        }
    }
    """
    db = {}
    current_section = None  # 'PROFILE', 'HARDWARE'

    # Mapowanie nagłówków sekcji w pliku ZM na nasze typy
    SECTION_MAP = {
        ";Profile;;;;;": "profile",
        ";Akcesoria;;;;;": "hardware",
        ";Uszczelki;;;;;": "hardware",  # Uszczelki traktujemy jako hardware
        ";Okucia;;;;;": "hardware",
    }

    try:
        # Kodowanie cp1250 dla polskich znaków (Windows)
        with open(zm_csv_path, "r", encoding="cp1250", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        # Fallback na utf-8
        with open(zm_csv_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

    for line in lines:
        line = line.strip()

        # 1. Wykrywanie Sekcji
        # Sprawdzamy czy linia zawiera klucz sekcji (np. ";Profile;;;;;")
        found_section = False
        for key, val in SECTION_MAP.items():
            if key in line:
                current_section = val
                found_section = True
                break

        if found_section:
            continue

        if not current_section:
            continue

        # 2. Parsowanie Danych
        # Format ZM: ;Kod;Opis;;;Jednostka;...
        # Split po średniku
        parts = line.split(";")
        if len(parts) < 3:
            continue

        # Kod jest zazwyczaj w kolumnie 1 (indeks 1), bo kolumna 0 jest pusta (;)
        code = clean(parts[1])
        desc = clean(parts[2])
        unit = clean(parts[5]) if len(parts) > 5 else ""

        # Walidacja kodu (musi mieć min. 3 znaki i nie być nagłówkiem "Kod elementu")
        if len(code) < 3 or "Kod elementu" in code:
            continue

        # Zapisz do bazy
        db[code] = {"type": current_section, "desc": desc, "unit": unit}

    print(f"✅ Zbudowano bazę produktów: {len(db)} elementów.")
    return db
