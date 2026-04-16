# tests/test_vendors.py
"""
Testy parsowania kodów profili i okuć.
"""

import pytest

from parsers.vendors import VENDOR_PROFILES, AluProfProfile, ReynaersProfile, clean

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

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("K51 8143 4R8017", "K518143"),
            ("K51 8395 4R8017", "K518395"),
            ("K51 8139 4R8017", "K518139"),
            ("K51 8143", "K518143"),
            ("K12 0470", "K120470"),
            ("K02 1234", "K021234"),
        ],
    )
    def test_with_k_prefix(self, input_text, expected):
        assert AluProfProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("K41 PL27 4R7016", "K41PL27X"),  # litery + kolor
        ],
    )
    def test_alpha_with_color(self, input_text, expected):
        assert AluProfProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("120 470", "120470"),
            ("120 4700", "1204700"),
        ],
    )
    def test_bare_numeric(self, input_text, expected):
        assert AluProfProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text",
        [
            "",
            "hello world",
            "8000 965 D",
            "ABC",
        ],
    )
    def test_no_match(self, input_text):
        assert AluProfProfile.parse_profile_code(input_text) == ""


# ============================================
# TESTY AluProfProfile - OKUCIA
# ============================================


class TestAluProfHardware:
    """Testy parse_hardware_code dla Aluprof."""

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Kolor jako osobny sufiks
            ("8000 965 D", "8000965X"),
            ("8000 969 B4", "8000969X"),
            ("8000 977 B4", "8000977X"),
            ("8000 989 B4", "8000989X"),
            ("8010 544 B4", "8010544X"),
        ],
    )
    def test_with_color_suffix(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Kolor wewnątrz kodu
            ("8A022 27I4", "8A02227X"),
        ],
    )
    def test_embedded_color(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Bez koloru
            ("8000 2590", "80002590"),
            ("8000 4431", "80004431"),
            ("8000 4514", "80004514"),
            ("8000 4516", "80004516"),
            ("8000 9383", "80009383"),
            ("8000 9732", "80009732"),
            ("8010 4991", "80104991"),
            ("8032 2073", "80322073"),
            ("8032 2077", "80322077"),
            ("8045 5040", "80455040"),
        ],
    )
    def test_plain_numeric(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Krótki format
            ("967 D", "967X"),
        ],
    )
    def test_short_format(self, input_text, expected):
        assert AluProfProfile.parse_hardware_code(input_text) == expected

    def test_with_color_suffix_param(self):
        """Wymuszony kolor przez parametr."""
        result = AluProfProfile.parse_hardware_code("8000 2590", color_suffix="B4")
        assert result == "80002590X"

    @pytest.mark.parametrize(
        "input_text",
        [
            "",
            "hello",
            "K51 8143",  # profil, nie okucie
        ],
    )
    def test_no_match(self, input_text):
        assert AluProfProfile.parse_hardware_code(input_text) == ""


# ============================================
# TESTY ReynaersProfile - PROFILE
# ============================================


class TestReynaersProfiles:

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("108.0081.59 7021-2", "108.0081.XX"),
            ("408.0014.59 7021-2", "408.0014.XX"),
            ("508.0114.59 7021-2", "508.0114.XX"),
            ("408.0014.69 W:59 7047-2+Z:59 7021-2", "408.0014.XX"),
        ],
    )
    def test_ral_color_becomes_xx(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("0S0.2703.--", "0S0.2703.--"),
            ("0S0.7106.--", "0S0.7106.--"),
            ("061.6461.--", "061.6461.--"),
        ],
    )
    def test_double_dash_preserved(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("061.6634.ZC", "061.6634.ZC"),
            ("061.8527.ZC", "061.8527.ZC"),
        ],
    )
    def test_zc_preserved(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("108.1874.17", "108.1874.17"),
            ("069.6831.04", "069.6831.04"),
            ("168.5000.00", "168.5000.00"),
            ("081.9229.07", "081.9229.07"),
            ("065.7443.14", "065.7443.14"),
        ],
    )
    def test_numeric_suffix_preserved(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("100.0001.HM", "100.0001.HM"),
            ("100.0001.N4", "100.0001.N4"),
            ("100.0001.C35", "100.0001.C35"),
            ("100.0001.35", "100.0001.35"),
            ("100.0001.39", "100.0001.39"),
            ("100.0001.01", "100.0001.01"),
            ("100.0001.06", "100.0001.06"),
        ],
    )
    def test_material_suffix_preserved(self, input_text, expected):
        assert ReynaersProfile.parse_profile_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text",
        [
            "",
            "hello world",
            "K51 8143",
        ],
    )
    def test_no_match(self, input_text):
        assert ReynaersProfile.parse_profile_code(input_text) == ""


class TestReynaersHardware:

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("061.6634.ZC", "061.6634.ZC"),
            ("065.6566.59 7021-2", "065.6566.XX"),
        ],
    )
    def test_color_codes(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("061.6461.--", "061.6461.--"),
            ("0S0.2703.--", "0S0.2703.--"),
        ],
    )
    def test_double_dash(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("069.6831.04", "069.6831.04"),
            ("168.5000.00", "168.5000.00"),
            ("169.8748.04", "169.8748.04"),
        ],
    )
    def test_numeric_suffix(self, input_text, expected):
        assert ReynaersProfile.parse_hardware_code(input_text) == expected

    @pytest.mark.parametrize(
        "input_text",
        [
            "",
            "hello",
            "K51 8143",
        ],
    )
    def test_no_match(self, input_text):
        assert ReynaersProfile.parse_hardware_code(input_text) == ""


class TestReynaersSpecialCodes:

    def test_dual_color_69(self):
        result = ReynaersProfile.parse_profile_code("408.0014.69 W:59 7047-2+Z:59 7021-2")
        assert result == "408.0014.XX"

    def test_consistent_profile_and_hardware(self):
        """Profil i okucie dają ten sam wynik."""
        codes = [
            "061.6634.ZC",
            "0S0.2703.--",
            "069.6831.04",
            "065.6566.59 7021-2",
        ]
        for code in codes:
            assert ReynaersProfile.parse_profile_code(code) == ReynaersProfile.parse_hardware_code(
                code
            )


class TestParseHardwareCode:
    def test_listwa_dymoszczelna_zwraca_pusty(self):
        assert AluProfProfile.parse_hardware_code("DOMATIC - Listwa dymoszczelna 600mm") == ""

    def test_wycofane_listwa_zwraca_pusty(self):
        assert (
            AluProfProfile.parse_hardware_code("(WYCOFANE) DOMATIC - Listwa dymoszczelna 500 mm")
            == ""
        )

    def test_kod_z_sufiksem_mm_czyszczony(self):
        assert AluProfProfile.parse_hardware_code("80004326 1200mm") == "80004326"

    def test_kolnierz_opis_zachowany(self):
        assert AluProfProfile.parse_hardware_code("Kołek rozporowy") == "Kołek rozporowy"


class TestFormatHardwareDesc:
    def test_lacznik_z_wkretem_rozklada_kody(self):
        result = AluProfProfile.format_hardware_desc("Łącznik z wkrętem (80122109 +80372710)")
        assert "80122109" in result
        assert "80372710" in result
        assert "Łącznik z wkrętem" in result

    def test_zwykly_opis_bez_zmian(self):
        assert AluProfProfile.format_hardware_desc("Łącznik 42 mm") == "Łącznik 42 mm"

    def test_pusty_zwraca_myslnik(self):
        assert AluProfProfile.format_hardware_desc("") == "—"


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
