"""
Testy jednostkowe dla core/context_builder.py
"""

from unittest.mock import MagicMock, patch

from core.context_builder import (
    _aggregate_global_qty,
    get_hardware_for_position,
    get_view_for_position,
    parse_project_name,
)

# ============================================
# parse_project_name
# ============================================


class TestParseProjectName:
    def test_full_format(self):
        result = parse_project_name("2024-01-23_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA")
        assert result["client"] == "Produkcja Beddeleem"
        assert result["number"] == "P241031"
        assert "BMEIA" in result["desc"]

    def test_minimal_format(self):
        result = parse_project_name("P241031")
        assert result["number"] == "P241031"
        assert result["client"] == ""

    def test_no_project_number(self):
        """BUG FIX #8: brak numeru → underscores zamieniane na spacje"""
        result = parse_project_name("Projekt_Bez_Numera")
        assert result["number"] == ""
        assert result["client"] == "Projekt Bez Numera"  # spacje, nie underscores

    def test_snake_case_converted_to_title_case(self):
        result = parse_project_name("Szpital_etap_8")
        assert result["number"] == ""
        assert result["client"] == "Szpital Etap 8"

    def test_date_prefix_stripped(self):
        result = parse_project_name("2025-04-16_Firma ABC_ P251234 Opis projektu")
        assert result["client"] == "Firma ABC"
        assert result["number"] == "P251234"

    def test_p_number_6_digits(self):
        result = parse_project_name("Klient XYZ P241031 Projekt")
        assert result["number"] == "P241031"

    def test_p_number_5_digits(self):
        result = parse_project_name("Klient XYZ P24103 Projekt")
        assert result["number"] == "P24103"


# ============================================
# get_view_for_position
# ============================================


class TestGetViewForPosition:
    """Testy funkcji get_view_for_position"""

    def test_returns_placeholder_when_missing(self):
        """Brak pliku = placeholder"""
        result = get_view_for_position("NONEXISTENT_PROJECT", "1")
        assert "logo.png" in result or "../../" in result

    def test_placeholder_contains_relative_path(self):
        """Placeholder to ścieżka relatywna, nie absolutna"""
        result = get_view_for_position("NONEXISTENT_PROJECT", "99")
        assert result.startswith("../../")

    def test_found_file_contains_project_name(self):
        """Znaleziony plik zawiera nazwę projektu w ścieżce"""
        fake_path = "/some/dir/views/Poz_3.jpg"
        with patch("glob.glob", return_value=[fake_path]):
            result = get_view_for_position("My Project", "3")
        assert "My%20Project" in result or "My Project" in result
        assert "Poz_3.jpg" in result


# ============================================
# _aggregate_global_qty
# ============================================


class TestAggregateGlobalQty:
    def test_simple_qty(self):
        assert _aggregate_global_qty(["4 szt"]) == "4 szt"

    def test_sum_multiple_entries(self):
        assert _aggregate_global_qty(["4 szt", "2 szt", "1 szt"]) == "7 szt"

    def test_multiplied_format(self):
        assert _aggregate_global_qty(["4x2 szt"]) == "8 szt"

    def test_mixed_formats(self):
        assert _aggregate_global_qty(["4x2 szt", "1 szt", "4x1 szt"]) == "13 szt"

    def test_empty_list(self):
        assert _aggregate_global_qty([]) == "1 szt"

    def test_no_digits_each_entry_counts_as_one(self):
        """Wpisy bez cyfr liczą się jako 1 każdy — zachowanie poprawne"""
        assert _aggregate_global_qty(["szt", "szt"]) == "2 szt"


# ============================================
# get_hardware_for_position — BUG FIX global_key
# ============================================


def test_debug_listwa_codes():
    from parsers.csv_parser import _parse_logikal_position, rows_for_pos_1
    from parsers.vendors import AluProfProfile

    # CSV = "C:\\Users\\pawel\\Desktop\\Zlecenia\\Jakub_Ojczyk\\Szpital\\Szpital_etap_8\\Szpital etap 8 - 1 skrzydłowe\\Szpital etap 8\\LP_dane.csv"

    # rows = _read_rows_logikal(CSV)
    # Znajdź pozycję z listw — np. pozycja 1
    result = _parse_logikal_position(rows_for_pos_1, "1", AluProfProfile)
    for h in result["hardware"]:
        if "80004" in h["code"].replace(" ", ""):
            print(repr(h["code"]), repr(h["desc"]))


