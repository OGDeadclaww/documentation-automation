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
        Parsuje kod profilu z tekstu.
        
        Args:
            code_text: Surowy tekst z HTML/CSV (np. "K51 8143 4R8017")
        
        Returns:
            str: Znormalizowany kod (np. "K518143") lub "" jeśli nie rozpoznano
        """
        raise NotImplementedError(
            f"{cls.NAME}.parse_profile_code() nie zaimplementowane"
        )

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
    """
    Parser kodów Aluprof.
    
    Profile:
        "K51 8143 4R8017" → "K518143"
        "K51 8395"        → "K518395"
        "120 470"         → "120470"   (bez prefiksu K)
    
    Okucia:
        "8000 965 D"      → "8000965X" (kolor → X)
        "8000 2590"       → "80002590" (brak koloru)
        "8000 4431"       → "80004431"
        "967 D"           → "967X"
    """
    NAME = "Aluprof"
    KEY = "aluprof"

    # Profile: K## #### (z opcjonalnym sufiksem 4R...)
    PROFILE_K_RE = re.compile(r"\bK(\d{2})\s*(\d{4})\b", re.IGNORECASE)
    
    # Profile: ### ### lub ### #### (bez prefiksu K)
    PROFILE_BARE_RE = re.compile(r"\b(\d{2,3})\s+(\d{3,4})\b")

    # Okucia: grupy cyfr z opcjonalnym sufiksem koloru
    HARDWARE_RE = re.compile(
        r"\b(\d{3,4})\s+(\d{1,4})\s*([A-Z]\d?|[A-Z]{1,2}\d)?\b",
        re.IGNORECASE
    )

    # Okucia: krótki format (np. "967 D")
    HARDWARE_SHORT_RE = re.compile(
        r"\b(\d{3,6})\s+([A-Z]\d?)\b",
        re.IGNORECASE
    )

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        """
        Parsuje kod profilu Aluprof.
        
        Przykłady:
            "K51 8143 4R8017" → "K518143"
            "K12 0470"        → "K120470"
            "120 470"         → "120470"
            "brak kodu"       → ""
        """
        t = clean(code_text).upper()

        # Wariant 1: Z prefiksem K (np. "K51 8143")
        m = cls.PROFILE_K_RE.search(t)
        if m:
            return f"K{m.group(1)}{m.group(2)}"

        # Wariant 2: Bez prefiksu K (np. "120 470")
        m = cls.PROFILE_BARE_RE.search(t)
        if m:
            combined = m.group(1) + m.group(2)
            if 5 <= len(combined) <= 6:
                return combined

        return ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        """
        Parsuje kod okucia Aluprof.
        Dodaje sufiks X gdy wykryto kod koloru.
        
        Przykłady:
            "8000 965 D"    → "8000965X"   (kolor D → X)
            "8000 969 B4"   → "8000969X"   (kolor B4 → X)
            "8000 2590"     → "80002590"   (brak koloru)
            "8000 4431"     → "80004431"
            "8010 544 B4"   → "8010544X"
            "967 D"         → "967X"       (krótki format)
            
        Args:
            code_text: Surowy tekst
            color_suffix: Wymuszony kolor (jeśli None, wykrywa z tekstu)
        """
        t = clean(code_text)

        # Próbuj pełny format: #### #### [kolor]
        m = cls.HARDWARE_RE.search(t)
        if m:
            part1 = m.group(1)
            part2 = m.group(2)
            color = m.group(3) or ""

            # Czy jest kolor (z tekstu lub wymuszony)?
            has_color = bool(color) or bool(color_suffix)

            if has_color:
                return f"{part1}{part2}X"
            
            # Brak koloru - dopełnij zerami jeśli trzeba
            if len(part1) == 4 and len(part2) < 4:
                return f"{part1}{part2.zfill(4)}"
            return f"{part1}{part2}"

        # Próbuj krótki format: ### [kolor] (np. "967 D")
        m = cls.HARDWARE_SHORT_RE.search(t)
        if m:
            part1 = m.group(1)
            return f"{part1}X"

        return ""


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
    "reynaers": AluProfProfile,   # Taki sam format jak Aluprof
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