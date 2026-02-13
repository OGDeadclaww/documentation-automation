# tests/test_csv_parser.py
"""
Testy parsowania plików CSV.
"""
import os
import pytest
from csv_parser import (
    get_positions_from_csv,
    extract_system_from_csv,
    extract_color_codes_from_csv,
    extract_additional_profiles_from_csv,
)
from vendors import AluProfProfile


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

class TestGetPositions:
    def test_basic(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Poz. 1;;MB-78EI;Drzwi;\n"
            "Poz. 2;;MB-78EI;Okno;\n"
            "Poz. 5;;MB-78EI;FIX;\n"
        )
        result = get_positions_from_csv(csv)
        assert result == ["1", "2", "5"]

    def test_no_positions(self, tmp_dir):
        csv = write_csv(tmp_dir, "Nagłówek;kolumna;\n")
        result = get_positions_from_csv(csv)
        assert result == []

    def test_ignores_non_mb(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Poz. 1;;MB-78EI;OK;\n"
            "Poz. 2;;CS-77;Inne;\n"  # brak MB-
        )
        result = get_positions_from_csv(csv)
        assert result == ["1"]


# ============================================
# SYSTEM
# ============================================

class TestExtractSystem:
    def test_basic(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "System:;\n"
            ";MB-78EI HI;\n"
        )
        result = extract_system_from_csv(csv)
        assert result == "mb-78ei"

    def test_mb86(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "System:;\n"
            ";MB-86 SI;\n"
        )
        result = extract_system_from_csv(csv)
        assert result == "mb-86"

    def test_not_found(self, tmp_dir):
        csv = write_csv(tmp_dir, "Dane;bez;systemu;\n")
        result = extract_system_from_csv(csv)
        assert result is None


# ============================================
# KOLORY
# ============================================

class TestExtractColors:
    def test_multiple_colors(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Kolor profili:;B4 [brązowy];I4 [czarny];D [srebrny]\n"
        )
        result = extract_color_codes_from_csv(csv)
        assert "B4" in result
        assert "I4" in result
        assert "D" in result

    def test_single_color(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Kolor profili:;B4 [brązowy]\n"
        )
        result = extract_color_codes_from_csv(csv)
        assert result == ["B4"]

    def test_no_colors(self, tmp_dir):
        csv = write_csv(tmp_dir, "Dane;bez;kolorów;\n")
        result = extract_color_codes_from_csv(csv)
        assert result == []


# ============================================
# PROFILE DODATKOWE
# ============================================

class TestAdditionalProfiles:
    def test_finds_profiles(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Profile dodatkowe;\n"
            "K51 8139;;\n"
            "120 470;;\n"
            "K41 PL27 4R7016;\n"
            "Akcesoria;\n"
        )
        result = extract_additional_profiles_from_csv(csv, AluProfProfile)
        assert "K518139" in result
        assert "120470" in result
        assert "K41PL27X" in result

    def test_empty_section(self, tmp_dir):
        csv = write_csv(tmp_dir,
            "Profile dodatkowe;\n"
            "Akcesoria;\n"
        )
        result = extract_additional_profiles_from_csv(csv, AluProfProfile)
        assert result == set()