def _make_hw_item(code: str, desc: str, qty: str = "4 szt") -> dict:
    return {"code": code, "desc": desc, "quantity": qty}


def _make_vendor_cls(parse_result: str | None = None):
    vendor = MagicMock()
    vendor.parse_hardware_code.return_value = parse_result
    return vendor


class TestGetHardwareForPositionGlobalKey:
    """
    BUG FIX: ten sam kod z różnymi opisami musi tworzyć osobne wpisy
    w all_hardware_map (klucz = code||desc).
    """

    def _call(self, hw_items: list[dict], all_hardware_map: dict) -> list[dict]:
        vendor_cls = MagicMock()
        vendor_cls.parse_hardware_code.side_effect = lambda c: c.replace(" ", "")

        with (
            patch(
                "parsers.csv_parser.get_data_for_position",  # patch w module źródłowym
                return_value={"hardware": hw_items},
            ),
            patch(
                "core.catalogs.build_hardware_catalog_link",
                return_value=("#", False),
            ),
        ):
            return get_hardware_for_position(
                csv_path="fake.csv",
                pos_num="1",
                vendor_key="aluprof",
                vendor_cls=vendor_cls,
                sys_name="MB-45",
                product_db={},
                all_hardware_map=all_hardware_map,
            )

    def test_same_code_different_desc_creates_two_global_entries(self):
        """80004327 640mm i 80004327 1200mm → dwa wpisy w all_hardware_map"""
        hw_items = [
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 640mm", "1 szt"),
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 1200mm", "1 szt"),
        ]
        all_hw = {}
        self._call(hw_items, all_hw)
        assert len(all_hw) == 2, f"Oczekiwano 2 wpisów, got {len(all_hw)}: {list(all_hw.keys())}"

    def test_same_code_same_desc_merges_into_one_global_entry(self):
        """Ten sam kod i opis z dwóch pozycji → jeden wpis, dwa qty_entries"""
        hw_items = [_make_hw_item("80122214", "Łącznik z wkrętem", "4 szt")]
        all_hw = {}
        self._call(hw_items, all_hw)
        self._call(hw_items, all_hw)
        assert len(all_hw) == 1
        assert all_hw[list(all_hw.keys())[0]]["qty_entries"] == ["4 szt", "4 szt"]

    def test_global_key_separator_not_in_code_or_desc(self):
        """Trzy różne kombinacje kod/opis → trzy osobne wpisy"""
        hw_items = [
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 640mm"),
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 1200mm"),
            _make_hw_item("80004326", "DOMATIC - Listwa dymoszczelna 1200mm"),
        ]
        all_hw = {}
        self._call(hw_items, all_hw)
        assert len(all_hw) == 3

    def test_hardware_list_sorted_by_code_then_desc(self):
        """hardware_list posortowana po (code, desc)"""
        hw_items = [
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 1200mm"),
            _make_hw_item("80004326", "DOMATIC - Listwa dymoszczelna 1200mm"),
            _make_hw_item("80004327", "DOMATIC - Listwa dymoszczelna 640mm"),
        ]
        all_hw = {}
        result = self._call(hw_items, all_hw)
        codes_descs = [(h["code"], h["desc"]) for h in result]
        assert codes_descs == sorted(codes_descs)

    def test_wycofane_desc_stored_correctly(self):
        """Opis 'WYCOFANE DOMATIC...' trafia do all_hardware_map"""
        hw_items = [_make_hw_item("80004327", "WYCOFANE DOMATIC - Listwa dymoszczelna 500mm")]
        all_hw = {}
        self._call(hw_items, all_hw)
        values = list(all_hw.values())
        assert len(values) == 1
        assert "WYCOFANE" in values[0]["desc"]


