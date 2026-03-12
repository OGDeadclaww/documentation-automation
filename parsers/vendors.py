# vendors.py
import re


def clean(t):
    return " ".join(str(t or "").replace("\xa0", " ").split())


class VendorProfile:
    NAME = "Generic"
    KEY = "generic"

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        return ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        return ""


# --- ALUPROF ---
class AluProfProfile(VendorProfile):
    NAME = "Aluprof"
    KEY = "aluprof"

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        t = clean(code_text).upper()
        m = re.search(r"\bK(\d{2})\s*(\d{4})\b", t)
        if m:
            prefix, code = m.group(1), m.group(2)
            if re.search(r"\b\d[A-Z]\d{3,}\b", t):
                return f"K{prefix}{code}X"
            return f"K{prefix}{code}"
        return ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        # Wycinamy wymiary " 1200mm" z końcówek (np. uszczelki progowe)
        t = re.sub(r"\s+\d+mm\b", "", code_text, flags=re.IGNORECASE).strip()

        # Odrzucamy twarde śmieci "stronicowe" Logikala
        if "DRZWI_" in t or "OKNO_" in t or "SOLEC_" in t or "W edytorze systemu" in t:
            return ""

        # Zostawiamy oryginalną wielkość liter, bo upper() nam niszczył np "Wkręt do betonu"
        # Sprawdzamy czy to czysty tekst z małymi literami - jeśli tak, to jest to opis, zwracamy bez "upper" i cięcia spacji
        if any(c.islower() for c in t):
            return t

        # Jeśli to standardowy kod (same cyfry, duże litery)
        t_upper = clean(t).upper()
        clean_no_space = t_upper.replace(" ", "")

        m = re.search(r"\b(\d{4})\s*(\d{3})\d\s+[A-Z0-9]+\b", t_upper)
        if m:
            return f"{m.group(1)}{m.group(2)}X"

        m = re.search(r"\b(\d{3,4})\s+(\d{1,4})\s+([A-Z]\d?|[A-Z]{1,2}\d)\b", t_upper)
        if m:
            return f"{m.group(1)}{m.group(2)}X"

        m = re.search(r"\b(\d[A-Z0-9]{2,5})\s+(\d{1,4})\b", t_upper)
        if m:
            part1, part2 = m.group(1), m.group(2)
            if len(part1) == 4 and len(part2) < 4:
                return f"{part1}{part2.zfill(4)}"
            return f"{part1}{part2}"

        if re.search(r"\d+", clean_no_space) and len(clean_no_space) < 15:
            return clean_no_space

        return t


# --- REYNAERS ---
class ReynaersProfile(VendorProfile):
    NAME = "Reynaers"
    KEY = "reynaers"
    CODE_RE = re.compile(r"\b(\d[A-Z0-9]\d)\.(\d{4})\.(\S+(?:\s+\S+)*)?", re.IGNORECASE)

    @classmethod
    def _parse_code(cls, code_text: str) -> tuple:
        t = clean(code_text)
        qty_match = re.search(r"\s+[\d,.]+(?:x[\d,.]+)?\s*szt", t, re.IGNORECASE)
        if qty_match:
            t = t[: qty_match.start()]

        t = t.upper()
        m = cls.CODE_RE.search(t)
        if not m:
            return ("", False)

        base = f"{m.group(1)}.{m.group(2)}"
        suffix = (m.group(3) or "").strip()

        if not suffix:
            return (base, True)
        # RAL / Bicolor
        if re.search(r"\d{2}\s+\d{4}", suffix) or re.search(r"\d{2}\s+W:", suffix):
            return (f"{base}.XX", True)
        return (f"{base}.{suffix}", True)

    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        code, ok = cls._parse_code(code_text)
        return code if ok else ""

    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        code, ok = cls._parse_code(code_text)
        return code if ok else ""


# --- GENERIC ---
class GenericProfile(VendorProfile):
    NAME = "Inny / Generic"
    KEY = "generic"

    @classmethod
    def parse_profile_code(cls, t: str) -> str:
        return ""

    @classmethod
    def parse_hardware_code(cls, t: str, c=None) -> str:
        return ""


VENDOR_PROFILES = {
    "aluprof": AluProfProfile,
    "reynaers": ReynaersProfile,
    "aliplast": AluProfProfile,
    "generic": GenericProfile,
}


def get_vendor_by_key(key: str) -> type:
    if key not in VENDOR_PROFILES:
        raise KeyError(f"Nieznany dostawca: {key}")
    return VENDOR_PROFILES[key]


def list_vendors() -> list:
    return [(key, cls.NAME) for key, cls in VENDOR_PROFILES.items()]
