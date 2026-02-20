# csv_parser.py
import re
import csv
from parsers.vendors import clean
from parsers.db_builder import normalize_key

POZ_LINE_RE = re.compile(r"Poz\.\s*(\d+)")
SYSTEM_KEYWORDS = ["MB-", "MasterLine", "CS-", "CP-", "SlimLine", "Hi-Finity"]

# ============================================
# POMOCNICZE
# ============================================


def _read_csv_rows(csv_path: str) -> list:
    for encoding in ("cp1250", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, errors="replace") as f:
                return list(csv.reader(f, delimiter=";"))
        except Exception:
            continue
    raise IOError(f"Nie można odczytać pliku: {csv_path}")


def _extract_dims_reynaers(row, idx_map):
    """Specyficzna ekstrakcja wymiarów dla Reynaers (szuka w całym wierszu)."""
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

    # Walidacja wstępna
    if dim and not any(c.isdigit() for c in dim):
        dim = ""
    if qty and not any(c.isdigit() for c in qty):
        qty = ""

    # Heurystyka (gdy kolumny się przesuną)
    if not qty:
        for val in row:
            if "szt" in val.lower():
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
# STRATEGIA 1: PARSER REYNAERS (Data-Driven)
# ============================================


def _parse_reynaers(rows, target_pos, product_db):
    data = {"profiles": [], "hardware": []}
    is_target_pos = False

    active_profile_code = None
    active_profile_desc = ""
    active_item_type = None
    col_idx = {"qty": None, "dim": None, "loc": None}

    IGNORE_SECTIONS = [
        "akcesoria",
        "okucia",
        "profile",
        "profile dodatkowe",
        "uszczelki",
        "kod:",
        "rysunek",
    ]
    GENERIC_DESCS = ["akcesoria", "okucia", "profile", "uszczelki"]

    for row in rows:
        line = ";".join(row)

        # 1. Pozycja
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

        # 2. Nagłówki
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

        # 3. Szukanie Kodu
        new_code = None
        for i in range(min(len(r), 3)):
            cell = r[i].strip()
            if not cell:
                continue

            # --- FILTRY REYNAERS ---
            if not any(c.isdigit() for c in cell):
                continue
            if not cell[0].isdigit():
                continue  # Musi startować od cyfry
            if len(cell) > 20 and " " in cell:  # Długie opisy
                if any(c in "ąęśżźćńółĄĘŚŻŹĆŃÓŁ" for c in cell):
                    continue
                if ")" in cell[:3]:
                    continue
                if "." not in cell[:10]:
                    continue

            clean_key = normalize_key(cell)
            if product_db and clean_key in product_db:
                new_code = cell
                break
            elif "." in cell and len(cell) > 5:
                if cell[3] == ".":
                    new_code = cell
                    break

        # --- A: Nowy Element ---
        if new_code:
            active_profile_code = new_code
            clean_key = normalize_key(new_code)

            if product_db and clean_key in product_db:
                active_item_type = product_db[clean_key]["type"]
                active_profile_desc = product_db[clean_key]["desc"]
            else:
                # Heurystyka typu
                if new_code.startswith(("008", "030", "108", "408", "508")):
                    active_item_type = "profile"
                else:
                    active_item_type = "hardware"
                active_profile_desc = ""

            qty, dim, loc = _extract_dims_reynaers(r, col_idx)

            # Inline opis (szukanie tekstu w tym samym wierszu)
            potential_inline_desc = ""
            for i, val in enumerate(r):
                if val == new_code or val == qty or val == dim or val == loc:
                    continue
                if len(val) > 3 and not any(c.isdigit() for c in val):
                    if val.lower() not in IGNORE_SECTIONS:
                        potential_inline_desc = val
                        break

            if potential_inline_desc:
                if (
                    not active_profile_desc
                    or active_profile_desc.lower() in GENERIC_DESCS
                ):
                    active_profile_desc = potential_inline_desc

            # Fix wymiaru (czy nie jest opisem?)
            if dim:
                stripped = re.sub(r"[0-9.,\s()';:xXmM/-]", "", dim)
                if len(stripped) > 2:
                    if not active_profile_desc:
                        active_profile_desc = dim
                    dim = ""

            should_add = False
            if active_item_type == "hardware":
                should_add = True
            elif active_item_type == "profile" and (qty or dim):
                should_add = True

            if should_add:
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

        # --- B: Kontynuacja (Kolejny wiersz) ---
        elif active_profile_code:
            qty, dim, loc = _extract_dims_reynaers(r, col_idx)

            # Sprawdzenie czy wymiar to nie opis
            is_dim_actually_desc = False
            if dim:
                if not any(c.isdigit() for c in dim):
                    is_dim_actually_desc = True
                else:
                    stripped = re.sub(r"[0-9.,\s()';:xXmM/-]", "", dim)
                    if len(stripped) > 2:
                        is_dim_actually_desc = True

            if is_dim_actually_desc:
                dim = ""

            # Szukanie opisu w wierszu bez danych
            potential_desc = dim if is_dim_actually_desc else ""
            if not potential_desc and not qty and not dim:
                for i in range(min(len(r), 2)):
                    cell = r[i].strip()
                    if cell and len(cell) > 3:
                        if cell.lower() in IGNORE_SECTIONS:
                            continue
                        potential_desc = cell
                        break

            if potential_desc:
                if (
                    not active_profile_desc
                    or active_profile_desc.lower() in GENERIC_DESCS
                ):
                    active_profile_desc = potential_desc
                    # Update ostatniego wpisu
                    target_list = (
                        data["profiles"]
                        if active_item_type == "profile"
                        else data["hardware"]
                    )
                    if target_list:
                        target_list[-1]["desc"] = active_profile_desc

            # Walidacja danych do dodania
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
# STRATEGIA 2: PARSER ALUPROF (Regex)
# ============================================


