"""
Moduł odpowiedzialny za parsowanie plików CSV z różnych programów (LogiKal, ReynaPro).
"""

import csv
import re
from collections import OrderedDict

from parsers.db_builder import normalize_key
from parsers.vendors import clean

POZ_LINE_RE = re.compile(r"Poz\.\s*(\d+)", re.IGNORECASE)
SYSTEM_KEYWORDS = ["MB-", "MasterLine", "CS-", "CP-", "SlimLine", "Hi-Finity"]
CODE_ROW_RE = re.compile(r"^K\d{2}\s+\d{4}\b", re.IGNORECASE)

# BUG FIX #4: Wzorzec rozpoznający stopki stron CSV
# Stopka ma postać: NazwaProjektu (N_strony) w pierwszej kolumnie
PAGE_FOOTER_RE = re.compile(r"^[A-Za-z0-9_\- ]+\s*\(\d+\)\s*$")

# BUG FIX #5: Słowa kluczowe identyfikujące okucia bez kodów Aluprof
# (polskie znaki powodują że regex [A-Z0-9]+ ich nie łapie)
SPECIAL_HARDWARE_KEYWORDS = [
    "kołek rozporowy",
    "wkręt do betonu",
    "wkret do betonu",
    "kołek",
    "wkręt",
]

# ============================================
# DETEKCJA FORMATU I ODCZYT
# ============================================


def _detect_format(filepath: str) -> str:
    try:
        with open(filepath, encoding="utf-16") as f:
            header = f.read(1000)
    except UnicodeError:
        try:
            with open(filepath, encoding="windows-1250") as f:
                header = f.read(1000)
        except Exception:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                header = f.read(1000)

    if "MB-CAD" in header or "LogiKal" in header or ";LISTA PRODUKCYJNA" in header:
        return "logikal"
    return "reynaers"


def _read_csv_rows(csv_path: str) -> list:
    for encoding in ("cp1250", "utf-8"):
        try:
            with open(csv_path, encoding=encoding, errors="replace") as f:
                return list(csv.reader(f, delimiter=";"))
        except Exception:
            continue
    raise OSError(f"Nie można odczytać pliku: {csv_path}")


def _read_rows_logikal(filepath: str) -> list[list[str]]:
    try:
        with open(filepath, encoding="utf-16") as f:
            return list(csv.reader(f, delimiter=";"))
    except UnicodeError:
        try:
            with open(filepath, encoding="windows-1250") as f:
                return list(csv.reader(f, delimiter=";"))
        except Exception:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                return list(csv.reader(f, delimiter=";"))


# ============================================
# ROUTERY GŁÓWNE
# ============================================


def get_positions_with_systems(csv_path: str, *args, **kwargs) -> dict:
    fmt = _detect_format(csv_path)

    if fmt == "logikal":
        rows = _read_rows_logikal(csv_path)
        sys_map = {}
        for row in rows:
            if not row:
                continue
            line = ";".join(row).replace('"', "").replace("'", "")
            m = re.search(
                r"Poz\.\s*(\d+)\s+([A-Za-z0-9\- ]+?)\s+(Drzwi|Witryn|Okno|cianka|Ścianka|\()",
                line,
                re.IGNORECASE,
            )
            if m:
                pos_num = m.group(1)
                sys_name = m.group(2).strip()
                if sys_name not in sys_map:
                    sys_map[sys_name] = []
                if pos_num not in sys_map[sys_name]:
                    sys_map[sys_name].append(pos_num)
        return sys_map
    else:
        return _get_reynaers_positions(csv_path)


def get_data_for_position(
    csv_path: str, position_number: str, vendor_profile, product_db=None, *args, **kwargs
) -> dict:
    fmt = _detect_format(csv_path)

    if fmt == "logikal":
        rows = _read_rows_logikal(csv_path)
        return _parse_logikal_position(rows, str(position_number), vendor_profile)
    else:
        return _get_reynaers_data(csv_path, str(position_number), vendor_profile, product_db)


# ============================================
# BUG FIX #4: Detektor stopek stron CSV
# ============================================


