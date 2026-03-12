# core/catalogs.py
"""
Moduł odpowiedzialny za wyszukiwanie katalogów systemowych i okuć.

Zawiera logikę:
- wyszukiwania katalogów PDF dla systemów (Reynaers, Aluprof, itp.)
- wyszukiwania kart katalogowych dla okuć
- określania statusu aktualności katalogu
"""
import datetime
import os
import re


def url_encode(path_str: str) -> str:
    """Zamienia spacje na %20 w ścieżce."""
    return path_str.replace(" ", "%20")


def get_catalog_status(d_obj: datetime.datetime) -> tuple[str, str]:
    """
    Zwraca (status_icon, status_text) na podstawie różnicy dat.
    """
    now = datetime.datetime.now()
    delta_days = (now - d_obj).days

    if delta_days <= 180:  # 6 miesięcy
        return "🟢", "Aktualny"
    elif delta_days <= 365:  # 1 rok
        return "🟡", "Do weryfikacji"
    else:  # Powyżej roku
        return "🔴", "Nieaktualny"


def find_system_catalog(vendor_key: str, sys_name: str) -> dict | None:
    """
    Szuka katalogu systemowego PDF dla danego dostawcy i systemu.
    """
    from config import CATALOGS_PATH, RELATIVE_DEPTH_TO_BASE

    VENDOR_CATALOG_FOLDERS = {
        "reynaers": "Reynaers",
        "aluprof": "Aluprof",
        "yawal": "Yawal",
        "aliplast": "Aliplast",
    }

    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return None

    catalog_dir = os.path.join(CATALOGS_PATH, vendor_folder)
    if not os.path.isdir(catalog_dir):
        print(f"⚠️ Brak folderu katalogów: {catalog_dir}")
        return None

    try:
        all_pdfs = [
            os.path.join(catalog_dir, f)
            for f in os.listdir(catalog_dir)
            if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(catalog_dir, f))
        ]
    except PermissionError:
        return None

    if not all_pdfs:
        return None

    def _normalize(text: str) -> str:
        """Usuwa spacje, myślniki, kropki i podkreślenia do porównań."""
        return re.sub(r"[\s\-_.]", "", text).lower()

    sys_normalized = _normalize(sys_name)
    special_marks = ["bp", "ei", "dpa"]
    found_special = [m for m in special_marks if m in sys_normalized]

    matches = []

    for pdf_path in all_pdfs:
        filename = os.path.basename(pdf_path)
        name_no_ext = os.path.splitext(filename)[0]
        filename_normalized = _normalize(name_no_ext)

        score = 10

        # 1. Zmieniona punktacja priorytetów!
        if sys_normalized == filename_normalized:
            score = 2  # Goła nazwa bez daty dostaje 2 punkty
        elif found_special and any(m in filename_normalized for m in found_special):
            if sys_normalized in filename_normalized:
                score = 3
        elif filename_normalized.startswith(sys_normalized):
            remainder = filename_normalized[len(sys_normalized) :]
            if re.match(r"^[\d]+$", remainder):
                score = 1  # NAJWYŻSZY PRIORYTET: Nazwa + Data
            else:
                score = 4
        elif sys_normalized in filename_normalized:
            score = 5

        if score < 10:
            matches.append((pdf_path, score))

    if not matches:
        return None

    # NOWY INTELIGENTNY EKSTRAKTOR DAT
    def _extract_date(filepath: str) -> datetime.datetime:
        name = os.path.basename(filepath)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

        # Format: RRRR-MM-DD, RRRR.MM.DD, RRRR_MM_DD
        m = re.search(r"(\d{4})[-._](\d{2})[-._](\d{2})", name)
        if m:
            try:
                return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # Format: DD-MM-RRRR, DD.MM.RRRR, DD_MM_RRRR
        m = re.search(r"(\d{2})[-._](\d{2})[-._](\d{4})", name)
        if m:
            try:
                return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

        # Jeśli brak daty w nazwie, używamy daty modyfikacji pliku z Windows
        return mtime

    # Sortujemy: najpierw po trafności (score = 1 jest najlepszy), potem po dacie (najnowsze)
    matches.sort(key=lambda x: (x[1], -_extract_date(x[0]).timestamp()))
    best_path, best_score = matches[0]

    date_obj = _extract_date(best_path)
    date_str = date_obj.strftime("%d.%m.%Y")

    status_icon, status_text = get_catalog_status(date_obj)

    best_norm = best_path.replace("\\", "/")
    catalogs_norm = CATALOGS_PATH.replace("\\", "/")

    if best_norm.lower().startswith(catalogs_norm.lower()):
        suffix = best_norm[len(catalogs_norm) :].lstrip("/")
        rel_path = url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}")
    else:
        rel_path = url_encode(best_norm)

    return {
        "name": sys_name.upper(),
        "date": date_str,
        "path": rel_path,
        "status_icon": status_icon,
        "status_text": status_text,
    }


