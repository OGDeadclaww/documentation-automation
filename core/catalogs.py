# core/catalogs.py
"""
Moduł odpowiedzialny za wyszukiwanie katalogów systemowych i okuć.

Zawiera logikę:
- wyszukiwania katalogów PDF dla systemów (Reynaers, Aluprof, itp.)
- wyszukiwania kart katalogowych dla okuć
- określania statusu aktualności katalogu
"""

import re
import os
import datetime
from typing import Optional, Dict, Tuple

from config import CATALOGS_PATH, RELATIVE_DEPTH_TO_BASE


# ==========================================
# KONFIGURACJA
# ==========================================

VENDOR_CATALOG_FOLDERS = {
    "reynaers": "Reynaers",
    "aluprof": "Aluprof",
    "yawal": "Yawal",
    "aliplast": "Aliplast",
}


# ==========================================
# HELPERS — STATUS KATALOGU
# ==========================================


def get_catalog_status(date_obj: datetime.datetime) -> Tuple[str, str]:
    """
    Zwraca (status_icon, status_text) na podstawie różnicy dat.

    - Do 3 miesięcy:   🟢 Aktualny
    - 3-6 miesięcy:    🟡 Do weryfikacji
    - Powyżej 6 mcy:   🔴 Nieaktualny
    """
    now = datetime.datetime.now()
    delta_days = (now - date_obj).days

    if delta_days <= 90:  # ~3 miesiące
        return "🟢", "Aktualny"
    elif delta_days <= 180:  # ~6 miesięcy
        return "🟡", "Do weryfikacji"
    else:
        return "🔴", "Nieaktualny"


def _normalize_system_name(text: str) -> str:
    """Normalizuje nazwę systemu do porównań."""
    return re.sub(r"[\s\-_.]", "", text).lower()


def _extract_date_from_catalog_filename(filepath: str) -> datetime.datetime:
    """
    Wyciąga datę z nazwy pliku katalogu.

    Szuka wzorców:
    - DD.MM.YYYY
    - MM_YYYY lub MM.YYYY
    - YYYY (rok)
    - Fallback: data modyfikacji pliku
    """
    name = os.path.basename(filepath)

    # Pattern: DD.MM.YYYY
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", name)
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # Pattern: MM_YYYY lub MM.YYYY
    m = re.search(r"(\d{2})[._](\d{4})", name)
    if m:
        try:
            return datetime.datetime(int(m.group(2)), int(m.group(1)), 1)
        except ValueError:
            pass

    # Pattern: YYYY
    m = re.search(r"(20\d{2})", name)
    if m:
        try:
            return datetime.datetime(int(m.group(1)), 1, 1)
        except ValueError:
            pass

    # Fallback
    return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))


# ==========================================
# KATALOGI SYSTEMOWE
# ==========================================