def _is_page_footer(row: list[str], first_col: str) -> bool:
    """
    Rozpoznaje stopkę strony w pliku CSV LogiKal.

    Stopka ma charakterystyczną postać:
      Col[0]: "NazwaProjektu (N)"   — np. "Szpital_etap_8 (26)"
    Cecha: pierwsza kolumna pasuje do wzorca NazwaProjektu (N)
    i wiersz ma <= 6 niepustych kolumn (stopki mają dużo pustych pól).
    """
    if not first_col:
        return False

    if PAGE_FOOTER_RE.search(first_col):
        non_empty = [c for c in row if c.strip()]
        # Stopka ma najczęściej <= 6 niepustych kolumn na ~20+ kolumnach
        if len(non_empty) <= 6:
            return True

    return False


# ============================================
# BUG FIX #5: Detektor specjalnych okuć bez kodów Aluprof
# ============================================


def _is_special_hardware_keyword(text: str) -> bool:
    """
    Sprawdza czy tekst to specjalne okucie bez kodu Aluprof
    (np. 'Kołek rozporowy', 'Wkręt do betonu').
    Polskie znaki powodują że standardowy regex [A-Z0-9]+ ich nie łapie.
    """
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in SPECIAL_HARDWARE_KEYWORDS)


def _is_desc_with_inline_codes(text: str) -> bool:
    """Rozpoznaje format: 'Opis (KOD + KOD)' — opis z kodami w nawiasie, NIE osobny rekord."""
    return bool(re.search(r"\([0-9]+\s*\+\s*[0-9]+\)", text))


# ============================================
# PARSER LOGIKAL
# ============================================


