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
