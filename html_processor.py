# html_processor.py
"""
Przetwarzanie plików HTML z obrazkami.
Parsowanie RK_images.html (rzuty) i LP_images.html (profile, okucia).
"""
import os
import shutil
from collections import defaultdict

from bs4 import BeautifulSoup

from config import PREFERRED_EXT_ORDER, CONFLICTS_DIR, ENABLE_CONFLICT_MODE
from vendors import clean


# ============================================
# UTILITY PLIKOWE
# ============================================

def find_existing_file(images_dir: str, filename_from_html: str) -> str:
    """
    Szuka pliku obrazka na dysku, próbując różne rozszerzenia.
    HTML może wskazywać na .jpg, ale plik może być .png.
    
    Args:
        images_dir: Folder z obrazkami
        filename_from_html: Nazwa pliku z HTML (np. "img3.jpg")
    
    Returns:
        str: Rzeczywista nazwa pliku lub None
    """
    base, _ = os.path.splitext(filename_from_html)
    candidates = [filename_from_html] + [base + ext for ext in PREFERRED_EXT_ORDER]

    for candidate in candidates:
        if os.path.exists(os.path.join(images_dir, candidate)):
            return candidate
    return None


def choose_preferred_filename(filenames: list) -> str:
    """
    Wybiera preferowany plik z listy (wg kolejności rozszerzeń).
    
    Args:
        filenames: Lista nazw plików
    
    Returns:
        str: Najlepsza nazwa pliku lub ""
    """
    if not filenames:
        return ""

    def rank(fn):
        ext = os.path.splitext(fn)[1].lower()
        return PREFERRED_EXT_ORDER.index(ext) if ext in PREFERRED_EXT_ORDER else 999

    return sorted(filenames, key=rank)[0]


def ensure_conflicts_dir(base_dir: str) -> str:
    """
    Tworzy folder na konflikty (duplikaty).
    
    Args:
        base_dir: Folder bazowy
    
    Returns:
        str: Ścieżka do folderu konfliktów
    """
    conflicts_dir = os.path.join(base_dir, CONFLICTS_DIR)
    os.makedirs(conflicts_dir, exist_ok=True)
    return conflicts_dir


# ============================================
# PARSOWANIE HTML
# ============================================

def _parse_html(html_path: str) -> BeautifulSoup:
    """
    Wczytuje i parsuje plik HTML.
    
    Args:
        html_path: Ścieżka do pliku HTML
    
    Returns:
        BeautifulSoup: Sparsowany dokument
    
    Raises:
        FileNotFoundError: Gdy brak pliku
    """
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Brak pliku HTML: {html_path}")

    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        return BeautifulSoup(f.read(), "html.parser")


# ============================================
# RZUTY (RK_images)
# ============================================

def get_rk_images_from_html(html_path: str) -> list:
    """
    Wyciąga listę nazw obrazków z RK_images.html.
    
    Args:
        html_path: Ścieżka do RK_images.html
    
    Returns:
        list: Lista nazw plików (np. ["img0.jpg", "img1.jpg", ...])
    """
    if not os.path.exists(html_path):
        print(f"❌ Brak pliku: {html_path}")
        return []

    soup = _parse_html(html_path)
    images = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            images.append(os.path.basename(src))

    return images