def _parse_logikal_position(
    rows: list[list[str]], target_pos: str, vendor_profile
) -> dict[str, list[dict]]:
    data = {"profiles": [], "hardware": []}

    in_target = False
    current_section = None
    qty_idx = dim_idx = pos_idx = None

    # Przechowujemy dane pod znormalizowanym kodem (lub oryginalnym, jeśli normalizacja pusta)
    aggr_data = {"profiles": OrderedDict(), "hardware": OrderedDict()}

    active_code = None
    orphan_entries = []

    def is_blank_row(r):
        return (not r) or all(not clean(c) for c in r)

    def is_code_row(c0):
        if not c0:
            return False
        c0 = clean(c0)

        # NOWE: jeśli to opis z inline kodami — NIE jest kodem
        if current_section == "hardware" and _is_desc_with_inline_codes(c0):
            return False

        # BUG FIX #5: specjalne okucia z polskimi znakami
        if current_section == "hardware" and _is_special_hardware_keyword(c0):
            return True

        if current_section == "profiles" and CODE_ROW_RE.search(c0):
            return True
        if (
            current_section == "hardware"
            # BUG FIX: dopuszczamy myślniki (sufiks R----NNNN) i znak + (Łącznik z wkrętem)
            and re.match(
                r"^[A-Z0-9\s\-+()]+$", re.sub(r"R-{3,}\d+", "", c0).replace("mm", "").strip()
            )
            and len(c0) < 40
            and not c0.startswith("Kod")
        ):
            return True
        return False

    def next_significant_is_code(start_i):
        """Sprawdza czy następny znaczący wiersz po start_i to wiersz z kodem."""
        j = start_i
        while j < len(rows):
            r = [clean(c) for c in rows[j]]
            if is_blank_row(r):
                j += 1
                continue
            line = ";".join(r)
            if re.search(r"Poz\.\s*\d+", line, re.IGNORECASE):
                return False
            if r and re.match(r"^(Akcesoria|Okucia|Profile)\b", r[0], flags=re.IGNORECASE):
                return False
            if qty_idx is None:
                return False
            return is_code_row(r[0])
        return False

    def get_desc_for_code(start_i):
        """
        Pobiera opis dla kodu zaczynając od wiersza start_i.
        Opis to pierwszy niepusty wiersz, który NIE jest kodem,
        NIE jest nagłówkiem sekcji i NIE jest w liście noise.
        """
        noise = [
            "Kod:",
            "Uwagi",
            "Bdy",
            "Błędy",
            "Wstawione",
            "Do konstrukcji",
            "Ostrzeżenia",
            "Ostrzeenia",
            "Wszystkie rezultaty",
            "W edytorze systemu",
        ]
        j = start_i
        while j < len(rows):
            nxt = [clean(c) for c in rows[j]]
            if is_blank_row(nxt):
                j += 1
                continue
            first = nxt[0]
            if not first:
                j += 1
                continue
            # Jeśli następny znaczący wiersz to inny kod lub nagłówek sekcji — brak opisu
            if is_code_row(first) or re.match(
                r"^(Akcesoria|Okucia|Profile)\b", first, flags=re.IGNORECASE
            ):
                break
            # Odfiltruj znane szumy
            if any(first.startswith(n) for n in noise):
                j += 1
                continue
            return first
        return "—"

    def normalize_hardware_key(raw_code: str) -> str:
        # BUG FIX #5: nie normalizuj specjalnych okuć z polskimi znakami
        if _is_special_hardware_keyword(raw_code):
            return raw_code
        if hasattr(vendor_profile, "parse_hardware_code"):
            norm = vendor_profile.parse_hardware_code(raw_code)
            return norm if norm else raw_code
        return raw_code

    pending_hw_desc = None
    for i in range(len(rows)):
        row_raw = rows[i]
        row = [clean(c) for c in row_raw]
        if is_blank_row(row):
            continue

        full_line = ";".join(row).replace('"', "")

        m_poz = re.search(r"Poz\.\s*(\d+)", full_line, re.IGNORECASE)
        if m_poz:
            if m_poz.group(1) == target_pos:
                in_target = True
                current_section = None
                active_code = None
                orphan_entries = []
                qty_idx = dim_idx = pos_idx = None
                continue
            else:
                if in_target:
                    in_target = False

        if not in_target:
            continue

        if row and re.match(r"^Profile\b", row[0], flags=re.IGNORECASE):
            current_section = "profiles"
            active_code = None
            orphan_entries = []
            qty_idx = dim_idx = pos_idx = None
            continue

        if row and re.match(r"^(Akcesoria|Okucia)\b", row[0], flags=re.IGNORECASE):
            current_section = "hardware"
            active_code = None
            orphan_entries = []
            qty_idx = dim_idx = pos_idx = None
            continue

        if not current_section:
            continue

        if any(c.lower().startswith("kod:") for c in row):
            qty_idx = next((k for k, c in enumerate(row) if c.lower().startswith("ilo")), None)
            dim_idx = next((k for k, c in enumerate(row) if c.lower().startswith("wym")), None)
            pos_idx = next((k for k, c in enumerate(row) if c.lower().startswith("po")), None)
            continue

        if qty_idx is None or dim_idx is None or pos_idx is None:
            continue

        first_col = row[0]

        # BUG FIX #4: Filtr stopek stron — PRZED noise filterem
        if _is_page_footer(row_raw, first_col):
            continue

        noise = [
            "Kod:",
            "Uwagi",
            "Bdy",
            "Błędy",
            "Wstawione",
            "Do konstrukcji",
            "Ostrzeżenia",
            "Ostrzeenia",
            "Wszystkie rezultaty",
            "W edytorze systemu",
            "Masa",
            "Powierzchnia",
            "Obwód",
            "Ciężar",
            "System:",
            "Kolor",
            "Robocizna",
        ]
        if any(first_col.startswith(n) for n in noise):
            continue
        if "DRZWI_EI60" in first_col or "SOLEC" in first_col or "DRZWI_" in first_col:
            if re.search(r"\(\d+\)$", first_col):
                continue

        qty = row[qty_idx] if qty_idx < len(row) else ""
        dim = row[dim_idx] if dim_idx < len(row) else ""
        loc = row[pos_idx] if pos_idx < len(row) else ""

        entry_data = {"qty": qty, "dim": dim, "loc": loc}
        has_data = bool(qty or dim or loc)

        # SCENARIUSZ 1: Pierwsza kolumna pusta — dane (sieroty lub kontynuacja)
        if not first_col:
            if has_data:
                if next_significant_is_code(i + 1):
                    # Za chwilę wjedzie kod → to jego "sierota"
                    orphan_entries.append(entry_data)
                elif active_code:
                    # Kolejne wymiary do obecnie aktywnego kodu
                    aggr_data[current_section][active_code]["entries"].append(entry_data)
                else:
                    # Awaryjnie — wisi przed wszystkim
                    orphan_entries.append(entry_data)
            continue

        # SCENARIUSZ 2: Wiersz z KODEM
        if is_code_row(first_col):
            raw_code = first_col

            if current_section == "hardware":
                norm_key = normalize_hardware_key(raw_code)
                active_code = norm_key if norm_key else raw_code
            else:
                active_code = raw_code

            # Opis: albo z pending (inline kody), albo z następnego wiersza
            if current_section == "hardware" and pending_hw_desc:
                desc = vendor_profile.format_hardware_desc(pending_hw_desc)
                pending_hw_desc = None
            else:
                desc = get_desc_for_code(i + 1)
                if current_section == "hardware":
                    desc = vendor_profile.format_hardware_desc(desc)

            target_dict = aggr_data[current_section]
            if active_code not in target_dict:
                target_dict[active_code] = {"code": active_code, "desc": desc, "entries": []}
            elif target_dict[active_code]["desc"] == "—":
                target_dict[active_code]["desc"] = desc

            if orphan_entries:
                target_dict[active_code]["entries"].extend(orphan_entries)
                orphan_entries = []

            if has_data:
                target_dict[active_code]["entries"].append(entry_data)

            continue

        # SCENARIUSZ 3: Wiersz z opisem (nie jest kodem)
        if first_col and not is_code_row(first_col):

            # MUSI BYĆ PIERWSZE — opis z inline kodami (np. "Łącznik z wkrętem (80122109 +80372710)")
            if current_section == "hardware" and _is_desc_with_inline_codes(first_col):
                pending_hw_desc = first_col
                continue

            # Odrzucamy opisy vendor-specific z myślnikiem " - "
            if current_section == "hardware" and re.search(r"\s-\s", first_col):
                continue

            if (
                active_code
                and aggr_data[current_section].get(active_code, {}).get("desc") == first_col
            ):
                # Opis już wczytany — jeśli ma dane, dodaj je
                if has_data:
                    aggr_data[current_section][active_code]["entries"].append(entry_data)
            else:
                # Zupełnie nowy element z samym opisem (np. Wkręty, Kołek rozporowy)
                active_code = first_col

                target_dict = aggr_data[current_section]
                if active_code not in target_dict:
                    target_dict[active_code] = {"code": first_col, "desc": first_col, "entries": []}

                if orphan_entries:
                    target_dict[active_code]["entries"].extend(orphan_entries)
                    orphan_entries = []

                if has_data:
                    target_dict[active_code]["entries"].append(entry_data)

    # ============================================
    # FINALIZACJA PROFILI — <br> join (jak oryginał)
    # ============================================
    #
    # LOGIKA:
    # Każdy entry to osobny wiersz wymiarów dla tego profilu
    # (jeden profil może mieć wiele wierszy — różne długości/lokalizacje).
    # qty/dim/loc łączymy <br> — dokładnie jak w oryginalnym, działającym parserze.
    #
    # DLACZEGO NIE OBLICZAMY:
    # LogiKal już zapisuje w CSV właściwą ilość z mnożnikiem konstrukcji:
    #   Poz. 1 (1 szt):  "1 szt"
    #   Poz. 2 (3 szt):  "1x3 szt", "2x3 szt"
    # Nie ma potrzeby nic przeliczać — bierzemy wprost z CSV.
    #
    for _, val in aggr_data["profiles"].items():
        if not val["entries"]:
            val["entries"].append({"qty": "1 szt", "dim": "—", "loc": "—"})

        qty_str = "<br>".join([e["qty"] if e["qty"] else "1 szt" for e in val["entries"]])
        dim_str = "<br>".join([e["dim"] if e["dim"] else "—" for e in val["entries"]])
        loc_str = "<br>".join([e["loc"] if e["loc"] else "—" for e in val["entries"]])

        data["profiles"].append(
            {
                "code": val["code"],
                "desc": val["desc"],
                "quantity": qty_str,
                "dimensions": dim_str,
                "location": loc_str,
            }
        )

    # ============================================
    # FINALIZACJA HARDWARE — qty wprost z CSV (BUG FIX #3)
    # ============================================
    #
    # LOGIKA:
    # LogiKal już zapisuje właściwą ilość z mnożnikiem konstrukcji w kolumnie qty:
    #   Poz. 1: "1 szt", "2 szt", "6 szt", "11 szt"
    #   Poz. 2: "1x3 szt", "2x3 szt", "6x3 szt", "11x3 szt"
    #
    # Format BUG FIX #3: "4x2 szt" (4 sztuki × 2 pozycje) — ale to LOGIKAL już daje!
    # Dla okuć SUMUJEMY entries (bo jeden kod może wystąpić w sekcji Akcesoria i Okucia
    # w tym samym pliku), ale qty bierzemy z CSV — nie przeliczamy.
    #
    # JEDNAK: entries dla hardware to zazwyczaj jeden wpis na kod (okucie ma jedną ilość),
    # więc bierzemy qty z pierwszego wpisu. Jeśli kod wystąpił kilka razy (np. w różnych
    # sekcjach), zostaną połączone w aggr_data przez normalizację klucza.
    #
    for _, val in aggr_data["hardware"].items():
        if not val["entries"]:
            val["entries"].append({"qty": "1 szt", "dim": "—", "loc": "—"})

        # Bierzemy qty bezpośrednio z CSV — LogiKal już wpisał właściwą wartość
        # (np. "1 szt", "2 szt", "1x3 szt", "2x3 szt", "11x3 szt")
        # Sprawdzamy czy wszystkie entries mają tę samą qty (tak powinno być)
        # Jeśli tak — bierzemy pierwszy. Jeśli nie — łączymy <br>.
        qty_values = [e["qty"] for e in val["entries"] if e["qty"]]
        if not qty_values:
            final_qty = "1 szt"
        elif len(set(qty_values)) == 1:
            # Wszystkie takie same — bierzemy jeden
            final_qty = qty_values[0]
        else:
            # Różne wartości (rzadkie) — łączymy
            final_qty = "<br>".join(qty_values)

        data["hardware"].append(
            {
                "code": val["code"],
                "desc": val["desc"],
                "quantity": final_qty,
                "dimensions": "—",
                "location": "—",
            }
        )

    return data