def _parse_aluprof(rows, target_pos, vendor_profile):
    data = {"profiles": [], "hardware": []}
    is_target_pos = False

    for row in rows:
        line = ";".join(row)

        # 1. Pozycja
        if "Poz." in line:
            m = POZ_LINE_RE.search(line)
            if m:
                found_pos = m.group(1)
                is_target_pos = str(found_pos) == target_pos
            continue
        if not is_target_pos:
            continue

        r = [clean(c) for c in row]
        if not any(r):
            continue

        # Skanujemy pierwsze kolumny
        for i in range(min(len(r), 3)):
            cell = r[i].strip()
            if not cell:
                continue

            # --- 1. Czy to Profil? (K... lub regex) ---
            prof_code = vendor_profile.parse_profile_code(cell)
            if prof_code:
                # Znaleziono profil (prof_code ma już X jeśli trzeba)
                desc = r[i + 1] if len(r) > i + 1 else "Profil"
                qty = ""
                dims = ""
                # Prosta heurystyka ilości (szukamy 'szt' w prawo)
                for val in r[i + 1 :]:
                    if "szt" in val.lower():
                        qty = val
                        break
                # Wymiar (często po ilości)
                # (Tutaj upraszczamy, bo Aluprof jest bardziej liniowy)

                data["profiles"].append(
                    {
                        "code": prof_code,  # Tu już jest np. K518102X
                        "desc": desc,
                        "quantity": qty,
                        "dimensions": dims,
                        "location": "—",
                        "type": "profile",
                    }
                )
                break

            # --- 2. Czy to Hardware? ---
            hw_code = vendor_profile.parse_hardware_code(cell)
            if hw_code:
                desc = r[i + 1] if len(r) > i + 1 else "Okucie"
                qty = ""
                for val in r[i + 1 :]:
                    if "szt" in val.lower():
                        qty = val
                        break

                data["hardware"].append(
                    {
                        "code": hw_code,
                        "desc": desc,
                        "quantity": qty,
                        "dimensions": "",
                        "location": "—",
                        "type": "hardware",
                    }
                )
                break

    return data


# ============================================
# GŁÓWNY DYSPOLITER (FASADA)
# ============================================


def get_data_for_position(
    csv_path: str, position_number: str, vendor_profile, product_db=None
) -> dict:
    rows = _read_csv_rows(csv_path)

    if vendor_profile.KEY == "reynaers":
        return _parse_reynaers(rows, str(position_number), product_db)
    else:
        # Aliplast, Aluprof, Generic
        return _parse_aluprof(rows, str(position_number), vendor_profile)


# ============================================
# FUNKCJE PUBLICZNE (Dla rename_images.py i innych)
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
    return None  # Uproszczone (używamy get_positions_with_systems)


def extract_color_codes_from_csv(csv_path: str) -> list:
    # (Zachowana logika wyciągania kolorów dla GUI)
    rows = _read_csv_rows(csv_path)
    colors = []
    for row in rows:
        if not any("Kolor profili:" in str(cell) for cell in row):
            continue
        for cell in row:
            if not cell or "Kolor profili:" in cell:
                continue
            # cell_clean = re.sub(r'[\^\\[\]\'"\(\)*]', " ", str(cell).upper()).strip()
            # ... (uproszczona ekstrakcja, można wkleić starą jeśli potrzebna)
    return colors


def parse_hardware_from_csv(csv_path: str, vendor_profile) -> dict:
    """
    Używana przez rename_images.py.
    Agreguje hardware ze wszystkich pozycji używając get_data_for_position.
    """
    rows = _read_csv_rows(csv_path)
    positions = set()
    for row in rows:
        line = ";".join(row)
        m = POZ_LINE_RE.search(line)
        if m:
            positions.add(m.group(1))

    hardware_codes = {}

    for pos in positions:
        # Pobieramy dane (bez product_db dla rename_images, więc działa w trybie heurystycznym)
        data = get_data_for_position(csv_path, pos, vendor_profile, product_db=None)

        for hw in data["hardware"]:
            raw_code = hw["code"]
            desc = hw["desc"]

            # Normalizacja XX (żeby pasowało do plików)
            normalized_code = vendor_profile.parse_hardware_code(raw_code)
            code = normalized_code if normalized_code else raw_code

            if code not in hardware_codes:
                hardware_codes[code] = {"desc": desc, "positions": set()}

            hardware_codes[code]["positions"].add(pos)

    return hardware_codes


def get_profile_codes_by_system(csv_path: str, vendor_profile) -> dict:
    """
    Używana przez rename_images.py.
    Zwraca kody profili (z X/XX) pogrupowane wg systemu.
    """
    systems_map = get_positions_with_systems(csv_path)
    profiles_by_sys = {}

    for sys_name, positions in systems_map.items():
        if sys_name not in profiles_by_sys:
            profiles_by_sys[sys_name] = set()

        for pos in positions:
            data = get_data_for_position(csv_path, pos, vendor_profile, product_db=None)

            for prof in data["profiles"]:
                # Kod z data["profiles"] jest już przetworzony przez parse_profile_code
                # w przypadku Aluprof (K...X), więc bierzemy go wprost.
                profiles_by_sys[sys_name].add(prof["code"])

    return profiles_by_sys