def test_debug_listwa_codes_1():
    import re

    from parsers.csv_parser import _parse_logikal_position, _read_rows_logikal
    from parsers.vendors import AluProfProfile

    CSV = r"C:\Users\pawel\Desktop\Zlecenia\Jakub_Ojczyk\Szpital\Szpital_etap_8\Szpital etap 8 - 1 skrzydłowe\LP_dane.csv"
    rows = _read_rows_logikal(CSV)

    # Zbierz unikalne pozycje
    positions = []
    for r in rows:
        line = ";".join(r)
        m = re.search(r"Poz\.\s*(\d+)", line, re.IGNORECASE)
        if m:
            positions.append(m.group(1))
    positions = list(dict.fromkeys(positions))
    print(f"\nPozycje: {positions}")

    # Przeskanuj wszystkie pozycje szukając kodów 80004326/80004327
    for pos in positions:
        result = _parse_logikal_position(rows, pos, AluProfProfile)
        for h in result["hardware"]:
            if "80004" in h["code"].replace(" ", ""):
                print(
                    f"  Poz.{pos}  code={h['code']!r}  desc={h['desc']!r}  qty={h.get('quantity', '?')!r}"
                )

    # assert False  # wymusza wyświetlenie outputu — usuń po debugowaniu


def test_parse_hardware_code_with_suffix():
    from parsers.vendors import AluProfProfile

    tests = [
        "8000 4327 1200mm",
        "8000 4327 640mm",
        "8000 4326 600mm",
        "8000 4327 500mm",
        "8000 4326",
        "8000 4327",
    ]
    for t in tests:
        result = AluProfProfile.parse_hardware_code(t)
        print(f"{t!r:30} → {result!r}")
    # assert False


def test_debug_pos_data_hardware():
    import sys

    sys.path.insert(0, "scripts")
    from core.context_builder import get_hardware_for_position
    from parsers.csv_parser import get_data_for_position
    from parsers.vendors import AluProfProfile

    CSV = r"C:\Users\pawel\Desktop\Zlecenia\Jakub_Ojczyk\Szpital\Szpital_etap_8\Szpital etap 8 - 1 skrzydłowe\LP_dane.csv"

    # Co wychodzi z parsera
    pos = get_data_for_position(CSV, "48", AluProfProfile, {})
    print(f"\nParser → {len(pos['hardware'])} rekordów hardware")
    for h in pos["hardware"]:
        if "80004" in h["code"].replace(" ", ""):
            print(f"  PARSER: code={h['code']!r}  desc={h['desc']!r}")

    # Co wychodzi z get_hardware_for_position
    all_hw_map = {}
    hw_list = get_hardware_for_position(
        CSV, "48", "aluprof", AluProfProfile, "MB-45", {}, all_hw_map
    )
    print(f"\nget_hardware_for_position → {len(hw_list)} rekordów")
    for h in hw_list:
        if "80004" in h["code"].replace(" ", ""):
            print(f"  HW_LIST: code={h['code']!r}  desc={h['desc']!r}")

    print("\nall_hardware_map keys z 80004:")
    for k in all_hw_map:
        if "80004" in k:
            print(f"  MAP: {k!r}")

    # assert False


def test_debug_global_hardware_context():
    import sys

    sys.path.insert(0, "scripts")
    from core.context_builder import prepare_context

    CSV = r"C:\Users\pawel\Desktop\Zlecenia\Jakub_Ojczyk\Szpital\Szpital_etap_8\Szpital etap 8 - 1 skrzydłowe\LP_dane.csv"
    ZM = r"C:\Users\pawel\Desktop\Zlecenia\Jakub_Ojczyk\Szpital\Szpital_etap_8\Szpital etap 8 - 1 skrzydłowe\ZM_dane.csv"
    DOC = r"C:\Users\pawel\Desktop\Zlecenia\Jakub_Ojczyk\Szpital\Szpital_etap_8\Szpital etap 8 - 1 skrzydłowe"

    ctx = prepare_context(CSV, ZM, "Szpital_etap_8", "aluprof", DOC)

    gh = ctx["global_hardware"]
    print(f"\nglobal_hardware: {len(gh)} rekordów")
    for hw in gh:
        if "80004" in hw["code"].replace(" ", ""):
            print(f"  code={hw['code']!r}  desc={hw['desc']!r}  qty={hw['quantity']!r}")

    # assert False