def rename_views(positions, rk_images, rk_images_dir, prefix, output_dir):
    """
    Kopiuje i zmienia nazwy rzutów pozycji.
    
    Mapowanie: pozycja N → obrazek o indeksie (N-1)*2 w RK_images.
    
    Args:
        positions: Lista numerów pozycji (np. ["1", "2", "5"])
        rk_images: Lista obrazków z RK HTML
        rk_images_dir: Folder źródłowy z obrazkami
        prefix: Prefiks nazwy (np. "Klatka_")
        output_dir: Folder docelowy
    
    Returns:
        int: Liczba skopiowanych plików
    """
    os.makedirs(output_dir, exist_ok=True)
    renamed = 0
    skipped = 0

    for pos_id in positions:
        try:
            pos_num = int(pos_id)
        except ValueError:
            skipped += 1
            continue

        rk_index = (pos_num - 1) * 2
        if rk_index >= len(rk_images):
            skipped += 1
            continue

        old_filename = rk_images[rk_index]
        old_path = os.path.join(rk_images_dir, old_filename)

        # Szukaj z różnymi rozszerzeniami
        if not os.path.exists(old_path):
            root, _ = os.path.splitext(old_filename)
            for ext in PREFERRED_EXT_ORDER:
                alt_path = os.path.join(rk_images_dir, root + ext)
                if os.path.exists(alt_path):
                    old_path = alt_path
                    old_filename = root + ext
                    break

        if not os.path.exists(old_path):
            skipped += 1
            continue

        _, ext = os.path.splitext(old_filename)
        new_filename = f"{prefix}Poz_{pos_id}{ext}"
        new_path = os.path.join(output_dir, new_filename)

        shutil.copy2(old_path, new_path)
        renamed += 1

    print(f"✅ Rzuty: skopiowano {renamed}, pominięto {skipped}")
    return renamed


# ============================================
# PROFILE (LP_images)
# ============================================

def _find_code_in_row(tds, img_td_index, parse_fn):
    """
    Szuka kodu w komórkach wiersza (lewo → prawo od obrazka).
    
    Args:
        tds: Lista elementów <td>
        img_td_index: Indeks komórki z obrazkiem
        parse_fn: Funkcja parsująca kod (np. vendor.parse_profile_code)
    
    Returns:
        str: Znaleziony tekst z kodem lub ""
    """
    # Szukaj w lewo
    for j in range(img_td_index - 1, -1, -1):
        txt = clean(tds[j].get_text())
        if parse_fn(txt):
            return txt

    # Szukaj w prawo
    for j in range(img_td_index + 1, len(tds)):
        txt = clean(tds[j].get_text())
        if parse_fn(txt):
            return txt

    return ""


def _find_code_in_neighbors(all_rows, row_idx, parse_fn):
    """
    Szuka kodu w sąsiednich wierszach (gdy kod i obrazek
    są w osobnych <tr>).
    
    Sprawdza: 1 wiersz wyżej, 1 niżej, 2 wyżej.
    
    Args:
        all_rows: Lista wszystkich <tr>
        row_idx: Indeks bieżącego wiersza
        parse_fn: Funkcja parsująca kod
    
    Returns:
        str: Znaleziony kod lub ""
    """
    # Sprawdź wiersz POWYŻEJ
    if row_idx > 0:
        prev_tr = all_rows[row_idx - 1]
        if not prev_tr.find("img"):
            for td in prev_tr.find_all("td"):
                txt = clean(td.get_text())
                code = parse_fn(txt)
                if code:
                    print(f"    🔗 Kod z wiersza powyżej: '{txt}'")
                    return code

    # Sprawdź wiersz PONIŻEJ
    if row_idx + 1 < len(all_rows):
        next_tr = all_rows[row_idx + 1]
        if not next_tr.find("img"):
            for td in next_tr.find_all("td"):
                txt = clean(td.get_text())
                code = parse_fn(txt)
                if code:
                    print(f"    🔗 Kod z wiersza poniżej: '{txt}'")
                    return code

    # Sprawdź 2 wiersze WYŻEJ
    if row_idx > 1:
        prev2_tr = all_rows[row_idx - 2]
        if not prev2_tr.find("img"):
            for td in prev2_tr.find_all("td"):
                txt = clean(td.get_text())
                code = parse_fn(txt)
                if code:
                    print(f"    🔗 Kod z 2 wiersze wyżej: '{txt}'")
                    return code

    return ""


