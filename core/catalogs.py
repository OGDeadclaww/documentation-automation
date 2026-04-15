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

    Strategia wyboru (od najlepszego):
      1. Dokładna nazwa + data w nazwie pliku (najnowsza data wygrywa)
      2. Dokładna nazwa + jakikolwiek sufiks cyfrowy/datowy
      3. Dokładna nazwa bez daty (plain match)
      4. Nazwa zawiera sys_name + specjalny marker (EI, BP, DPA)
      5. Nazwa zawiera sys_name gdziekolwiek
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

    # BUG FIX #1: Nowa inteligentna funkcja ekstrakcji daty z nazwy pliku
    def _extract_date_from_name(filename: str) -> datetime.datetime | None:
        """
        Próbuje wyekstrahować datę z nazwy pliku.
        Zwraca datetime jeśli znaleziono, None jeśli brak daty w nazwie.
        """
        # Format: DD.MM.RRRR lub DD-MM-RRRR lub DD_MM_RRRR (np. 12.09.2025)
        m = re.search(r"(\d{2})[-._](\d{2})[-._](\d{4})", filename)
        if m:
            try:
                return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

        # Format: RRRR-MM-DD, RRRR.MM.DD, RRRR_MM_DD
        m = re.search(r"(\d{4})[-._](\d{2})[-._](\d{2})", filename)
        if m:
            try:
                return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        return None  # Brak daty w nazwie pliku

    def _get_file_mtime(filepath: str) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

    sys_normalized = _normalize(sys_name)
    special_marks = ["bp", "ei", "dpa"]
    found_special = [m for m in special_marks if m in sys_normalized]

    # BUG FIX #1: Przepisana logika scoringu
    # Niższy score = lepsze dopasowanie
    # Priorytety:
    #   1 = dokładna nazwa + data w nazwie (NAJLEPSZY)
    #   2 = dokładna nazwa + sufiks datowy/numeryczny
    #   3 = dokładna nazwa bez daty (plain)
    #   4 = zawiera sys_name + special marker (EI/BP/DPA)
    #   5 = zawiera sys_name gdziekolwiek
    #  10 = brak dopasowania (odrzucony)

    matches = []

    for pdf_path in all_pdfs:
        filename = os.path.basename(pdf_path)
        name_no_ext = os.path.splitext(filename)[0]
        filename_normalized = _normalize(name_no_ext)

        score = 10  # domyślnie odrzucony

        if filename_normalized == sys_normalized:
            # Dokładna nazwa bez żadnych dodatków (plain)
            score = 3

        elif filename_normalized.startswith(sys_normalized):
            # Nazwa pliku zaczyna się od sys_name + coś
            remainder = filename_normalized[len(sys_normalized) :]

            # Sprawdź czy data jest w ORYGINALNEJ nazwie (przed normalizacją)
            has_date_in_name = _extract_date_from_name(name_no_ext) is not None

            if has_date_in_name:
                # Najlepsze dopasowanie: dokładna nazwa + data
                score = 1
            elif re.match(r"^[\d]+$", remainder):
                # Sufiks czysto numeryczny (bez interpunkcji — po normalizacji)
                score = 2
            else:
                # Inne sufiksy
                score = 4

        elif sys_normalized in filename_normalized:
            # sys_name gdzieś w środku nazwy pliku
            if found_special and any(m in filename_normalized for m in found_special):
                score = 4
            else:
                score = 5

        if score < 10:
            matches.append((pdf_path, score))

    if not matches:
        return None

    # BUG FIX #1: Sortowanie dwupoziomowe
    # Poziom 1: score (rosnąco — niższy = lepszy)
    # Poziom 2: data w nazwie pliku (malejąco — nowszy = lepszy)
    #           Jeśli brak daty w nazwie → używamy daty modyfikacji pliku
    def _sort_key(item):
        pdf_path, score = item
        filename = os.path.basename(pdf_path)
        name_no_ext = os.path.splitext(filename)[0]
        date_from_name = _extract_date_from_name(name_no_ext)
        if date_from_name is not None:
            effective_date = date_from_name
        else:
            effective_date = _get_file_mtime(pdf_path)
        return (score, -effective_date.timestamp())

    matches.sort(key=_sort_key)
    best_path, best_score = matches[0]

    # Ustal datę do wyświetlenia (preferuj datę z nazwy)
    best_name_no_ext = os.path.splitext(os.path.basename(best_path))[0]
    date_from_name = _extract_date_from_name(best_name_no_ext)
    date_obj = date_from_name if date_from_name is not None else _get_file_mtime(best_path)
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

    # Szukamy pliku PDF dla danego kodu okucia
    safe_hw_code = hw_code.replace(" ", "_")
    pdf_filename = f"{safe_hw_code}_obrobka.pdf"
    pdf_path = os.path.join(hw_dir, pdf_filename)

    if os.path.isfile(pdf_path):
        suffix = os.path.join(vendor_folder, sys_folder_upper, pdf_filename).replace("\\", "/")
        rel_path = url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}")
        return rel_path, True

    # Fallback: szukaj bez _obrobka
    pdf_filename_plain = f"{safe_hw_code}.pdf"
    pdf_path_plain = os.path.join(hw_dir, pdf_filename_plain)
    if os.path.isfile(pdf_path_plain):
        suffix = os.path.join(vendor_folder, sys_folder_upper, pdf_filename_plain).replace(
            "\\", "/"
        )
        rel_path = url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{suffix}")
        return rel_path, True

    # Brak pliku — zwróć link do folderu systemu
    folder_suffix = os.path.join(vendor_folder, sys_folder_upper, "").replace("\\", "/")
    rel_path = url_encode(f"{RELATIVE_DEPTH_TO_BASE}/Katalogi/{folder_suffix}")
    return rel_path, False
