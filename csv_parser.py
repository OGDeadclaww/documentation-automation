# csv_parser.py
"""
Parsowanie plików CSV z danymi projektowymi.
Wyciąga pozycje, system, kolory, okucia i profile dodatkowe.
"""
import os
import re
import csv

from config import POZ_LINE_RE, SECTION_RE
from vendors import clean


# ============================================
# WEWNĘTRZNE HELPERS
# ============================================

def _read_csv_rows(csv_path: str) -> list:
    """
    Wczytuje CSV z automatycznym wykrywaniem kodowania.
    Próbuje cp1250 (Windows PL), fallback na utf-8.
    
    Args:
        csv_path: Ścieżka do pliku CSV
    
    Returns:
        list: Lista wierszy (każdy wiersz to lista stringów)
    """
    for encoding in ("cp1250", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, errors="replace") as f:
                return list(csv.reader(f, delimiter=";"))
        except Exception:
            continue

    raise IOError(f"Nie można odczytać pliku: {csv_path}")


# ============================================
# POZYCJE
# ============================================

def get_positions_from_csv(csv_path: str) -> list:
    """
    Wyciąga numery pozycji z CSV.
    Szuka wierszy zawierających "Poz." i "MB-".
    
    Args:
        csv_path: Ścieżka do pliku CSV
    
    Returns:
        list: Lista numerów pozycji jako stringi (np. ["1", "2", "5"])
    
    Przykład wiersza CSV:
        "Poz. 1;;MB-78EI;Drzwi;..."
    """
    rows = _read_csv_rows(csv_path)
    positions = []

    for row in rows:
        line = ";".join(row)
        if "Poz." in line and "MB-" in line:
            match = POZ_LINE_RE.search(line)
            if match:
                positions.append(match.group(1))

    return positions


# ============================================
# SYSTEM PROFILI
# ============================================

def extract_system_from_csv(csv_path: str) -> str:
    """
    Wykrywa system profili z sekcji "System:" w CSV.
    
    Args:
        csv_path: Ścieżka do pliku CSV
    
    Returns:
        str: Nazwa systemu (np. "mb-78ei") lub None
    
    Szuka wzorca:
        Wiersz N:   "System:"
        Wiersz N+1: "MB-78EI HI"  →  "mb-78ei"
    """
    rows = _read_csv_rows(csv_path)

    for i, row in enumerate(rows):
        # Szukaj wiersza z "System:"
        if not any("System:" in str(cell) for cell in row):
            continue

        # Sprawdź następny wiersz
        if i + 1 >= len(rows):
            continue

        for cell in rows[i + 1]:
            cell_clean = clean(cell).upper()
            if not re.match(r"MB-\d+", cell_clean, re.IGNORECASE):
                continue

            # Usuń warianty (HI/SI/EI/HS) i normalizuj
            system = re.sub(
                r"\s*(HI|SI).*", "",
                cell_clean,
                flags=re.IGNORECASE
            ).strip().lower()
            system = re.sub(r"\s+", "", system)
            return system

    return None


# ============================================
# KOLORY
# ============================================

