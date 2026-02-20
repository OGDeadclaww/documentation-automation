"""
Testy jednostkowe dla core/context_builder.py
"""

from core.context_builder import (
    get_view_for_position,
    parse_project_name,
)


class TestParseProjectName:
    """Testy funkcji parse_project_name"""

    def test_full_format(self):
        """Pełny format z klientem i opisem"""
        result = parse_project_name("2024-01-23_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA")
        assert result["client"] == "Produkcja Beddeleem"
        assert result["number"] == "P241031"
        assert "BMEIA" in result["desc"]

    def test_minimal_format(self):
        """Minimalny format - sam numer projektu"""
        result = parse_project_name("P241031")
        assert result["number"] == "P241031"
        # Gdy tylko numer, client będzie pusty (numer jest ekstrahowany)
        assert result["client"] == ""

    def test_no_project_number(self):
        """Brak numeru projektu"""
        result = parse_project_name("Projekt_Bez_Numera")
        assert result["number"] == ""
        assert result["client"] == "Projekt_Bez_Numera"


class TestGetViewForPosition:
    """Testy funkcji get_view_for_position"""

    def test_returns_placeholder_when_missing(self):
        """Brak pliku = placeholder"""
        result = get_view_for_position("NONEXISTENT_PROJECT", "1")
        assert "logo.png" in result or "../../" in result
