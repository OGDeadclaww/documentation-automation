# tests/test_vendors.py
"""
Testy parsowania kodów profili i okuć.
"""
import pytest
from vendors import AluProfProfile, GenericProfile, clean, VENDOR_PROFILES


# ============================================
# TESTY clean()
# ============================================

class TestClean:
    def test_nbsp(self):
        assert clean("hello\xa0world") == "hello world"

    def test_multiple_spaces(self):
        assert clean("  hello   world  ") == "hello world"

    def test_none(self):
        assert clean(None) == ""

    def test_empty(self):
        assert clean("") == ""


# ============================================
# TESTY AluProfProfile - PROFILE
# ============================================

class TestAluProfProfiles:
    """Testy parse_profile_code dla Aluprof."""

    @pytest.mark.parametrize("input_text, expected", [
        ("K51 8143 4R8017", "K518143"),
        ("K51 8395 4R8017", "K518395"),
        ("K51 8139 4R8017", "K518139"),
        ("K51 8143",        "K518143"),
        ("K12 0470",        "K120470"),
        ("K02 1234",        "K021234"),
    ])
    def test_with_k_prefix(self, input_text, expected):
        assert AluProfProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        ("120 470",  "120470"),
        ("120 4700", "1204700"),
    ])
    def test_bare_numeric(self, input_text, expected):
        assert AluProfProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize("input_text", [
        "",
        "hello world",
        "8000 965 D",      # okucie, nie profil
        "ABC",
    ])
    def test_no_match(self, input_text):
        assert AluProfProfile.parse_profile_code(input_text) == ""


# ============================================
# TESTY AluProfProfile - OKUCIA
# ============================================

class TestAluProfHardware:
    """Testy parse_hardware_code dla Aluprof."""

    @pytest.mark.parametrize("input_text, expected", [
        # Kolor jako osobny sufiks
        ("8000 965 D",    "8000965X"),
        ("8000 969 B4",   "8000969X"),
        ("8000 977 B4",   "8000977X"),
        ("8000 989 B4",   "8000989X"),
        ("8010 544 B4",   "8010544X"),
    ])
    def test_with_color_suffix(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        # Kolor wewnątrz kodu
        ("8A022 27I4", "8A02227X"),
    ])
    def test_embedded_color(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        # Bez koloru
        ("8000 2590",  "80002590"),
        ("8000 4431",  "80004431"),
        ("8000 4514",  "80004514"),
        ("8000 4516",  "80004516"),
        ("8000 9383",  "80009383"),
        ("8000 9732",  "80009732"),
        ("8010 4991",  "80104991"),
        ("8032 2073",  "80322073"),
        ("8032 2077",  "80322077"),
        ("8045 5040",  "80455040"),
    ])
    def test_plain_numeric(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        # Krótki format
        ("967 D", "967X"),
    ])
    def test_short_format(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    def test_with_color_suffix_param(self):
        """Wymuszony kolor przez parametr."""
        result = AluProfProfile.parse_hardware_code("8000 2590", color_suffix="B4")
        assert result == "80002590X"

    @pytest.mark.parametrize("input_text", [
        "",
        "hello",
        "K51 8143",  # profil, nie okucie
    ])
    def test_no_match(self, input_text):
        assert AluProfProfile.parse_hardware_code(input_text) == ""


# ============================================
# TESTY REJESTR DOSTAWCÓW
# ============================================

class TestVendorRegistry:
    def test_aluprof_exists(self):
        assert "aluprof" in VENDOR_PROFILES

    def test_generic_exists(self):
        assert "generic" in VENDOR_PROFILES

    def test_aluprof_is_correct_class(self):
        assert VENDOR_PROFILES["aluprof"] is AluProfProfile

    def test_all_vendors_have_name(self):
        for key, cls in VENDOR_PROFILES.items():
            assert cls.NAME, f"{key} nie ma NAME"

    def test_all_vendors_have_key(self):
        for key, cls in VENDOR_PROFILES.items():
            assert cls.KEY, f"{key} nie ma KEY"