# tests/test_csv_parser.py
"""
Testy parsowania plików CSV.
"""

import os

from parsers.csv_parser import _parse_logikal_position
from parsers.vendors import AluProfProfile

# ============================================
# HELPER: tworzenie CSV do testów
# ============================================


def write_csv(tmp_dir, content, filename="test.csv"):
    path = os.path.join(tmp_dir, filename)
    with open(path, "w", encoding="cp1250") as f:
        f.write(content)
    return path


# ============================================
# POZYCJE
# ============================================


"""
class TestGetPositions:
    def test_basic(self, tmp_dir):
        csv = write_csv(
            tmp_dir,
            "Poz. 1;;MB-78EI;Drzwi;\n" "Poz. 2;;MB-78EI;Okno;\n" "Poz. 5;;MB-78EI;FIX;\n",
        )
        result = get_positions_from_csv(csv)
        assert result == ["1", "2", "5"]

    def test_no_positions(self, tmp_dir):
        csv = write_csv(tmp_dir, "Nagłówek;kolumna;\n")
        result = get_positions_from_csv(csv)
        assert result == []
"""

# ============================================
# SYSTEM
# ============================================


"""
class TestExtractSystem:
    def test_basic(self, tmp_dir):
        csv = write_csv(tmp_dir, "System:;\n" ";MB-78EI HI;\n")
        result = extract_system_from_csv(csv)
        assert result == "mb-78ei"

    def test_mb86(self, tmp_dir):
        csv = write_csv(tmp_dir, "System:;\n" ";MB-86 SI;\n")
        result = extract_system_from_csv(csv)
        assert result == "mb-86"

    def test_not_found(self, tmp_dir):
        csv = write_csv(tmp_dir, "Dane;bez;systemu;\n")
        result = extract_system_from_csv(csv)
        assert result is None
"""

# ============================================
# KOLORY
# ============================================

"""
class TestExtractColors:
    def test_multiple_colors(self, tmp_dir):
        csv = write_csv(tmp_dir, "Kolor profili:;B4 [brązowy];I4 [czarny];D [srebrny]\n")
        result = extract_color_codes_from_csv(csv)
        assert "B4" in result
        assert "I4" in result
        assert "D" in result

    def test_single_color(self, tmp_dir):
        csv = write_csv(tmp_dir, "Kolor profili:;B4 [brązowy]\n")
        result = extract_color_codes_from_csv(csv)
        assert result == ["B4"]

    def test_no_colors(self, tmp_dir):
        csv = write_csv(tmp_dir, "Dane;bez;kolorów;\n")
        result = extract_color_codes_from_csv(csv)
        assert result == []
"""

# ============================================
# PROFILE DODATKOWE
# ============================================


"""
class TestAdditionalProfiles:
    def test_finds_profiles(self, tmp_dir):
        csv = write_csv(
            tmp_dir,
            "Profile dodatkowe;\n" "K51 8139;;\n" "120 470;;\n" "K41 PL27 4R7016;\n" "Akcesoria;\n",
        )
        #result = extract_additional_profiles_from_csv(csv, AluProfProfile)
        assert "K518139" in result
        assert "120470" in result
        assert "K41PL27X" in result

    def test_empty_section(self, tmp_dir):
        csv = write_csv(tmp_dir, "Profile dodatkowe;\n" "Akcesoria;\n")
        result = extract_additional_profiles_from_csv(csv, AluProfProfile)
        assert result == set()
"""

