"""
Testy jednostkowe dla core/file_scanner.py
"""

from core.file_scanner import (
    extract_date_from_filename,
    find_project_folder,
)


class TestFindProjectFolder:
    """Testy funkcji find_project_folder"""

    def test_find_existing_folder(self, tmp_path):
        """Znajdowanie istniejącego folderu"""
        # Utwórz strukturę
        base = tmp_path / "projects"
        base.mkdir()
        target = base / "P241031_BMEIA"
        target.mkdir()

        results = find_project_folder(str(base), "P241031", max_depth=2)
        assert len(results) == 1
        assert "P241031_BMEIA" in results[0]

    def test_no_matching_folder(self, tmp_path):
        """Brak pasującego folderu"""
        base = tmp_path / "projects"
        base.mkdir()
        (base / "OTHER").mkdir()

        results = find_project_folder(str(base), "P999999", max_depth=2)
        assert len(results) == 0

    def test_max_depth_respected(self, tmp_path):
        """Maksymalna głębokość"""
        base = tmp_path / "projects"
        base.mkdir()
        level1 = base / "level1"
        level1.mkdir()
        level2 = level1 / "level2"
        level2.mkdir()
        target = level2 / "P241031_deep"
        target.mkdir()

        # max_depth=1 nie powinien znaleźć
        results = find_project_folder(str(base), "P241031", max_depth=1)
        assert len(results) == 0

        # max_depth=3 powinien znaleźć
        results = find_project_folder(str(base), "P241031", max_depth=3)
        assert len(results) == 1


class TestExtractDateFromFilename:
    """Testy funkcji extract_date_from_filename"""

    def test_dd_mm_yyyy_pattern(self):
        """Pattern DD.MM.YYYY"""
        result = extract_date_from_filename("dokument_23.01.2024.pdf")
        assert result == "23.01.2024"

    def test_dd_mm_yy_pattern(self):
        """Pattern DD-MM-YY"""
        result = extract_date_from_filename("dokument_2-12-25.pdf")
        assert "25" in result or "2025" in result

    def test_iso_pattern(self):
        """Pattern YYYY-MM-DD"""
        result = extract_date_from_filename("dokument_2024-01-23.pdf")
        assert result == "23.01.2024"

    def test_no_date_fallback(self):
        """Brak daty = dzisiejsza"""
        import datetime

        result = extract_date_from_filename("dokument_bez_daty.pdf")
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        assert result == today

    def test_folder_name_fallback(self):
        """Data z nazwy folderu"""
        result = extract_date_from_filename("dokument.pdf", folder_name="2024-01-23_Project")
        assert result == "23.01.2024"
