"""
Testy jednostkowe dla core/catalogs.py
"""

import datetime

from core.catalogs import (
    _extract_date_from_catalog_filename,
    _normalize_system_name,
    get_catalog_status,
)


class TestGetCatalogStatus:
    """Testy funkcji get_catalog_status"""

    def test_actualny_katalog(self):
        """Katalog do 3 miesięcy = 🟢 Aktualny"""
        now = datetime.datetime.now()
        recent = now - datetime.timedelta(days=30)
        icon, text = get_catalog_status(recent)
        assert icon == "🟢"
        assert text == "Aktualny"

    def test_do_weryfikacji(self):
        """Katalog 3-6 miesięcy = 🟡 Do weryfikacji"""
        now = datetime.datetime.now()
        old = now - datetime.timedelta(days=120)
        icon, text = get_catalog_status(old)
        assert icon == "🟡"
        assert text == "Do weryfikacji"

    def test_nieaktualny(self):
        """Katalog powyżej 6 miesięcy = 🔴 Nieaktualny"""
        now = datetime.datetime.now()
        old = now - datetime.timedelta(days=200)
        icon, text = get_catalog_status(old)
        assert icon == "🔴"
        assert text == "Nieaktualny"


class TestNormalizeSystemName:
    """Testy funkcji _normalize_system_name"""

    def test_remove_separators(self):
        """Usuwanie separatorów"""
        assert _normalize_system_name("MB-70") == "mb70"
        assert _normalize_system_name("CS.77") == "cs77"
        assert _normalize_system_name("MASTERLINE 8") == "masterline8"

    def test_lowercase(self):
        """Konwersja do lowercase"""
        assert _normalize_system_name("MB-70") == "mb70"
        assert _normalize_system_name("Abc") == "abc"

    def test_empty_string(self):
        """Pusty string"""
        assert _normalize_system_name("") == ""


class TestExtractDateFromCatalogFilename:
    """Testy funkcji _extract_date_from_catalog_filename"""

    def test_dd_mm_yyyy_pattern(self, tmp_path):
        """Pattern DD.MM.YYYY"""
        file = tmp_path / "katalog_23.01.2024.pdf"
        file.write_text("test")
        date = _extract_date_from_catalog_filename(str(file))
        assert date.day == 23
        assert date.month == 1
        assert date.year == 2024

    def test_mm_yyyy_pattern(self, tmp_path):
        """Pattern MM_YYYY"""
        file = tmp_path / "katalog_04_2022.pdf"
        file.write_text("test")
        date = _extract_date_from_catalog_filename(str(file))
        assert date.month == 4
        assert date.year == 2022

    def test_year_only_pattern(self, tmp_path):
        """Pattern YYYY"""
        file = tmp_path / "katalog_2023.pdf"
        file.write_text("test")
        date = _extract_date_from_catalog_filename(str(file))
        assert date.year == 2023
