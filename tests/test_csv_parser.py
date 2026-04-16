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
