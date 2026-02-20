"""
Testy jednostkowe dla core/versioning.py
"""

import json

from core.versioning import (
    get_clean_system_name,
    get_next_version,
)


class TestGetNextVersion:
    """Testy funkcji get_next_version"""

    def test_new_file_returns_v1(self, tmp_path):
        """Nowy plik MD = v1.0"""
        # Tymczasowa ścieżka
        import core.versioning as v

        original = v.DOCUMENTATION_PROJECTS_PATH
        v.DOCUMENTATION_PROJECTS_PATH = str(tmp_path)

        # Utwórz indeks
        index_path = tmp_path / "project_index.json"
        index_path.write_text(json.dumps({"P241031": {"version": "1.0"}}))

        # Plik MD nie istnieje
        md_path = tmp_path / "new.md"
        version = get_next_version(str(md_path), "P241031")
        assert version == "1.0"

        # Przywróć
        v.DOCUMENTATION_PROJECTS_PATH = original

    def test_existing_file_bumps_minor(self, tmp_path):
        """Istniejący plik = bump minor"""
        import core.versioning as v

        original = v.DOCUMENTATION_PROJECTS_PATH
        v.DOCUMENTATION_PROJECTS_PATH = str(tmp_path)

        # Utwórz plik MD
        md_path = tmp_path / "existing.md"
        md_path.write_text("test")

        # Indeks z wersją 2.0
        index_path = tmp_path / "project_index.json"
        index_path.write_text(json.dumps({"P241031": {"version": "2.0"}}))

        version = get_next_version(str(md_path), "P241031")
        assert version == "2.1"

        # Przywróć
        v.DOCUMENTATION_PROJECTS_PATH = original


class TestGetCleanSystemName:
    """Testy funkcji get_clean_system_name"""

    def test_remove_hi_suffix(self):
        """Usuwanie sufiksu HI"""
        result = get_clean_system_name("MB-70 HI")
        assert "HI" not in result
        assert "MB-70" in result

    def test_remove_si_suffix(self):
        """Usuwanie sufiksu SI"""
        result = get_clean_system_name("CS-77 SI")
        assert "SI" not in result

    def test_keep_bp_suffix(self):
        """Zachowanie sufiksu BP"""
        result = get_clean_system_name("CS-77 BP")
        assert "BP" in result

    def test_empty_string(self):
        """Pusty string"""
        assert get_clean_system_name("") == "UNKNOWN"