# ============================================
# STARY KOD REYNAERS (NIENARUSZONY)
# ============================================


def _extract_dims_reynaers(row, idx_map):
    qty = row[idx_map["qty"]] if idx_map["qty"] is not None and idx_map["qty"] < len(row) else ""
    dim = row[idx_map["dim"]] if idx_map["dim"] is not None and idx_map["dim"] < len(row) else ""
    loc = row[idx_map["loc"]] if idx_map["loc"] is not None and idx_map["loc"] < len(row) else ""

    if dim and not any(c.isdigit() for c in dim):
        dim = ""
    if qty and not any(c.isdigit() for c in qty):
        qty = ""

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


def _get_reynaers_positions(csv_path: str) -> dict:
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

        system = None
        line_upper = line.upper()
        m = re.search(r"MASTERLINE\s*(\d+)", line_upper)
        if m:
            system = f"masterline-{m.group(1)}"
        m = re.search(r"(CS|CP)-?\s*(\d+)", line_upper)
        if m:
            system = f"{m.group(1).lower()}-{m.group(2)}"
        m = re.search(r"(MB-\d+\w*)", line_upper)
        if m:
            s = re.sub(r"\s+(HI|SI)\b.*", "", m.group(1), flags=re.IGNORECASE)
            system = s.strip().lower()

        if system:
            if system not in systems:
                systems[system] = []
            systems[system].append(pos)
    return systems


