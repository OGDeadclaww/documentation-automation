# csv_parser.py
import re
import csv
from vendors import clean

# Zaimportuj normalize_key z db_builder, aby logika była spójna
from db_builder import normalize_key

POZ_LINE_RE = re.compile(r"Poz\.\s*(\d+)")
SYSTEM_KEYWORDS = ["MB-", "MasterLine", "CS-", "CP-", "SlimLine", "Hi-Finity"]

# ============================================
# WEWNĘTRZNE HELPERS
# ============================================


def _read_csv_rows(csv_path: str) -> list:
    for encoding in ("cp1250", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, errors="replace") as f:
                return list(csv.reader(f, delimiter=";"))
        except Exception:
            continue
    raise IOError(f"Nie można odczytać pliku: {csv_path}")


def _extract_dims(row, idx_map):
    qty = (
        row[idx_map["qty"]]
        if idx_map["qty"] is not None and idx_map["qty"] < len(row)
        else ""
    )
    dim = (
        row[idx_map["dim"]]
        if idx_map["dim"] is not None and idx_map["dim"] < len(row)
        else ""
    )
    loc = (
        row[idx_map["loc"]]
        if idx_map["loc"] is not None and idx_map["loc"] < len(row)
        else ""
    )

    if dim and not any(c.isdigit() for c in dim):
        dim = ""
    if qty and not any(c.isdigit() for c in qty):
        qty = ""

    if not qty:
        for val in row:
            v = val.lower()
            if "szt" in v:
                qty = val
                break

    if not dim:
        for val in row:
            v = val.lower()
            if v == qty.lower():
                continue
            if not any(c.isdigit() for c in v):
                continue
            if (
                "mm" in v
                or (v.replace(".", "").isdigit() and len(v) > 3)
                or ("(" in v and ")" in v)
            ):
                dim = val
                break

    return qty, dim, loc


# ============================================
# GŁÓWNY PARSER DANYCH POZYCJI
# ============================================


def get_data_for_position(
    csv_path: str, position_number: str, vendor_profile, product_db=None
) -> dict:
    rows = _read_csv_rows(csv_path)
    data = {"profiles": [], "hardware": []}
    target_pos = str(position_number).strip()
    is_target_pos = False

    active_profile_code = None
    active_profile_desc = ""
    active_item_type = None
    col_idx = {"qty": None, "dim": None, "loc": None}

    for row in rows:
        line = ";".join(row)

        if "Poz." in line:
            m = POZ_LINE_RE.search(line)
            if m:
                found_pos = m.group(1)
                is_target_pos = str(found_pos) == target_pos
                active_profile_code = None
                col_idx = {"qty": None, "dim": None, "loc": None}
            continue
        if not is_target_pos:
            continue

        r = [clean(c) for c in row]
        if not any(r):
            continue

        if "Ilo" in line and "Wymiar" in line:
            for i, col in enumerate(r):
                cl = col.lower()
                if "ilo" in cl:
                    col_idx["qty"] = i
                elif "wymiar" in cl:
                    col_idx["dim"] = i
                elif "ołożenie" in cl or "olozenie" in cl:
                    col_idx["loc"] = i
            continue

        new_code = None

        for i in range(min(len(r), 3)):
            cell = r[i].strip()
            if not cell:
                continue
            if not any(c.isdigit() for c in cell):
                continue
            if len(cell) > 20 and " " in cell:
                if any(c in "ąęśżźćńółĄĘŚŻŹĆŃÓŁ" for c in cell):
                    continue
                if ")" in cell[:3]:
                    continue
                if "." not in cell[:10]:
                    continue

            # --- NORMALIZACJA KLUCZA ---
            clean_key = normalize_key(cell)

            # A. Baza Wiedzy (szukamy po czystym kluczu)
            if product_db and clean_key in product_db:
                new_code = cell  # Zachowujemy oryginał z LP do wyświetlania
                break

            # B. Heurystyka (Regex)
            elif "." in cell and len(cell) > 5:
                if cell[3] == ".":
                    new_code = cell
                    break

        # --- A: Nowy Element ---
        if new_code:
            active_profile_code = new_code
            clean_key = normalize_key(new_code)

            # Pobieranie typu i opisu z bazy
            if product_db and clean_key in product_db:
                active_item_type = product_db[clean_key]["type"]
                active_profile_desc = product_db[clean_key]["desc"]
            else:
                if new_code.startswith(("008", "030", "108", "408", "508")):
                    active_item_type = "profile"
                else:
                    active_item_type = "hardware"
                active_profile_desc = ""

            qty, dim, loc = _extract_dims(r, col_idx)

            should_add = False
            if active_item_type == "hardware":
                should_add = True
            elif active_item_type == "profile" and (qty or dim):
                should_add = True

            if should_add:
                if dim:
                    stripped = re.sub(r"[0-9.,\s()';:xXmM-]", "", dim)
                    if len(stripped) > 1:
                        dim = ""

                entry = {
                    "code": active_profile_code,
                    "desc": active_profile_desc,
                    "quantity": qty,
                    "dimensions": dim,
                    "location": loc,
                    "type": active_item_type,
                }
                if active_item_type == "profile":
                    data["profiles"].append(entry)
                else:
                    data["hardware"].append(entry)

        # --- B: Kontynuacja ---
        elif active_profile_code:
            qty, dim, loc = _extract_dims(r, col_idx)

            is_valid_dim = False
            if dim:
                stripped = re.sub(r"[0-9.,\s()';:xXmM-]", "", dim)
                if len(stripped) < 2:
                    is_valid_dim = True

            is_valid_qty = qty and any(c.isdigit() for c in qty)

            if is_valid_qty or is_valid_dim:
                entry = {
                    "code": active_profile_code,
                    "desc": active_profile_desc,
                    "quantity": qty,
                    "dimensions": dim if is_valid_dim else "",
                    "location": loc,
                    "type": active_item_type,
                }
                if active_item_type == "profile":
                    data["profiles"].append(entry)
                else:
                    data["hardware"].append(entry)

    return data


# ============================================
# STARE FUNKCJE (bez zmian, tylko lista)
# ============================================
def get_positions_from_csv(csv_path: str) -> list:
    rows = _read_csv_rows(csv_path)
    positions = []
    for row in rows:
        line = ";".join(row)
        if "Poz." in line and any(kw in line for kw in SYSTEM_KEYWORDS):
            match = POZ_LINE_RE.search(line)
            if match:
                positions.append(match.group(1))
    return positions


def get_positions_with_systems(csv_path: str) -> dict:
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
    line_upper = line.upper()
    m = re.search(r"MASTERLINE\s*(\d+)", line_upper)
    if m:
        return f"masterline-{m.group(1)}"
    m = re.search(r"(CS|CP)-?\s*(\d+)", line_upper)
    if m:
        return f"{m.group(1).lower()}-{m.group(2)}"
    m = re.search(r"(MB-\d+\w*)", line_upper)
    if m:
        s = re.sub(r"\s+(HI|SI)\b.*", "", m.group(1), flags=re.IGNORECASE)
        return s.strip().lower()
    return None


def extract_system_from_csv(csv_path: str) -> str:
    return None


def extract_color_codes_from_csv(csv_path: str) -> list:
    return []  # Uproszczone


def parse_hardware_from_csv(csv_path: str, vendor_profile) -> dict:
    return {}  # Uproszczone, nieużywane w nowym generatorze


def get_profile_codes_by_system(csv_path: str, vendor_profile) -> dict:
    return {}  # Zachowane
