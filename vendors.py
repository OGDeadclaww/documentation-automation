# vendors.py
"""
Klasy dostawców profili (vendor profiles).
Odpowiadają za parsowanie kodów profili i okuć
specyficznych dla danego producenta (Aluprof, Reynaers, itp.).
"""
import re


def clean(t):
    """Czyści tekst: zamienia &nbsp; na spacje, usuwa wielokrotne spacje."""
    return " ".join(str(t or "").replace("\xa0", " ").split())


# ============================================
# KLASA BAZOWA
# ============================================

class VendorProfile:
    """
    Bazowa klasa dostawcy profili.
    Każdy dostawca MUSI nadpisać:
      - parse_profile_code()
      - parse_hardware_code()
    """
    NAME = "Generic"
    KEY = "generic"
    PROFILE_RE = None
    HARDWARE_RE = None

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        """
        Parsuje kod profilu Aluprof.
        """
        t = clean(code_text).upper()

        # Pattern 1: K## + 4 cyfry (np. "K51 8143")
        m = re.search(r"\bK(\d{2})\s*(\d{4})\b", t)
        if m:
            return f"K{m.group(1)}{m.group(2)}"

        # Pattern 2: K## + alfanumeryczny kod (np. "K41 PL27")
        m = re.search(r"\bK(\d{2})\s+([A-Z]{1,3}\d{1,4})\b", t)
        if m:
            prefix = m.group(1)
            code = m.group(2)
            has_color = bool(re.search(r"\b\d[A-Z]\d{3,}\b", t))
            if has_color:
                return f"K{prefix}{code}X"
            return f"K{prefix}{code}"

        # Pattern 3: Bez K (np. "120 470")
        m = re.search(r"\b(\d{2,3})\s+(\d{3,4})\b", t)
        if m:
            combined = m.group(1) + m.group(2)
            if 5 <= len(combined) <= 7:
                return combined

        return ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        raise NotImplementedError(
            f"{cls.NAME}.parse_hardware_code() nie zaimplementowane"
        )


# ============================================
# ALUPROF
# ============================================

class AluProfProfile(VendorProfile):
    NAME = "Aluprof"
    KEY = "aluprof"

    # Profile
    PROFILE_K_RE = re.compile(r"\bK(\d{2})\s*(\d{4})\b", re.IGNORECASE)
    PROFILE_BARE_RE = re.compile(r"\b(\d{2,3})\s+(\d{3,4})\b")

    # Okucia
    HARDWARE_RE = re.compile(
        r"\b(\d[A-Z0-9]{2,5})\s+(\d+[A-Z]\d+|\d{1,4})\s*([A-Z]\d?|[A-Z]{1,2}\d)?\b",
        re.IGNORECASE
    )

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        t = clean(code_text).upper()
        if not t:
            return ""

        # Pattern 1: Kolor WEWNĄTRZ (np. "8A022 27I4")
        m_embedded = re.search(
            r"\b(\d[A-Z0-9]{2,5})\s+(\d+)([A-Z]\d*)(\d*)\b",
            t
        )
        if m_embedded:
            part1 = m_embedded.group(1)
            digits_before = m_embedded.group(2)
            color_letter = m_embedded.group(3)
            digits_after = m_embedded.group(4)

            if re.match(r"^[A-Z]\d?$", color_letter):
                all_digits = digits_before + digits_after
                return f"{part1}{all_digits}X"

        # Pattern 2: Standard (np. "8000 965 D")
        m_standard = re.search(
            r"\b(\d{3,4})\s+(\d{1,4})\s+([A-Z]\d?|[A-Z]{1,2}\d)\b",
            t
        )
        if m_standard:
            part1 = m_standard.group(1)
            part2 = m_standard.group(2)
            return f"{part1}{part2}X"

        # Pattern 3: Bez koloru (np. "8000 4431")
        m_plain = re.search(
            r"\b(\d[A-Z0-9]{2,5})\s+(\d{1,4})\b",
            t
        )
        if m_plain:
            part1 = m_plain.group(1)
            part2 = m_plain.group(2)
            if color_suffix:
                return f"{part1}{part2}X"
            if len(part1) == 4 and len(part2) < 4:
                return f"{part1}{part2.zfill(4)}"
            return f"{part1}{part2}"

        # Pattern 4: Krótki (np. "967 D")
        m_short = re.search(
            r"\b(\d{3,6})\s+([A-Z]\d?)\b",
            t
        )
        if m_short:
            return f"{m_short.group(1)}X"

        return ""