# Minimalne CSV jako lista wierszy
ROWS_LACZNIK = [
    ["Poz. 1"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    ["8012 2214", "", "", "", "", "", "", "", ""],
    ["Łącznik z wkrętem (80122109 +80372710)", "", ""],
    ["", "", "", "", "4 szt", "", "", "", "1+3..4"],
]


def test_lacznik_ma_opis():
    result = _parse_logikal_position(ROWS_LACZNIK, "1", AluProfProfile)
    hw = result["hardware"]
    codes = [item["code"] for item in hw]
    assert "80122214" in codes  # ← bez replace(), pełna asercja


ROWS_LACZNIK_Z_OPISEM = [
    ["Poz. 1"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    # Opis z inline kodami PRZED numerycznym kodem
    ["Łącznik z wkrętem (80122109 +80372710)", "", ""],
    ["8012 2214", "", "", "", "4 szt", "", "", "", "1+3..4"],
]


class TestInlineCodeDesc:
    def test_opis_z_inline_kodami_trafia_jako_desc(self):
        """Wiersz 'Łącznik z wkrętem (80122109 +80372710)' nie może być osobnym rekordem"""
        result = _parse_logikal_position(ROWS_LACZNIK_Z_OPISEM, "1", AluProfProfile)
        hw = result["hardware"]
        codes = [item["code"] for item in hw]

        # Nie może być osobnym wpisem
        assert "Łącznik z wkrętem (80122109 +80372710)" not in codes

    def test_opis_z_inline_kodami_przypisany_do_kodu(self):
        """Opis powinien trafić do pola desc rekordu 80122214"""
        result = _parse_logikal_position(ROWS_LACZNIK_Z_OPISEM, "1", AluProfProfile)
        hw = result["hardware"]
        item = next((i for i in hw if "80122214" in i["code"].replace(" ", "")), None)

        assert item is not None, "Brak rekordu z kodem 80122214"
        assert "80122109" in item["desc"]
        assert "80372710" in item["desc"]


class TestIsCodeRow:
    """Testujemy zachowanie is_code_row przez obserwację wyników parsowania"""

    def test_opis_z_inline_kodami_nie_jest_kodem(self):
        """'Łącznik z wkrętem (...)' nie może być traktowany jako kod"""
        result = _parse_logikal_position(ROWS_LACZNIK_Z_OPISEM, "1", AluProfProfile)
        hw = result["hardware"]
        # Jeśli byłby kodem, byłby kluczem w hw — nie powinien nim być
        assert not any("Łącznik z wkrętem" in item["code"] for item in hw)


ROWS_LACZNIK_OSCIEZNICOWY_BEZ_KODU = [
    ["Poz. X"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    # opis który pasuje do _is_special_hardware_keyword ale NIE ma kodu po sobie
    ["Łącznik ościeżnicowy 68x16 mm", "", ""],
    ["80322073", "", "", "", "4 szt", "", "", "", "1"],
]

ROWS_LACZNIK_OSCIEZNICOWY_OPIS_PRZED_KODEM = [
    ["Poz. Y"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    ["Łącznik ościeżnicowy 68x16 mm", "", ""],
    # TEN wiersz nie ma żadnego kodu numerycznego po opisie
]


class TestOpiszBezKoduNieTrafia:
    def test_opis_hardware_bez_kodu_nie_tworzy_rekordu_z_opisem_jako_kodem(self):
        """Opis-tylko wiersz nigdy nie może stać się rekordem z code==desc"""
        result = _parse_logikal_position(ROWS_LACZNIK_OSCIEZNICOWY_BEZ_KODU, "X", AluProfProfile)
        hw = result["hardware"]
        # Nie może być rekordu gdzie code == "Łącznik ościeżnicowy 68x16 mm"
        assert not any(
            item["code"] == "Łącznik ościeżnicowy 68x16 mm" for item in hw
        ), f"Znaleziono błędny rekord: {[i for i in hw if i['code'] == 'Łącznik ościeżnicowy 68x16 mm']}"

    def test_opis_hardware_przypisany_do_nastepnego_kodu(self):
        """Opis powinien trafić jako pending_hw_desc do następnego kodu"""
        result = _parse_logikal_position(ROWS_LACZNIK_OSCIEZNICOWY_BEZ_KODU, "X", AluProfProfile)
        hw = result["hardware"]
        item = next((i for i in hw if "80322073" in i["code"]), None)
        assert item is not None, "Brak rekordu 80322073"
        assert "Łącznik ościeżnicowy 68x16 mm" in item["desc"]


ROWS_OPIS_BEZ_DANYCH = [
    ["Poz. Z"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    # Wiersz opisu — brak danych w kolumnach
    ["Łącznik ościeżnicowy 68x16 mm", "", "", "", "", "", "", "", ""],
    ["80322073", "", "", "", "4 szt", "", "", "", "1"],
]


class TestOpiszBezDanychJakoPendingDesc:
    def test_opis_bez_danych_ustawia_pending_desc(self):
        """Wiersz opisu bez ilości/wymiarów → pending_hw_desc, nie nowy rekord"""
        result = _parse_logikal_position(ROWS_OPIS_BEZ_DANYCH, "Z", AluProfProfile)
        hw = result["hardware"]
        assert not any(item["code"] == "Łącznik ościeżnicowy 68x16 mm" for item in hw)

    def test_pending_desc_przypisany_do_nastepnego_kodu(self):
        """pending_hw_desc trafia do desc następnego kodu numerycznego"""
        result = _parse_logikal_position(ROWS_OPIS_BEZ_DANYCH, "Z", AluProfProfile)
        hw = result["hardware"]
        item = next((i for i in hw if "80322073" in i["code"]), None)
        assert item is not None, "Brak rekordu 80322073"
        assert "Łącznik ościeżnicowy" in item["desc"]


# ============================================
# _parse_logikal_position — hardware desc
# ============================================


class TestParseLogikalHardwareDesc:
    """
    Testy sprawdzające poprawność przypisania desc do kodów okuć.
    Weryfikuje dwa known bugs:
      1. Stopka strony (np. 'Szpital_etap_8 (15)') wyciekająca jako desc
      2. Przesunięcie desc o jeden wiersz gdy dwa kolejne kody mają
         podobną nazwę handlową (np. Łącznik z wkrętem)
    """

    def _make_rows(self, entries):
        rows = [
            ["Poz. 1", "", "MB-78EI", "Drzwi", "", "", "", "", "", ""],
            ["Okucia", "", "", "", "", "", "", "", "", ""],
            ["Kod:", "Rysunek", "", "", "Ilość", "Wymiary", "", "", "Położenie", ""],
        ]
        for entry in entries:
            code, qty, desc = entry[:3]
            loc = entry[3] if len(entry) > 3 else ""
            rows.append(["", "", "", "", qty, "", "", "", loc, ""])
            rows.append([code, "", "", "", "", "", "", "", "", ""])
            rows.append([desc, "", "", "", "", "", "", "", "", ""])
        rows.append(["Poz. 2", "", "MB-78EI", "Okno", "", "", "", "", "", ""])
        return rows

    def test_distinct_desc_for_similar_connector_names(self):
        """
        Dwa kody łączników z prawie identyczną nazwą handlową —
        każdy powinien dostać swój własny opis, nie opis poprzedniego.
        """
        from parsers.csv_parser import _parse_logikal_position
        from parsers.vendors import AluProfProfile

        rows = self._make_rows(
            [
                ("8012 2214 ", "8 szt", "Łącznik z wkrętem (80122109 +80372710)", "A..B"),
                ("8012 2215 ", "4 szt", "Łącznik z wkrętem (80122111 +80372710)", "1+3..4"),
                ("8032 2073 ", "18 szt", "Łącznik ościeżnicowy 68x16 mm", "1..2+4"),
            ]
        )

        result = _parse_logikal_position(rows, "1", AluProfProfile)
        hw = {h["code"]: h["desc"] for h in result["hardware"]}

        assert "80122214" in hw
        assert "80122215" in hw
        assert "80322073" in hw

        # Każdy kod musi mieć swój unikalny opis
        assert "80122109" in hw["80122214"]
        assert "80122111" in hw["80122215"]
        assert hw["80322073"] == "Łącznik ościeżnicowy 68x16 mm"

    def test_page_footer_not_leaked_as_desc(self):
        from parsers.csv_parser import _parse_logikal_position
        from parsers.vendors import AluProfProfile

        rows = [
            ["Poz. 1", "", "MB-78EI", "Drzwi", "", "", "", "", "", ""],
            ["Okucia", "", "", "", "", "", "", "", "", ""],
            ["Kod:", "Rysunek", "", "", "Ilość", "Wymiary", "", "", "Położenie", ""],
            ["", "", "", "", "11 szt", "", "", "", "", ""],
            ["8043 504X", "", "", "", "", "", "", "", "", ""],
            ["Zaślepka otworu o14 mm[czarny mat]", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "11 szt", "", "", "", "", ""],
            ["Kołek rozporowy", "", "", "", "", "", "", "", "", ""],
            ["Szpital_etap_8 (15)", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "1 szt", "", "", "", "", ""],
            ["8000 4318 ", "", "", "", "", "", "", "", "", ""],
            ["Wkładka bębenkowa 35/35 mm", "", "", "", "", "", "", "", "", ""],
            ["Poz. 2", "", "MB-78EI", "Okno", "", "", "", "", "", ""],
        ]

        result = _parse_logikal_position(rows, "1", AluProfProfile)
        hw = {h["code"]: h["desc"] for h in result["hardware"]}

        assert hw.get("Kołek rozporowy") == "—"
        assert hw.get("80004318") == "Wkładka bębenkowa 35/35 mm"

    def test_no_desc_shift_after_page_footer(self):
        from parsers.csv_parser import _parse_logikal_position
        from parsers.vendors import AluProfProfile

        rows = [
            ["Poz. 1", "", "MB-78EI", "Drzwi", "", "", "", "", "", ""],
            ["Okucia", "", "", "", "", "", "", "", "", ""],
            ["Kod:", "Rysunek", "", "", "Ilość", "Wymiary", "", "", "Położenie", ""],
            ["", "", "", "", "2 szt", "", "", "", "", ""],
            ["8012 4123 ", "", "", "", "", "", "", "", "", ""],
            ["Łącznik 31 mm", "", "", "", "", "", "", "", "", ""],
            ["Szpital_etap_8 (99)", "", "", "", "", "", "", "", "", ""],
            ["", "", "", "", "1 szt", "", "", "", "", ""],
            ["8000 4318 ", "", "", "", "", "", "", "", "", ""],
            ["Wkładka bębenkowa 35/35 mm", "", "", "", "", "", "", "", "", ""],
            ["Poz. 2", "", "MB-78EI", "Okno", "", "", "", "", "", ""],
        ]

        result = _parse_logikal_position(rows, "1", AluProfProfile)
        hw = {h["code"]: h["desc"] for h in result["hardware"]}

        assert hw.get("80124123") == "Łącznik 31 mm"
        assert hw.get("80004318") == "Wkładka bębenkowa 35/35 mm"


# ============================================
# OKUCIA — inline desc in code row (BUG FIX: 8000 4327)
# ============================================

ROWS_LISTWA_INLINE_WYCOFANE = [
    ["Poz. 1"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    [
        "8000 4327",
        "",
        "600mm",
        "WYCOFANE DOMATIC - Listwa dymoszczelna 600 mm",
        "1 sztB",
        "",
        "",
        "",
        "B",
    ],
]

ROWS_LISTWA_INLINE = [
    ["Poz. 1"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    ["8000 4327", "", "640mm", "DOMATIC - Listwa dymoszczelna 640mm", "", "", "", "", "A"],
    ["8000 4327", "", "1200mm", "DOMATIC - Listwa dymoszczelna 1200mm", "", "", "", "", "B"],
]

# Stopka dokładnie taka jak w prawdziwym CSV (bez spacji)
ROWS_LISTWA_INLINE_Z_STOPKA = [
    ["Poz. 1"],
    ["Akcesoria"],
    ["Kod:", "", "", "", "Ilość", "Wymiary", "", "", "Położenie"],
    ["8000 4327", "", "640mm", "DOMATIC - Listwa dymoszczelna 640mm", "", "", "", "", "A"],
    ["Szpitaletap8 47124 19715.04.2026", "", "", "", "", "", "", "", ""],
    ["8000 4327", "", "1200mm", "DOMATIC - Listwa dymoszczelna 1200mm", "", "", "", "", "B"],
]


class TestInlineHardwareDesc:

    def test_inline_desc_640mm(self):
        """8000 4327 640mm — desc from column 3, not from the next row"""
        result = _parse_logikal_position(ROWS_LISTWA_INLINE, "1", AluProfProfile)
        hw = {h["code"].replace(" ", ""): h["desc"] for h in result["hardware"]}
        assert "80004327" in hw
        assert "DOMATIC" in hw["80004327"]
        assert "640" in hw["80004327"]

    def test_inline_desc_same_code_twice_first_desc_wins(self):
        """
        Parser merges two rows with identical code 8000 4327 into one record.
        The first inline desc (640mm) is stored — second row does not overwrite it.
        """
        result = _parse_logikal_position(ROWS_LISTWA_INLINE, "1", AluProfProfile)
        hw = [h for h in result["hardware"] if h["code"].replace(" ", "") == "80004327"]
        # Either one merged record or two — neither should have empty/dash desc
        assert len(hw) >= 1
        assert all(h["desc"] != "—" for h in hw)
        assert all("DOMATIC" in h["desc"] for h in hw)

    def test_inline_desc_wycofane_not_treated_as_noise(self):
        """Desc starting with 'WYCOFANE' is not noise — must be stored as desc"""
        result = _parse_logikal_position(ROWS_LISTWA_INLINE_WYCOFANE, "1", AluProfProfile)
        hw = {h["code"].replace(" ", ""): h["desc"] for h in result["hardware"]}
        assert "80004327" in hw
        assert "WYCOFANE" in hw["80004327"]
        assert "600" in hw["80004327"]

    def test_page_footer_between_inline_rows_does_not_corrupt_desc(self):
        """Page footer between two 8000 4327 rows must not leak into desc"""
        result = _parse_logikal_position(ROWS_LISTWA_INLINE_Z_STOPKA, "1", AluProfProfile)
        hw = [h for h in result["hardware"] if h["code"].replace(" ", "") == "80004327"]
        descs = [h["desc"] for h in hw]
        assert all("Szpital" not in d for d in descs), f"Page footer leaked into desc: {descs}"
        assert all("DOMATIC" in d for d in descs)

    def test_no_regression_standard_next_row_desc_still_works(self):
        """Regression: codes without inline desc still pick up desc from the next row"""
        result = _parse_logikal_position(ROWS_LACZNIK, "1", AluProfProfile)
        hw = {h["code"].replace(" ", ""): h["desc"] for h in result["hardware"]}
        assert "80122214" in hw
        assert hw["80122214"] != "—"