def rename_profiles_from_lp_html(html_path, images_dir, output_dir, vendor_profile):
    """
    Parsuje LP_images.html, rozpoznaje kody profili i kopiuje obrazki
    z nowymi nazwami.
    
    Obsługuje dwa scenariusze HTML:
    - Kod i obrazek w tym samym <tr>
    - Kod i obrazek w sąsiednich <tr>
    
    Args:
        html_path: Ścieżka do LP_images.html
        images_dir: Folder z obrazkami (LP_images.files)
        output_dir: Folder docelowy
        vendor_profile: Klasa dostawcy
    
    Returns:
        int: Liczba skopiowanych plików
    """
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")

    soup = _parse_html(html_path)

    print(f"    DEBUG: Szukam profili w HTML: {html_path}")
    print(f"    DEBUG: Folder obrazków: {images_dir}")
    print(f"    DEBUG: Folder wyjściowy: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    basecode_to_all = defaultdict(set)
    renamed = 0
    skipped = 0

    all_rows = soup.find_all("tr")
    parse_fn = vendor_profile.parse_profile_code

    for row_idx, tr in enumerate(all_rows):
        img = tr.find("img")
        if not img:
            continue

        src = img.get("src")
        if not src:
            continue

        old_filename_html = os.path.basename(src)
        existing_filename = find_existing_file(images_dir, old_filename_html)
        if not existing_filename:
            print(f"    ❌ Nie znaleziono pliku: {old_filename_html}")
            skipped += 1
            continue

        # Szukaj kodu w tym samym wierszu
        tds = tr.find_all("td")
        img_td = img.find_parent("td")
        code_text = ""

        if img_td in tds:
            idx = tds.index(img_td)
            code_text = _find_code_in_row(tds, idx, parse_fn)

        # Szukaj w sąsiednich wierszach
        base_code = parse_fn(code_text) if code_text else ""
        if not base_code:
            base_code = _find_code_in_neighbors(all_rows, row_idx, parse_fn)

        if not base_code:
            row_text = clean(tr.get_text())[:100]
            print(f"    ⚠️ Nie sparsowano kodu dla: {old_filename_html} (tekst: '{row_text}')")
            skipped += 1
            continue

        print(f"    ✓ Profil: {base_code} → {existing_filename}")

        old_path = os.path.join(images_dir, existing_filename)
        _, ext = os.path.splitext(existing_filename)
        new_filename = f"{base_code}{ext.lower()}"
        new_path = os.path.join(output_dir, new_filename)

        if not os.path.exists(new_path):
            shutil.copy2(old_path, new_path)
            renamed += 1
        basecode_to_all[base_code].add(new_filename)

    print(f"\n✅ Profile: skopiowano {renamed}, pominięto {skipped}")

    # Podsumowanie
    print(f"\n    📋 Znalezione kody profili:")
    for code in sorted(basecode_to_all.keys()):
        print(f"       {code}")

    # Obsługa konfliktów
    if ENABLE_CONFLICT_MODE:
        _handle_conflicts(basecode_to_all, output_dir)

    return renamed


# ============================================
# OKUCIA / AKCESORIA (LP_images)
# ============================================

def build_hardware_mapping_from_lp_html(html_path, images_dir, vendor_profile):
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")

    soup = _parse_html(html_path)
    tmp = defaultdict(set)
    parse_fn = vendor_profile.parse_hardware_code

    # ═══════════════════════════════════════════════
    # DEBUG: Pokaż co widzi parser
    # ═══════════════════════════════════════════════
    print(f"\n    DEBUG HW mapping: Parsowanie {html_path}")
    found_any = False

    for tr in soup.find_all("tr"):
        img = tr.find("img")
        if not img:
            continue

        src = img.get("src")
        if not src:
            continue

        real_fn = find_existing_file(images_dir, os.path.basename(src))
        if not real_fn:
            continue

        tds = tr.find_all("td")
        img_td = img.find_parent("td")
        code_text = ""

        if img_td in tds:
            idx = tds.index(img_td)

            # DEBUG: Pokaż wszystkie komórki
            for j, td in enumerate(tds):
                td_text = clean(td.get_text())
                if td_text:
                    marker = " ← IMG" if j == idx else ""
                    hw_result = parse_fn(td_text)
                    print(f"      TD[{j}]: '{td_text}' → hw: '{hw_result}'{marker}")

            for j in range(idx - 1, -1, -1):
                txt = clean(tds[j].get_text())
                if parse_fn(txt):
                    code_text = txt
                    break
            if not code_text:
                for j in range(idx + 1, len(tds)):
                    txt = clean(tds[j].get_text())
                    if parse_fn(txt):
                        code_text = txt
                        break

        code_hw = parse_fn(code_text, color_suffix=None)

        if code_hw:
            found_any = True
            print(f"    ✓ HW: {code_hw} → {real_fn}")
            tmp[code_hw].add(real_fn)
        else:
            row_text = clean(tr.get_text())[:80]
            if row_text.strip():
                print(f"    ⚠️ Nie sparsowano HW: '{row_text}'")
    # ═══════════════════════════════════════════════

    if not found_any:
        print(f"\n    ❌ NIE ZNALEZIONO ŻADNYCH OKUĆ W HTML!")
        print(f"    Sprawdź czy LP_images.html zawiera okucia")

    out = {}
    for code_hw, files in tmp.items():
        out[code_hw] = choose_preferred_filename(list(files))

    # DEBUG: Pokaż mapowanie
    print(f"\n    DEBUG HW mapping wynik:")
    for code, fn in sorted(out.items()):
        print(f"       {code} → {fn}")
    if not out:
        print(f"       (pusto)")

    return out


def rename_hardware(hardware_codes, code_to_srcfile, srcdir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    renamed = 0
    skipped = 0

    for code_hw in hardware_codes.keys():
        src_fn = code_to_srcfile.get(code_hw)

        # Fallback: kod z X ↔ bez X
        if not src_fn and code_hw.endswith("X"):
            src_fn = code_to_srcfile.get(code_hw[:-1])
        elif not src_fn:
            src_fn = code_to_srcfile.get(code_hw + "X")

        if not src_fn:
            print(f"    ⚠️ Brak obrazka dla: {code_hw}")
            skipped += 1
            continue

        src_path = os.path.join(srcdir, src_fn)
        if not os.path.exists(src_path):
            skipped += 1
            continue

        _, ext = os.path.splitext(src_fn)
        new_filename = f"{code_hw}{ext.lower()}"
        new_path = os.path.join(output_dir, new_filename)

        if not os.path.exists(new_path):
            shutil.copy2(src_path, new_path)
            print(f"    ✓ {code_hw} → {new_filename}")
            renamed += 1

    print(f"✅ Okucia/Akcesoria: skopiowano {renamed}, pominięto {skipped}")
    return renamed


# ============================================
# KONFLIKTY
# ============================================

def _handle_conflicts(basecode_to_all, output_dir):
    """
    Przenosi duplikaty do folderu _conflicts/.
    Zostawia preferowany plik, resztę przenosi.
    
    Args:
        basecode_to_all: Mapowanie {kod: {pliki}}
        output_dir: Folder z plikami
    """
    conflicts_dir = ensure_conflicts_dir(output_dir)
    moved = 0
    multi = 0

    for base_code, names_set in basecode_to_all.items():
        names = sorted(list(names_set))
        if len(names) <= 1:
            continue

        multi += 1
        main_name = choose_preferred_filename(names)

        for fn in names:
            if fn == main_name:
                continue

            src_path = os.path.join(output_dir, fn)
            if not os.path.exists(src_path):
                continue

            dst_path = os.path.join(conflicts_dir, fn)

            # Unikaj nadpisywania
            if os.path.exists(dst_path):
                root, ext = os.path.splitext(fn)
                k = 2
                while True:
                    alt = f"{root}__dup{k}{ext}"
                    dst_path = os.path.join(conflicts_dir, alt)
                    if not os.path.exists(dst_path):
                        break
                    k += 1

            shutil.move(src_path, dst_path)
            moved += 1

    print(
        f"✅ Konflikty profili: {multi} kodów miało duplikaty, "
        f"przeniesiono {moved} do {CONFLICTS_DIR}/"
    )