def _get_reynaers_data(csv_path: str, target_pos: str, vendor_profile, product_db=None) -> dict:
    rows = _read_csv_rows(csv_path)
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
            if not cell[0].isdigit():
                continue
            if len(cell) > 20 and " " in cell:
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

        if new_code:
            active_profile_code = new_code
            clean_key = normalize_key(new_code)

            if product_db and clean_key in product_db:
                active_item_type = product_db[clean_key]["type"]
                active_profile_desc = product_db[clean_key]["desc"]
            else:
                if new_code.startswith(("008", "030", "108", "408", "508")):
                    active_item_type = "profile"
                else:
                    active_item_type = "hardware"
                active_profile_desc = ""

            qty, dim, loc = _extract_dims_reynaers(r, col_idx)

            potential_inline_desc = ""
            for _, val in enumerate(r):
                if val == new_code or val == qty or val == dim or val == loc:
                    continue
                if len(val) > 3 and not any(c.isdigit() for c in val):
                    if val.lower() not in IGNORE_SECTIONS:
                        potential_inline_desc = val
                        break

            if potential_inline_desc:
                if not active_profile_desc or active_profile_desc.lower() in GENERIC_DESCS:
                    active_profile_desc = potential_inline_desc

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

        elif active_profile_code:
            qty, dim, loc = _extract_dims_reynaers(r, col_idx)

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
                if not active_profile_desc or active_profile_desc.lower() in GENERIC_DESCS:
                    active_profile_desc = potential_desc
                    target_list = (
                        data["profiles"] if active_item_type == "profile" else data["hardware"]
                    )
                    if target_list:
                        target_list[-1]["desc"] = active_profile_desc

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
# FUNKCJE PUBLICZNE (Dla rename_images itp)
# ============================================


