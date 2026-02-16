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

POZ_LINE_RE_REYNAERS = re.compile(r"Poz\.\s*(\d+)")
SYSTEM_KEYWORDS = ["MB-", "MasterLine", "CS-", "CP-", "SlimLine", "Hi-Finity"]

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
    Obsługuje Aluprof (MB-) i Reynaers (MasterLine, CS-77, etc.)
    """
    rows = _read_csv_rows(csv_path)
    positions = []

    for row in rows:
        line = ";".join(row)
        if "Poz." not in line:
            continue
        # Sprawdź czy linia zawiera jakikolwiek znany system
        has_system = any(kw in line for kw in SYSTEM_KEYWORDS)
        if has_system:
            match = POZ_LINE_RE.search(line)
            if match:
                positions.append(match.group(1))

    return positions

def get_positions_with_systems(csv_path: str) -> dict:
    """
    Wyciąga pozycje pogrupowane wg systemu.
    
    Returns:
        dict: {system: [pozycje]}
        
    Przykład:
        {
            "masterline-8": ["1", "5", "6"],
            "cs-77": ["2", "3", "4"]
        }
    """
    rows = _read_csv_rows(csv_path)
    systems = {}
    
    for row in rows:
        line = ";".join(row)
        if "Poz." not in line:
            continue
        
        match = POZ_LINE_RE.search(line)
        if not match:
            continue
        
        pos = match.group(1)
        system = _detect_system_in_line(line)
        
        if system:
            if system not in systems:
                systems[system] = []
            systems[system].append(pos)
    
    return systems


def _detect_system_in_line(line: str) -> str:
    """Wykrywa system z linii pozycji."""
    line_upper = line.upper()
    
    # MasterLine8
    m = re.search(r"MASTERLINE\s*(\d+)", line_upper)
    if m:
        return f"masterline-{m.group(1)}"
    
    # CS-77 BP, CS-77, CS-86 etc.
    m = re.search(r"(CS|CP)-?\s*(\d+)", line_upper)
    if m:
        return f"{m.group(1).lower()}-{m.group(2)}"
    
    # MB-78EI etc.
    m = re.search(r"(MB-\d+\w*)", line_upper)
    if m:
        system = re.sub(r"\s+(HI|SI)\b.*", "", m.group(1), flags=re.IGNORECASE)
        return system.strip().lower()
    
    # SlimLine, Hi-Finity
    m = re.search(r"(SLIMLINE|HI-FINITY)\s*(\d*)", line_upper)
    if m:
        name = m.group(1).lower()
        num = m.group(2)
        return f"{name}-{num}" if num else name
    
    return None


# ============================================
# SYSTEM PROFILI
# ============================================

def extract_system_from_csv(csv_path: str) -> str:
    """
    Wykrywa system profili z CSV.
    Obsługuje Aluprof (MB-XX) i Reynaers (MasterLine8, CS-77, etc.)
    """
    rows = _read_csv_rows(csv_path)

    for i, row in enumerate(rows):
        if not any("System:" in str(cell) for cell in row):
            continue

        if i + 1 >= len(rows):
            continue

        for cell in rows[i + 1]:
            cell_clean = clean(cell).upper()

            # Aluprof: MB-78EI HI → mb-78ei
            if re.match(r"MB-\d+", cell_clean):
                system = re.sub(
                    r"\s+(HI|SI)\b.*", "",
                    cell_clean, flags=re.IGNORECASE
                ).strip().lower()
                system = re.sub(r"\s+", "", system)
                return system

            # Reynaers: MasterLine8 HI+ → masterline-8
            m = re.match(r"(MASTERLINE)\s*(\d+)", cell_clean)
            if m:
                system = f"masterline-{m.group(2)}"
                # Usuń warianty HI+/SI
                return system.lower()

            # Reynaers: CS-77 BP → cs-77
            m = re.match(r"(CS|CP|SLIMLINE|HI-FINITY)-?\s*(\d+)", cell_clean)
            if m:
                system = f"{m.group(1).lower()}-{m.group(2)}"
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
    Parsuje kody okuć z CSV.
    Obsługuje Aluprof (MB-) i Reynaers (MasterLine, CS-77, etc.)
    """
    rows = _read_csv_rows(csv_path)

    hardware_codes = {}
    current_pos = None
    current_section = None

    for i, row in enumerate(rows):
        r = [clean(c) for c in row]
        line = ";".join(r)

        # Nowa pozycja - obsłuż oba formaty
        mpos = POZ_LINE_RE.search(line)
        if mpos:
            has_system = any(kw in line for kw in SYSTEM_KEYWORDS)
            if has_system:
                current_pos = mpos.group(1)
                current_section = None
                continue

        if not current_pos:
            continue

        # Nowa sekcja
        if r and r[0] and SECTION_RE.match(r[0]):
            sec = SECTION_RE.match(r[0]).group(1).capitalize()
            current_section = sec if sec in ("Akcesoria", "Okucia") else None
            continue

        if current_section not in ("Akcesoria", "Okucia"):
            continue

        # Parsuj kod
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