def extract_color_codes_from_csv(csv_path: str) -> list:
    """
    Wykrywa kody kolorów z wiersza "Kolor profili:" w CSV.
    
    Args:
        csv_path: Ścieżka do pliku CSV
    
    Returns:
        list: Lista kodów kolorów (np. ["B4", "I4", "D"])
    
    Obsługiwane formaty:
        "B4 [brązowy]"     → "B4"
        "I4 [czarny]"      → "I4"
        "D [srebrny]"      → "D"
    """
    rows = _read_csv_rows(csv_path)
    colors = []

    for row in rows:
        if not any("Kolor profili:" in str(cell) for cell in row):
            continue

        for cell in row:
            if not cell or "Kolor profili:" in cell:
                continue

            cell_upper = str(cell).upper()

            # Wyczyść opisy i znaki specjalne
            cell_clean = re.sub(
                r'[\^\\[\]\'"\(\)*]', " ", cell_upper
            )
            cell_clean = re.sub(
                r"\b(CZARNY|BRĄZOWY|ANODA|SREBRNY|SREBRNA|BIAŁY|"
                r"MAT|MATOWY|LAKIEROWANY|NIETYPOWY|STANDARD)\b",
                "",
                cell_clean,
            )
            cell_clean = cell_clean.strip()

            # Split po średniku (wiele kolorów w jednej komórce)
            segments = [s.strip() for s in cell_clean.split(";") if s.strip()]

            for segment in segments:
                # Litera + cyfry: B4, I4, E6
                for m in re.findall(r"\b([A-Z]\d{1,2})\b", segment):
                    if m not in ("X", "X1", "Y", "Y1"):
                        colors.append(m)

                # Pojedyncza litera: D, E, F, G, H
                for m in re.findall(r"(?:^|\s)([DBEFGH])(?:\s|$)", segment):
                    colors.append(m)

    # Usuń duplikaty zachowując kolejność
    seen = set()
    unique = [c for c in colors if not (c in seen or seen.add(c))]

    if unique:
        print(f"    🎨 Wykryte kody kolorów: {', '.join(unique)}")
    else:
        print(f"    ⚠️ Nie wykryto kodów kolorów")

    return unique


# ============================================
# OKUCIA / AKCESORIA
# ============================================

def parse_hardware_from_csv(csv_path: str, vendor_profile) -> dict:
    """
    Parsuje kody okuć i akcesoriów z CSV.
    X dodawany TYLKO gdy okucie ma kolor w swoim kodzie,
    NIE globalnie na podstawie koloru projektu.
    """
    rows = _read_csv_rows(csv_path)

    hardware_codes = {}
    current_pos = None
    current_section = None

    for i, row in enumerate(rows):
        r = [clean(c) for c in row]
        line = ";".join(r)

        mpos = POZ_LINE_RE.search(line)
        if mpos and "MB-" in line:
            current_pos = mpos.group(1)
            current_section = None
            continue

        if not current_pos:
            continue

        if r and r[0] and SECTION_RE.match(r[0]):
            sec = SECTION_RE.match(r[0]).group(1).capitalize()
            current_section = sec if sec in ("Akcesoria", "Okucia") else None
            continue

        if current_section not in ("Akcesoria", "Okucia"):
            continue

        # Parsuj BEZ wymuszania koloru - niech parser sam wykryje
        joined = " ".join(x for x in r if x)
        code_hw = vendor_profile.parse_hardware_code(joined, color_suffix=None)
        if not code_hw:
            continue

        desc = ""
        if i + 1 < len(rows):
            next_row = [clean(c) for c in rows[i + 1]]
            next_desc = next_row[0] if next_row else ""
            if next_desc and not vendor_profile.parse_hardware_code(
                next_desc, color_suffix=None
            ):
                desc = next_desc

        if code_hw not in hardware_codes:
            hardware_codes[code_hw] = {"desc": desc, "positions": set()}
        hardware_codes[code_hw]["positions"].add(current_pos)

    return hardware_codes


# ============================================
# PROFILE DODATKOWE
# ============================================

def extract_additional_profiles_from_csv(csv_path: str, vendor_profile) -> set:
    """
    Wyciąga profile z sekcji "Profile dodatkowe" w CSV.
    
    Args:
        csv_path: Ścieżka do pliku CSV
        vendor_profile: Klasa dostawcy (np. AluProfProfile)
    
    Returns:
        set: Zbiór kodów profili (np. {"K518139", "K120470"})
    """
    rows = _read_csv_rows(csv_path)
    profiles = set()
    in_section = False

    for row in rows:
        r = [clean(c) for c in row]
        line = ";".join(r)

        # Początek sekcji
        if re.search(r"Profile\s+dodatkowe", line, re.IGNORECASE):
            in_section = True
            continue

        # Koniec sekcji
        if in_section and r and r[0]:
            if re.match(
                r"^(Akcesoria|Okucia|Izolacyjność)", r[0], re.IGNORECASE
            ):
                in_section = False
                continue

        # Parsuj profile
        if in_section:
            for cell in r:
                code = vendor_profile.parse_profile_code(cell)
                if code:
                    profiles.add(code)

    return profiles