def get_positions_from_csv(csv_path: str) -> list:
    sys_map = get_positions_with_systems(csv_path)
    positions = []
    for pos_list in sys_map.values():
        positions.extend(pos_list)
    return sorted((set(positions)), key=lambda x: int(x))


def extract_system_from_csv(csv_path: str) -> str:
    systems_map = get_positions_with_systems(csv_path)
    if systems_map:
        return list(systems_map.keys())[0]
    return ""


def extract_color_codes_from_csv(csv_path: str) -> list:
    rows = _read_csv_rows(csv_path)
    colors = []
    for row in rows:
        if not any("Kolor profili:" in str(cell) for cell in row):
            continue
        for cell in row:
            if not cell or "Kolor profili:" in cell:
                continue
            cell_clean = re.sub(r'[\^\\[\]\'"\(\)*]', " ", str(cell).upper()).strip()
            if cell_clean and cell_clean not in colors:
                colors.append(cell_clean)
    return colors


def parse_hardware_from_csv(csv_path: str, vendor_profile) -> dict:
    positions = get_positions_from_csv(csv_path)
    hardware_codes = {}
    for pos in positions:
        data = get_data_for_position(csv_path, pos, vendor_profile, product_db=None)
        for hw in data["hardware"]:
            raw_code = hw["code"]
            desc = hw["desc"]

            if hasattr(vendor_profile, "parse_hardware_code"):
                normalized_code = vendor_profile.parse_hardware_code(raw_code)
            else:
                normalized_code = vendor_profile.parse_profile_code(raw_code)

            code = normalized_code if normalized_code else raw_code

            if code not in hardware_codes:
                hardware_codes[code] = {"desc": desc, "positions": set()}
            hardware_codes[code]["positions"].add(pos)
    return hardware_codes


def get_profile_codes_by_system(csv_path: str, vendor_profile) -> dict:
    systems_map = get_positions_with_systems(csv_path)
    profiles_by_sys = {}
    for sys_name, positions in systems_map.items():
        if sys_name not in profiles_by_sys:
            profiles_by_sys[sys_name] = set()
        for pos in positions:
            data = get_data_for_position(csv_path, pos, vendor_profile, product_db=None)
            for prof in data["profiles"]:
                raw_code = prof["code"]
                norm = vendor_profile.parse_profile_code(raw_code)
                code = norm if norm else raw_code
                profiles_by_sys[sys_name].add(code)
    return profiles_by_sys
