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

        Przykłady:
            "K51 8143 4R8017" → "K518143"
            "K12 0470"        → "K120470"
            "K41 PL27 4R7016" → "K41PL27X"
            "120 470"         → "120470"
            "brak kodu"       → ""
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
            # Sufiks koloru = cyfra+litera+cyfry (np. "4R7016")
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
        """
        Parsuje kod okucia/akcesorium z tekstu.
        
        Args:
            code_text: Surowy tekst (np. "8000 965 D")
            color_suffix: Opcjonalny kod koloru (np. "B4", "D")
        
        Returns:
            str: Znormalizowany kod (np. "8000965X") lub "" jeśli nie rozpoznano
        """
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

    # Okucia: obsługuje mieszane kody alfanumeryczne
    # Grupa 1: kod bazowy (np. "8A022", "8000", "8010")
    # Grupa 2: druga część z opcjonalnym kolorem (np. "27I4", "965", "2590", "544 B4")
    HARDWARE_RE = re.compile(
        r"\b(\d[A-Z0-9]{2,5})\s+(\d+[A-Z]\d+|\d{1,4})\s*([A-Z]\d?|[A-Z]{1,2}\d)?\b",
        re.IGNORECASE
    )

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        """
        Parsuje kod okucia Aluprof.
        
        Przykłady:
            "8A022 27I4"    → "8A02227X"   (kolor I4 w środku → X)
            "8000 965 D"    → "8000965X"   (kolor D → X)
            "8000 969 B4"   → "8000969X"   (kolor B4 → X)
            "8000 2590"     → "80002590"   (brak koloru)
            "8000 4431"     → "80004431"
            "8010 544 B4"   → "8010544X"
            "967 D"         → "967X"       (krótki format)
        """
        t = clean(code_text).upper()
        if not t:
            return ""

        # ─── Pattern 1: Kolor WEWNĄTRZ drugiej części (np. "8A022 27I4") ───
        m_embedded = re.search(
            r"\b(\d[A-Z0-9]{2,5})\s+(\d+)([A-Z]\d*)(\d*)\b",
            t
        )
        if m_embedded:
            part1 = m_embedded.group(1)          # "8A022"
            digits_before = m_embedded.group(2)   # "27"
            color_letter = m_embedded.group(3)    # "I4" lub "I"
            digits_after = m_embedded.group(4)    # "" lub dodatkowe cyfry

            # Sprawdź czy to wygląda na kolor (litera + opcjonalna cyfra)
            if re.match(r"^[A-Z]\d?$", color_letter):
                # Kolor w środku → wyciągnij same cyfry + X
                all_digits = digits_before + digits_after
                return f"{part1}{all_digits}X"

        # ─── Pattern 2: Standardowy format (np. "8000 965 D") ───
        m_standard = re.search(
            r"\b(\d{3,4})\s+(\d{1,4})\s+([A-Z]\d?|[A-Z]{1,2}\d)\b",
            t
        )
        if m_standard:
            part1 = m_standard.group(1)
            part2 = m_standard.group(2)
            return f"{part1}{part2}X"

        # ─── Pattern 3: Bez koloru (np. "8000 4431") ───
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

        # ─── Pattern 4: Krótki format z kolorem (np. "967 D") ───
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

    CODE_RE = re.compile(
        r"\b(\d[A-Z0-9]\d)\.(\d{4})\.(\S+(?:\s+\S+)*)?",
        re.IGNORECASE
    )

    @classmethod
    def _is_ral_color(cls, suffix: str) -> bool:
        """
        Sprawdza czy sufiks to kolor RAL (zmienny per projekt).
        
        RAL:
            "59 7021-2"                    → True
            "69 W:59 7047-2+Z:59 7021-2"   → True
            
        Nie RAL (stały kod materiału/wariantu):
            "ZC", "HM", "N4", "C35"        → False
            "00", "04", "07", "14", "17"    → False
            "--"                            → False
        """
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
        
        Returns:
            tuple: (full_code_with_suffix, is_parseable) lub ("", False)
        """
        t = clean(code_text).upper()
        m = cls.CODE_RE.search(t)
        if not m:
            return ("", False)

        group = m.group(1)
        article = m.group(2)
        suffix = (m.group(3) or "").strip()

        base = f"{group}.{article}"

        if not suffix:
            # Brak sufiksu - nie powinno się zdarzyć ale obsłuż
            return (base, True)

        if cls._is_ral_color(suffix):
            # RAL → zamień na .XX
            return (f"{base}.XX", True)

        # Wszystko inne → zachowaj oryginalny sufiks
        return (f"{base}.{suffix}", True)

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        """
        Parsuje kod profilu Reynaers. Zachowuje oryginalny sufiks.
        
        Przykłady:
            "108.0081.59 7021-2"              → "108.0081.XX"
            "408.0014.69 W:59 7047-2+Z:7021"  → "408.0014.XX"
            "0S0.2703.--"                     → "0S0.2703.--"
            "061.6634.ZC"                     → "061.6634.ZC"
            "108.1874.17"                     → "108.1874.17"
            "069.6831.04"                     → "069.6831.04"
            "168.5000.00"                     → "168.5000.00"
            "081.9229.07"                     → "081.9229.07"
            "065.7443.14"                     → "065.7443.14"
            "xxx.xxxx.HM"                     → "xxx.xxxx.HM"
            "xxx.xxxx.N4"                     → "xxx.xxxx.N4"
            "xxx.xxxx.C35"                    → "xxx.xxxx.C35"
        """
        code, ok = cls._parse_code(code_text)
        return code if ok else ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        """
        Parsuje kod okucia Reynaers.
        
        Przykłady:
            "061.6634.ZC"         → "061.6634.ZC"
            "065.6566.59 7021-2"  → "065.6566.XX"
            "061.6461.--"         → "061.6461.--"
            "069.6831.04"         → "069.6831.04"
            "168.5000.00"         → "168.5000.00"
        """
        code, ok = cls._parse_code(code_text)
        return code if ok else ""

# ============================================
# GENERIC (fallback dla nieznanych dostawców)
# ============================================

class GenericProfile(VendorProfile):
    """
    Generyczny parser - fallback dla nieznanych dostawców.
    
    Profile:
        "A12 34567" → "A1234567"
    
    Okucia:
        "ABC-12345" → "ABC12345"
    """
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
    "aliplast": AluProfProfile,   # Taki sam format jak Aluprof
    "generic": GenericProfile,
}


def get_vendor_by_key(key: str) -> type:
    """
    Zwraca klasę dostawcy po kluczu.
    
    Args:
        key: Klucz dostawcy (np. "aluprof", "generic")
    
    Returns:
        Klasa VendorProfile
    
    Raises:
        KeyError: Gdy dostawca nieznany
    """
    if key not in VENDOR_PROFILES:
        available = ", ".join(VENDOR_PROFILES.keys())
        raise KeyError(
            f"Nieznany dostawca: '{key}'. Dostępni: {available}"
        )
    return VENDOR_PROFILES[key]


def list_vendors() -> list:
    """Zwraca listę (key, name) dostępnych dostawców."""
    return [(key, cls.NAME) for key, cls in VENDOR_PROFILES.items()]

# Szybki test
if __name__ == "__main__":
    tests = [
        ("8A022 27I4",   "8A02227X"),
        ("8000 965 D",   "8000965X"),
        ("8000 969 B4",  "8000969X"),
        ("8000 2590",    "80002590"),
        ("8000 4431",    "80004431"),
        ("8010 544 B4",  "8010544X"),
        ("8000 9732",    "80009732"),
        ("8000 977 B4",  "8000977X"),
        ("8000 989 B4",  "8000989X"),
        ("8010 4991",    "80104991"),
        ("8045 5040",    "80455040"),
        ("8032 2073",    "80322073"),
        ("8032 2077",    "80322077"),
        ("967 D",        "967X"),
        ("K51 8143",     ""),       # profil, nie okucie
        ("",             ""),
    ]

    for input_text, expected in tests:
        result = AluProfProfile.parse_hardware_code(input_text)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_text}' → '{result}' (oczekiwano: '{expected}')")