def find_system_catalog(vendor_key: str, sys_name: str) -> Optional[Dict]:
    """
    Szuka katalogu systemowego PDF dla danego dostawcy i systemu.

    Logika dopasowania (od najbardziej precyzyjnej):
    1. Nazwa pliku zaczyna się od sys_name
    2. Nazwa pliku zawiera sys_name
    3. Nazwa pliku zawiera sys_name bez separatorów

    Status zależy od świeżości (3msc/6msc).

    Returns:
        Dict z kluczami: name, date, path, status_icon, status_text
        lub None jeśli nie znaleziono
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return None

    catalog_dir = os.path.join(CATALOGS_PATH, vendor_folder)
    if not os.path.isdir(catalog_dir):
        print(f"⚠️ Brak folderu katalogów: {catalog_dir}")
        return None

    # Pobierz wszystkie PDF
    try:
        all_pdfs = [
            os.path.join(catalog_dir, f)
            for f in os.listdir(catalog_dir)
            if f.lower().endswith(".pdf")
            and os.path.isfile(os.path.join(catalog_dir, f))
        ]
    except PermissionError:
        print(f"⚠️ Brak dostępu do: {catalog_dir}")
        return None

    if not all_pdfs:
        return None

    sys_normalized = _normalize_system_name(sys_name)
    special_marks = ["bp", "ei", "dpa"]
    found_special = [m for m in special_marks if m in sys_normalized]

    matches = []

    for pdf_path in all_pdfs:
        filename = os.path.basename(pdf_path)
        filename_normalized = _normalize_system_name(filename)

        score = 10

        if sys_normalized == filename_normalized:
            score = 1
        elif found_special and any(m in filename_normalized for m in found_special):
            if sys_normalized in filename_normalized:
                score = 2
        elif filename_normalized.startswith(sys_normalized):
            score = 3
        elif sys_normalized in filename_normalized:
            score = 4

        if score < 10:
            matches.append((pdf_path, score))

    if not matches:
        return None

    # Sortuj: najlepszy score + najnowsza data
    matches.sort(
        key=lambda x: (x[1], -_extract_date_from_catalog_filename(x[0]).timestamp())
    )
    best_path, best_score = matches[0]

    date_obj = _extract_date_from_catalog_filename(best_path)
    date_str = date_obj.strftime("%d.%m.%Y")
    status_icon, status_text = get_catalog_status(date_obj)

    # Ścieżka relatywna
    best_norm = best_path.replace("\\", "/")
    catalogs_norm = CATALOGS_PATH.replace("\\", "/")

    if best_norm.lower().startswith(catalogs_norm.lower()):
        suffix = best_norm[len(catalogs_norm) :].lstrip("/")
        rel_path = f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}".replace(" ", "%20")
    else:
        rel_path = best_norm.replace(" ", "%20")

    return {
        "name": sys_name.upper(),
        "date": date_str,
        "path": rel_path,
        "status_icon": status_icon,
        "status_text": status_text,
    }


# ==========================================
# OKUCIA — KARTY KATALOGOWE
# ==========================================


def find_hardware_catalog_page(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> str:
    """
    Szuka strony katalogowej (PDF) dla konkretnego okucia.

    Struktura:
      Katalogi/{Vendor}/{SYS_NAME_UPPERCASE}/{hw_code}*.pdf

    Returns:
        Relatywna ścieżka MD lub '#' jeśli nie znaleziono.
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return "#"

    sys_folder = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder)

    if not os.path.isdir(hw_dir):
        return "#"

    code_normalized = hw_code.replace(" ", "_").replace(".", "").lower()

    try:
        all_files = os.listdir(hw_dir)
        candidates = [
            f
            for f in all_files
            if os.path.isfile(os.path.join(hw_dir, f))
            and os.path.splitext(f)[1].lower() == ".pdf"
            and f.lower().replace("_", "").replace(".", "").startswith(code_normalized)
        ]

        if not candidates:
            return "#"

        filename = candidates[0]
        rel_path = (
            f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{vendor_folder}/{sys_folder}/{filename}"
        )
        return rel_path.replace(" ", "%20")

    except PermissionError:
        return "#"


def build_hardware_catalog_link(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> Tuple[str, bool]:
    """
    Wylicza link do PDF okucia w katalogu.

    Logika:
    1. Szukaj rzeczywistego pliku pasującego do kodu
    2. Jeśli znajdziesz → zwróć link (file_exists=True)
    3. Jeśli nie → zwróć fallback {kod}_obrobka.pdf (file_exists=False)

    Returns:
        (link_relatywny, czy_plik_istnieje)
    """
    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return "#", False

    sys_folder_upper = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder_upper)

    if not os.path.isdir(hw_dir):
        code_normalized = hw_code.replace(" ", "_")
        fallback_filename = f"{code_normalized}_obrobka.pdf"
        rel_link = f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{vendor_folder}/{sys_folder_upper}/{fallback_filename}"
        return rel_link.replace(" ", "%20"), False

    code_search = hw_code.replace(" ", "").replace(".", "").lower()

    try:
        all_files = os.listdir(hw_dir)
        pdf_files = [f for f in all_files if f.lower().endswith(".pdf")]

        matching_files = [
            f
            for f in pdf_files
            if f.lower().replace("_", "").replace(".", "").startswith(code_search)
        ]

        if matching_files:
            found_filename = matching_files[0]
            rel_link = f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{vendor_folder}/{sys_folder_upper}/{found_filename}"
            return rel_link.replace(" ", "%20"), True

    except PermissionError:
        pass

    # Fallback
    code_normalized = hw_code.replace(" ", "_")
    fallback_filename = f"{code_normalized}_obrobka.pdf"
    rel_link = f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{vendor_folder}/{sys_folder_upper}/{fallback_filename}"
    return rel_link.replace(" ", "%20"), False
