# tests/test_vendors.py
"""
Testy parsowania kodów profili i okuć.
"""
import pytest
from vendors import AluProfProfile, GenericProfile, clean, VENDOR_PROFILES, ReynaersProfile


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
        ("K41 PL27 4R7016", "K41PL27X"),   # litery + kolor
    ])
    def test_alpha_with_color(self, input_text, expected):
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
        "8000 965 D",
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
# TESTY ReynaersProfile - PROFILE
# ============================================

class TestReynaersProfiles:
    """Testy parse_profile_code dla Reynaers."""

    @pytest.mark.parametrize("input_text, expected", [
        ("108.0081.59 7021-2", "1080081X"),
        ("408.0014.59 7021-2", "4080014X"),
        ("508.0114.59 7021-2", "5080114X"),
        ("508.0892.59 7021-2", "5080892X"),
        ("408.0026.59 7021-2", "4080026X"),
        ("408.1028.59 7021-2", "4081028X"),
        ("065.6566.59 7021-2", "0656566X"),
    ])
    def test_with_ral_color(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        ("108.1874.17", "1081874"),
    ])
    def test_variant_no_color(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize("input_text", [
        "",
        "hello world",
        "K51 8143",
    ])
    def test_no_match(self, input_text):
        assert ReynaersProfile.parse_profile_code(input_text) == ""


class TestReynaersHardware:
    """Testy parse_hardware_code dla Reynaers."""

    @pytest.mark.parametrize("input_text, expected", [
        ("061.6634.ZC",         "0616634X"),
        ("065.6566.59 7021-2",  "0656566X"),
    ])
    def test_with_color(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        ("061.6461.--",  "0616461"),
        ("061.6681.--",  "0616681"),
        ("061.7054.--",  "0617054"),
        ("061.8154.--",  "0618154"),
        ("065.6571.--",  "0656571"),
    ])
    def test_no_color_dashes(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        ("069.6831.04",  "0696831"),
        ("069.8360.04",  "0698360"),
        ("069.8426.04",  "0698426"),
        ("069.8427.04",  "0698427"),
        ("069.8511.04",  "0698511"),
        ("069.8512.04",  "0698512"),
    ])
    def test_variant_suffix(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text, expected", [
        ("168.5000.00",  "1685000"),
        ("168.5012.--",  "1685012"),
        ("168.7073.00",  "1687073"),
        ("168.7088.00",  "1687088"),
        ("168.7104.00",  "1687104"),
        ("168.8074.00",  "1688074"),
        ("168.8104.00",  "1688104"),
        ("169.8748.04",  "1698748"),
    ])
    def test_standard_neutral(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize("input_text", [
        "",
        "hello",
        "K51 8143",
    ])
    def test_no_match(self, input_text):
        assert ReynaersProfile.parse_hardware_code(input_text) == ""

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