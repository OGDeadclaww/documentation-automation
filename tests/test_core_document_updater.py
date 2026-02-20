"""
Testy jednostkowe dla core/document_updater.py
"""

from core.document_updater import (
    format_dimensions,
    get_output_filename,
    strip_date_from_folder_name,
)


class TestFormatDimensions:
    """Testy funkcji format_dimensions"""

    def test_angle_with_degree(self):
        """Kąt ze stopniem"""
        result = format_dimensions("1234x567 (45°)")
        assert "*" in result
        assert "(45°)" in result

    def test_angle_with_minute(self):
        """Kąt z minutami"""
        result = format_dimensions("1234x567 (45'30\")")
        assert "*" in result

    def test_no_angle(self):
        """Brak kąta"""
        result = format_dimensions("1234x567")
        assert result == "1234x567"

    def test_empty_string(self):
        """Pusty string"""
        assert format_dimensions("") == ""
        assert format_dimensions(None) is None


class TestStripDateFromFolderName:
    """Testy funkcji strip_date_from_folder_name"""

    def test_remove_date_prefix(self):
        """Usuwanie prefiksu daty"""
        result = strip_date_from_folder_name("2024-01-23_Project")
        assert result == "Project"
        assert "2024" not in result

    def test_different_separator(self):
        """Różne separatory"""
        result = strip_date_from_folder_name("2024.01.23_Project")
        assert "2024" not in result

    def test_no_date(self):
        """Brak daty"""
        result = strip_date_from_folder_name("Project_NoDate")
        assert result == "Project_NoDate"


class TestGetOutputFilename:
    """Testy funkcji get_output_filename"""

    def test_clean_name(self):
        """Czysta nazwa"""
        result = get_output_filename("2024-01-23_Project")
        assert result.endswith(".md")
        assert "2024" not in result

    def test_adds_extension(self):
        """Dodaje rozszerzenie"""
        result = get_output_filename("Project")
        assert result.endswith(".md")