# ============================================
# REYNAERS
# ============================================

class ReynaersProfile(VendorProfile):
    NAME = "Reynaers"
    KEY = "reynaers"

    # Regex wyłapujący format: 3cyfry.4cyfry.sufiks
    # Sufiks łapie wszystko do końca, dlatego musimy czyścić input przed użyciem tego regexa.
    CODE_RE = re.compile(
        r"\b(\d[A-Z0-9]\d)\.(\d{4})\.(\S+(?:\s+\S+)*)?",
        re.IGNORECASE
    )

    @classmethod
    def _is_ral_color(cls, suffix: str) -> bool:
        if not suffix:
            return False
        suffix = suffix.strip()
        # RAL: cyfra+cyfra+spacja+4cyfry (np. "59 7021-2")
        if re.search(r"\d{2}\s+\d{4}", suffix):
            return True
        # Dwukolorowy RAL: "69 W:59..."
        if re.search(r"\d{2}\s+W:", suffix):
            return True
        return False

    @classmethod
    def _parse_code(cls, code_text: str) -> tuple:
        """
        Parsuje kod Reynaers.
        """
        t = clean(code_text) # Nie robimy upper() od razu, żeby łatwiej znaleźć "szt"

        # --- FIX: Usuwanie "śmieci" ilościowych ---
        # Parser CSV skleja komórki, więc dostajemy np. "069.6831.04 5 szt A..B"
        # Musimy uciąć tekst przed ilością.
        # Wzorzec: spacja + (cyfry/przecinek/x) + spacja + "szt"
        # Np.: " 5 szt", " 4x2 szt", " 1,0 szt"
        qty_match = re.search(r"\s+[\d,.]+(?:x[\d,.]+)?\s*szt", t, re.IGNORECASE)
        if qty_match:
            # Ucinamy string w miejscu, gdzie zaczyna się ilość
            t = t[:qty_match.start()]

        t = t.upper() # Teraz bezpiecznie zamieniamy na wielkie litery

        m = cls.CODE_RE.search(t)
        if not m:
            return ("", False)

        group = m.group(1)
        article = m.group(2)
        suffix = (m.group(3) or "").strip()

        base = f"{group}.{article}"

        if not suffix:
            return (base, True)

        if cls._is_ral_color(suffix):
            # RAL → zamień na .XX
            return (f"{base}.XX", True)

        # Wszystko inne (np. 04, ZC, --) → zachowaj
        return (f"{base}.{suffix}", True)

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        code, ok = cls._parse_code(code_text)
        return code if ok else ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        code, ok = cls._parse_code(code_text)
        return code if ok else ""

# ============================================
# GENERIC
# ============================================

class GenericProfile(VendorProfile):
    NAME = "Inny / Generic"
    KEY = "generic"

    PROFILE_RE = re.compile(
        r"\b([A-Z]\d{2})\s*(\d{3,5})\b", re.IGNORECASE
    )
    HARDWARE_RE = re.compile(
        r"\b([0-9A-Z]{3,8})[\s\-/.](\d{1,5}[A-Z]?\d*)\b", re.IGNORECASE
    )

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        t = clean(code_text).upper()
        m = cls.PROFILE_RE.search(t)
        if not m:
            return ""
        return f"{m.group(1)}{m.group(2)}"

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        t = clean(code_text)
        m = cls.HARDWARE_RE.search(t)
        if not m:
            return ""
        part1 = m.group(1)
        part2 = m.group(2)
        has_color = bool(re.search(r"[A-Z]", part2)) or bool(color_suffix)
        if has_color:
            part2_clean = re.sub(r"[A-Z]+", "", part2)
            return f"{part1}{part2_clean}X"
        return f"{part1}{part2}"


# ============================================
# REJESTR DOSTAWCÓW
# ============================================

VENDOR_PROFILES = {
    "aluprof": AluProfProfile,
    "reynaers": ReynaersProfile,
    "aliplast": AluProfProfile,
    "generic": GenericProfile,
}


def get_vendor_by_key(key: str) -> type:
    if key not in VENDOR_PROFILES:
        available = ", ".join(VENDOR_PROFILES.keys())
        raise KeyError(
            f"Nieznany dostawca: '{key}'. Dostępni: {available}"
        )
    return VENDOR_PROFILES[key]


def list_vendors() -> list:
    return [(key, cls.NAME) for key, cls in VENDOR_PROFILES.items()]