def find_base_hardware_catalog(vendor_key: str, catalog_type: str) -> dict | None:
    """
    Szuka ogólnego katalogu okuć (np. 'okucia 2 - drzwi') dla danego dostawcy.
    """
    from config import CATALOGS_PATH, RELATIVE_DEPTH_TO_BASE

    VENDOR_CATALOG_FOLDERS = {
        "reynaers": "Reynaers",
        "aluprof": "Aluprof",
        "yawal": "Yawal",
        "aliplast": "Aliplast",
    }

    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return None

    catalog_dir = os.path.join(CATALOGS_PATH, vendor_folder)
    if not os.path.isdir(catalog_dir):
        return None

    try:
        all_pdfs = [
            os.path.join(catalog_dir, f)
            for f in os.listdir(catalog_dir)
            if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(catalog_dir, f))
        ]
    except PermissionError:
        return None

    search_term = catalog_type.lower().replace(" ", "").replace("-", "")
    matches = []

    for pdf_path in all_pdfs:
        filename = os.path.basename(pdf_path).lower()
        name_no_ext = os.path.splitext(filename)[0]
        norm_name = name_no_ext.replace(" ", "").replace("-", "")

        if norm_name.startswith(search_term):
            matches.append(pdf_path)

    if not matches:
        return None

    # Sortowanie po dacie modyfikacji pliku (najnowszy pierwszy)
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    best_path = matches[0]

    date_ts = os.path.getmtime(best_path)
    date_str = datetime.datetime.fromtimestamp(date_ts).strftime("%d.%m.%Y")

    status_icon, status_text = "🟢", "Aktualny"

    best_norm = best_path.replace("\\", "/")
    catalogs_norm = CATALOGS_PATH.replace("\\", "/")

    if best_norm.lower().startswith(catalogs_norm.lower()):
        suffix = best_norm[len(catalogs_norm) :].lstrip("/")
        rel_path = url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}")
    else:
        rel_path = url_encode(best_norm)

    display_name = "Okucia Drzwiowe" if "drzwi" in catalog_type else "Okucia Okienne"

    return {
        "name": f"ALUPROF - {display_name}",
        "date": date_str,
        "path": rel_path,
        "status_icon": status_icon,
        "status_text": status_text,
    }


# ==========================================
# WYSZUKIWANIE OKUĆ (PRZYWRÓCONE)
# ==========================================


def build_hardware_catalog_link(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> tuple[str, bool]:
    """
    Wylicza link do PDF okucia w katalogu.
    Zwraca: (link_relatywny, czy_plik_istnieje)
    """
    import os

    from config import CATALOGS_PATH, RELATIVE_DEPTH_TO_BASE

    VENDOR_CATALOG_FOLDERS = {
        "reynaers": "Reynaers",
        "aluprof": "Aluprof",
        "yawal": "Yawal",
        "aliplast": "Aliplast",
    }

    vendor_folder = VENDOR_CATALOG_FOLDERS.get(vendor_key)
    if not vendor_folder:
        return "#", False

    sys_folder_upper = sys_name.upper()
    hw_dir = os.path.join(CATALOGS_PATH, vendor_folder, sys_folder_upper)

    code_normalized = hw_code.replace(" ", "_")
    fallback_filename = f"{code_normalized}_obrobka.pdf"
    fallback_link = (
        f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{vendor_folder}/{sys_folder_upper}/{fallback_filename}"
    )

    if not os.path.isdir(hw_dir):
        return url_encode(fallback_link), False

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
            return url_encode(rel_link), True

    except PermissionError:
        pass

    return url_encode(fallback_link), False


def find_hardware_catalog_page(
    vendor_key: str,
    sys_name: str,
    hw_code: str,
) -> str:
    """Kompatybilność wsteczna dla starego kodu"""
    link, _ = build_hardware_catalog_link(vendor_key, sys_name, hw_code)
    return link
