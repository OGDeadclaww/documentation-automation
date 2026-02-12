import os
import re
import csv
import shutil
from collections import defaultdict
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import json
import getpass
import socket
from datetime import datetime
from config import (
    BASE_PATH,
    PROJECTS_IMAGES,
    IMAGES_DB,
    OUTPUT_VIEWS_DIR,
    OUTPUT_PROFILES_DIR,
    OUTPUT_HARDWARE_DIR,
    CONFLICTS_DIR,
    ENABLE_CONFLICT_MODE,
    PREFERRED_EXT_ORDER,
    MAX_PREFIX_LENGTH,
    POZ_LINE_RE,
    SECTION_RE,
    KNOWN_SYSTEMS
)
from vendors import (
    clean,
    VendorProfile,
    AluProfProfile,
    GenericProfile,
    VENDOR_PROFILES,
    get_vendor_by_key,
    list_vendors,
)
from auth import check_authorization, log_audit
from gui import (
    select_vendor,
    select_file,
    select_project_from_list,
    select_folder,
    get_project_prefix_from_met,
    validate_and_choose_system,
    confirm_detected_colors,
)

def get_positions_from_csv(csv_path):
    positions = []
    try:
        with open(csv_path, "r", encoding="cp1250", errors="replace") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if not row:
                    continue
                line = ";".join(row)
                if "Poz." in line and "MB-" in line:
                    match = POZ_LINE_RE.search(line)
                    if match:
                        positions.append(match.group(1))
    except Exception as e:
        print(f"⚠️ Błąd odczytu CSV (cp1250): {e}, próbuję UTF-8...")
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                line = ";".join(row)
                if "Poz." in line and "MB-" in line:
                    match = POZ_LINE_RE.search(line)
                    if match:
                        positions.append(match.group(1))
    return positions

def extract_system_from_csv(csv_path):
    try:
        with open(csv_path, "r", encoding="cp1250", errors="replace") as f:
            reader = list(csv.reader(f, delimiter=";"))
    except Exception:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = list(csv.reader(f, delimiter=";"))
    
    for i, row in enumerate(reader):
        if any("System:" in str(cell) for cell in row):
            # Sprawdź WSZYSTKIE komórki w następnym wierszu
            if i + 1 < len(reader):
                for cell in reader[i + 1]:
                    cell_clean = clean(cell).upper()
                    if re.match(r"MB-\d+", cell_clean, re.IGNORECASE):
                        # Usuń warianty (HI/SI/EI)
                        system_clean = re.sub(r"\s*(HI|SI|EI|HS).*", "", cell_clean, flags=re.IGNORECASE).strip().lower()
                        system_clean = re.sub(r"\s+", "", system_clean)
                        return system_clean
    return None

def find_existing_file(images_dir: str, filename_from_html: str):
    base, _ = os.path.splitext(filename_from_html)
    candidates = [filename_from_html] + [base + ext for ext in PREFERRED_EXT_ORDER]
    for c in candidates:
        if os.path.exists(os.path.join(images_dir, c)):
            return c
    return None

#def extract_color_code_from_csv(csv_path):
    """Wykrywa kod koloru z sekcji 'Kolor profili:'"""
    try:
        with open(csv_path, "r", encoding="cp1250", errors="replace") as f:
            reader = list(csv.reader(f, delimiter=";"))
    except Exception:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = list(csv.reader(f, delimiter=";"))
    
    for i, row in enumerate(reader):
        if any("Kolor profili:" in str(cell) for cell in row):
            for j in range(i, min(i + 3, len(reader))):
                for cell in reader[j]:
                    cell_clean = clean(cell).upper()
                    if re.match(r"^[A-Z0-9]{1,3}$", cell_clean) and cell_clean not in ["X", "Y", "KOLOR", "PROFILI"]:
                        print(f"✓ Wykryto kod koloru: {cell_clean}")
                        return cell_clean
    return None


def choose_preferred_filename(filenames: list) -> str:
    if not filenames:
        return ""
    def rank(fn):
        ext = os.path.splitext(fn)[1].lower()
        return PREFERRED_EXT_ORDER.index(ext) if ext in PREFERRED_EXT_ORDER else 999
    return sorted(filenames, key=rank)[0]

def ensure_conflicts_dir(base_dir: str) -> str:
    conflicts_dir = os.path.join(base_dir, CONFLICTS_DIR)
    os.makedirs(conflicts_dir, exist_ok=True)
    return conflicts_dir

def get_rk_images_from_html(html_path):
    if not os.path.exists(html_path):
        print(f"❌ Brak pliku: {html_path}")
        return []
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    images = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        base_name = os.path.basename(src)
        images.append(base_name)
    return images

def rename_views(positions, rk_images, rk_images_dir, prefix, output_dir):
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

def rename_profiles_from_lp_html(html_path, images_dir, output_dir, vendor_profile):
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Brak pliku HTML: {html_path}")
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")
    os.makedirs(output_dir, exist_ok=True)
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    print(f"    DEBUG: Szukam profili w HTML: {html_path}")
    print(f"    DEBUG: Folder obrazków: {images_dir}")
    print(f"    DEBUG: Folder wyjściowy: {output_dir}")

    basecode_to_all = defaultdict(set)
    renamed = 0
    skipped = 0

    # ═══════════════════════════════════════════════════════════════
    # NOWA LOGIKA: Buduj mapę kod→obrazek z SĄSIEDNICH wierszy
    # HTML z Aluprofa ma strukturę:
    #   <tr> kod profilu </tr>
    #   <tr> obrazek     </tr>
    # LUB:
    #   <tr> kod + obrazek (w tym samym wierszu) </tr>
    # ═══════════════════════════════════════════════════════════════

    all_rows = soup.find_all("tr")
    print(f"    DEBUG: Znaleziono {len(all_rows)} wierszy <tr>")

    for row_idx, tr in enumerate(all_rows):
        img = tr.find("img")
        tds = tr.find_all("td")

        # ─── SCENARIUSZ A: Kod i obrazek W TYM SAMYM wierszu ───
        if img:
            src = img.get("src")
            if not src:
                continue
            old_filename_html = os.path.basename(src)
            existing_filename = find_existing_file(images_dir, old_filename_html)
            if not existing_filename:
                print(f"    ❌ Nie znaleziono pliku: {old_filename_html}")
                skipped += 1
                continue

            # Szukaj kodu w komórkach tego wiersza
            code_text = ""
            img_td = img.find_parent("td")
            if img_td in tds:
                idx = tds.index(img_td)
                # Szukaj w lewo
                for j in range(idx - 1, -1, -1):
                    txt = clean(tds[j].get_text())
                    if vendor_profile.parse_profile_code(txt):
                        code_text = txt
                        break
                # Szukaj w prawo
                if not code_text:
                    for j in range(idx + 1, len(tds)):
                        txt = clean(tds[j].get_text())
                        if vendor_profile.parse_profile_code(txt):
                            code_text = txt
                            break

            # ─── SCENARIUSZ B: Kod w SĄSIEDNIM wierszu ───
            if not code_text:
                # Sprawdź wiersz POWYŻEJ
                if row_idx > 0:
                    prev_tr = all_rows[row_idx - 1]
                    if not prev_tr.find("img"):  # Poprzedni nie ma obrazka
                        for td in prev_tr.find_all("td"):
                            txt = clean(td.get_text())
                            if vendor_profile.parse_profile_code(txt):
                                code_text = txt
                                print(f"    🔗 Kod z wiersza powyżej: '{txt}'")
                                break

                # Sprawdź wiersz PONIŻEJ
                if not code_text and row_idx + 1 < len(all_rows):
                    next_tr = all_rows[row_idx + 1]
                    if not next_tr.find("img"):  # Następny nie ma obrazka
                        for td in next_tr.find_all("td"):
                            txt = clean(td.get_text())
                            if vendor_profile.parse_profile_code(txt):
                                code_text = txt
                                print(f"    🔗 Kod z wiersza poniżej: '{txt}'")
                                break

            base_code = vendor_profile.parse_profile_code(code_text)
            if not base_code:
                # Ostatnia szansa - sprawdź 2 wiersze wyżej
                if row_idx > 1:
                    prev2_tr = all_rows[row_idx - 2]
                    if not prev2_tr.find("img"):
                        for td in prev2_tr.find_all("td"):
                            txt = clean(td.get_text())
                            base_code = vendor_profile.parse_profile_code(txt)
                            if base_code:
                                print(f"    🔗 Kod z 2 wiersze wyżej: '{txt}'")
                                break

            if not base_code:
                row_text = clean(tr.get_text())[:100]
                print(f"    ⚠️ Nie sparsowano kodu dla: {old_filename_html} (tekst: '{row_text}')")
                skipped += 1
                continue
            else:
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

    if ENABLE_CONFLICT_MODE:
        conflicts_dir = ensure_conflicts_dir(output_dir)
        moved = 0
        multi = 0
        for base_code, names_set in basecode_to_all.items():
            names = sorted(list(names_set))
            if len(names) > 1:
                multi += 1
                main_name = choose_preferred_filename(names)
                for fn in names:
                    if fn == main_name:
                        continue
                    src_path = os.path.join(output_dir, fn)
                    if not os.path.exists(src_path):
                        continue
                    dst_path = os.path.join(conflicts_dir, fn)
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
        print(f"✅ Konflikty profili: {multi} kodów miało duplikaty, przeniesiono {moved} do {CONFLICTS_DIR}/")
    return renamed

#def rename_profiles_from_lp_html(html_path, images_dir, output_dir, vendor_profile):
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Brak pliku HTML: {html_path}")
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")
    os.makedirs(output_dir, exist_ok=True)
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    print(f"    DEBUG: Szukam profili w HTML: {html_path}")
    print(f"    DEBUG: Folder obrazków: {images_dir}")
    print(f"    DEBUG: Folder wyjściowy: {output_dir}")

    basecode_to_all = defaultdict(set)
    renamed = 0
    skipped = 0
    
    # ═══════════════════════════════════════════════════════════════
    # NOWY DEBUG: Pokaż WSZYSTKIE wiersze z obrazkami
    # ═══════════════════════════════════════════════════════════════
    all_rows = soup.find_all("tr")
    print(f"\n    DEBUG: Znaleziono {len(all_rows)} wierszy <tr> w HTML")
    print(f"    DEBUG: Szukam K518143...\n")
    
    for row_idx, tr in enumerate(all_rows):
        # Sprawdź czy gdziekolwiek w wierszu jest "8143"
        row_text = clean(tr.get_text())
        if "8143" in row_text:
            print(f"    🔍 ZNALEZIONO '8143' w wierszu {row_idx}!")
            print(f"       Pełny tekst wiersza: '{row_text[:200]}'")
            
            # Pokaż wszystkie <td>
            tds = tr.find_all("td")
            for td_idx, td in enumerate(tds):
                td_text = clean(td.get_text())
                has_img = "📷" if td.find("img") else "  "
                print(f"       TD[{td_idx}] {has_img}: '{td_text}'")
            
            # Sprawdź czy jest obrazek
            img = tr.find("img")
            if img:
                print(f"       IMG src: {img.get('src', 'BRAK')}")
            else:
                print(f"       ❌ BRAK <img> w tym wierszu!")
            print()
    # ═══════════════════════════════════════════════════════════════
    
    for tr in soup.find_all("tr"):
        img = tr.find("img")
        if not img:
            continue
        src = img.get("src")
        if not src:
            continue
        old_filename_html = os.path.basename(src)
        existing_filename = find_existing_file(images_dir, old_filename_html)
        if not existing_filename:
            print(f"    ❌ Nie znaleziono: {old_filename_html}")
            skipped += 1
            continue
        tds = tr.find_all("td")
        img_td = img.find_parent("td")
        code_text = ""
        if img_td in tds:
            idx = tds.index(img_td)
            
            # ═══════════════════════════════════════════════════════
            # DEBUG: Pokaż co widzi parser dla każdego obrazka
            # ═══════════════════════════════════════════════════════
            print(f"    --- Obrazek: {old_filename_html} ---")
            for j, td in enumerate(tds):
                marker = " ← IMG" if j == idx else ""
                td_text = clean(td.get_text())
                parse_result = vendor_profile.parse_profile_code(td_text)
                print(f"      TD[{j}]: '{td_text}' → parse: '{parse_result}'{marker}")
            # ═══════════════════════════════════════════════════════
            
            for j in range(idx - 1, -1, -1):
                txt = clean(tds[j].get_text())
                if vendor_profile.parse_profile_code(txt):
                    code_text = txt
                    break
            if not code_text:
                for j in range(idx + 1, len(tds)):
                    txt = clean(tds[j].get_text())
                    if vendor_profile.parse_profile_code(txt):
                        code_text = txt
                        break
        base_code = vendor_profile.parse_profile_code(code_text)
        if not base_code:
            print(f"    ⚠️ Nie sparsowano kodu z: '{code_text}'")
            skipped += 1
            continue
        else:
            print(f"    ✓ Znaleziono profil: {base_code}")
        old_path = os.path.join(images_dir, existing_filename)
        _, ext = os.path.splitext(existing_filename)
        new_filename = f"{base_code}{ext.lower()}"
        new_path = os.path.join(output_dir, new_filename)
        if not os.path.exists(new_path):
            shutil.copy2(old_path, new_path)
            renamed += 1
        basecode_to_all[base_code].add(new_filename)
    
    print(f"\n✅ Profile: skopiowano {renamed}, pominięto {skipped}")
    
    # ═══════════════════════════════════════════════════════════════
    # PODSUMOWANIE: Pokaż wszystkie znalezione kody
    # ═══════════════════════════════════════════════════════════════
    print(f"\n    📋 Wszystkie znalezione kody profili:")
    for code in sorted(basecode_to_all.keys()):
        print(f"       {code}")
    
    expected = ["K518143", "K518395", "K518139"]
    missing = [e for e in expected if e not in basecode_to_all]
    if missing:
        print(f"\n    ❌ BRAKUJĄCE kody: {', '.join(missing)}")
    # ═══════════════════════════════════════════════════════════════
    
    if ENABLE_CONFLICT_MODE:
        conflicts_dir = ensure_conflicts_dir(output_dir)
        moved = 0
        multi = 0
        for base_code, names_set in basecode_to_all.items():
            names = sorted(list(names_set))
            if len(names) > 1:
                multi += 1
                main_name = choose_preferred_filename(names)
                for fn in names:
                    if fn == main_name:
                        continue
                    src_path = os.path.join(output_dir, fn)
                    if not os.path.exists(src_path):
                        continue
                    dst_path = os.path.join(conflicts_dir, fn)
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
        print(f"✅ Konflikty profili: {multi} kodów miało duplikaty, przeniesiono {moved} do {CONFLICTS_DIR}/")
    return renamed

#def rename_profiles_from_lp_html(html_path, images_dir, output_dir, vendor_profile):
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Brak pliku HTML: {html_path}")
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")
    os.makedirs(output_dir, exist_ok=True)
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    print(f"    DEBUG: Szukam profili w HTML: {html_path}")
    print(f"    DEBUG: Folder obrazków: {images_dir}")
    print(f"    DEBUG: Folder wyjściowy: {output_dir}")

    basecode_to_all = defaultdict(set)
    renamed = 0
    skipped = 0
    for tr in soup.find_all("tr"):
        img = tr.find("img")
        if not img:
            continue
        src = img.get("src")
        if not src:
            continue
        old_filename_html = os.path.basename(src)
        existing_filename = find_existing_file(images_dir, old_filename_html)
        if not existing_filename:
            print(f"    ❌ Nie znaleziono: {old_filename_html}")
            skipped += 1
            continue
        tds = tr.find_all("td")
        img_td = img.find_parent("td")
        code_text = ""
        if img_td in tds:
            idx = tds.index(img_td)
            for j in range(idx - 1, -1, -1):
                txt = clean(tds[j].get_text())
                if vendor_profile.parse_profile_code(txt):
                    code_text = txt
                    break
            if not code_text:
                for j in range(idx + 1, len(tds)):
                    txt = clean(tds[j].get_text())
                    if vendor_profile.parse_profile_code(txt):
                        code_text = txt
                        break
        base_code = vendor_profile.parse_profile_code(code_text)
        if not base_code:
            print(f"    ⚠️ Nie sparsowano kodu z: '{code_text}'")
            skipped += 1
            continue
        else:
            print(f"    ✓ Znaleziono profil: {base_code}")
        old_path = os.path.join(images_dir, existing_filename)
        _, ext = os.path.splitext(existing_filename)
        new_filename = f"{base_code}{ext.lower()}"
        new_path = os.path.join(output_dir, new_filename)
        if not os.path.exists(new_path):
            shutil.copy2(old_path, new_path)
            renamed += 1
        basecode_to_all[base_code].add(new_filename)
    print(f"✅ Profile: skopiowano {renamed}, pominięto {skipped}")
    if ENABLE_CONFLICT_MODE:
        conflicts_dir = ensure_conflicts_dir(output_dir)
        moved = 0
        multi = 0
        for base_code, names_set in basecode_to_all.items():
            names = sorted(list(names_set))
            if len(names) > 1:
                multi += 1
                main_name = choose_preferred_filename(names)
                for fn in names:
                    if fn == main_name:
                        continue
                    src_path = os.path.join(output_dir, fn)
                    if not os.path.exists(src_path):
                        continue
                    dst_path = os.path.join(conflicts_dir, fn)
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
        print(f"✅ Konflikty profili: {multi} kodów miało duplikaty, przeniesiono {moved} do {CONFLICTS_DIR}/")
    return renamed

def parse_hardware_from_csv(csv_path, vendor_profile, color_code=None):
    color_codes = extract_color_codes_from_csv(csv_path)
    if not color_codes:
        color_code = None
    elif len(color_codes) == 1:
        color_code = list(color_codes)[0]
    else:
        print(f"⚠️ Wiele kodów kolorów w pliku CSV: {color_codes}")
    
    try:
        rows = list(csv.reader(open(csv_path, "r", encoding="cp1250", errors="replace"), delimiter=";"))
    except Exception:
        rows = list(csv.reader(open(csv_path, "r", encoding="utf-8", errors="ignore"), delimiter=";"))
    
    hardware_codes = {}
    current_pos = None
    current_section = None
    
    for i in range(len(rows)):
        r = [clean(c) for c in rows[i]]
        line = ";".join(r)
        
        mpos = POZ_LINE_RE.search(line)
        if mpos and "MB-" in line:
            current_pos = mpos.group(1)
            current_section = None
            continue
        
        if not current_pos:
            continue
        
        if r and r[0] and SECTION_RE.match(r[0]):
            sec = SECTION_RE.match(r[0]).group(1).capitalize()
            current_section = sec if sec in ["Akcesoria", "Okucia"] else None
            continue
        
        if current_section not in ["Akcesoria", "Okucia"]:
            continue
        
        joined = " ".join([x for x in r if x])
        code_hw = vendor_profile.parse_hardware_code(joined, color_suffix=color_code)
        if not code_hw:
            continue
        
        desc = ""
        if i + 1 < len(rows):
            next_row = [clean(c) for c in rows[i + 1]]
            next_desc = next_row[0] if next_row else ""
            if next_desc and not vendor_profile.parse_hardware_code(next_desc, color_suffix=color_code):
                desc = next_desc
        
        if code_hw not in hardware_codes:
            hardware_codes[code_hw] = {"desc": desc, "positions": set()}
        hardware_codes[code_hw]["positions"].add(current_pos)
    
    return hardware_codes


def build_hardware_mapping_from_lp_html(html_path, images_dir, vendor_profile, color_code=None):
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Brak pliku HTML: {html_path}")
    if not os.path.isdir(images_dir):
        raise FileNotFoundError(f"Brak folderu: {images_dir}")
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    tmp = defaultdict(set)
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
            for j in range(idx - 1, -1, -1):
                txt = clean(tds[j].get_text())
                if vendor_profile.parse_hardware_code(txt):
                    code_text = txt
                    break
            if not code_text:
                for j in range(idx + 1, len(tds)):
                    txt = clean(tds[j].get_text())
                    if vendor_profile.parse_hardware_code(txt):
                        code_text = txt
                        break
        code_hw = vendor_profile.parse_hardware_code(code_text, color_suffix=None)
        if not code_hw:
            continue
        tmp[code_hw].add(real_fn)
    out = {}
    for code_hw, files in tmp.items():
        files = list(files)
        out[code_hw] = choose_preferred_filename(files)
    return out

def rename_hardware(hardware_codes, code_to_srcfile, srcdir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    renamed = 0
    skipped = 0
    for code_hw in hardware_codes.keys():
        src_fn = code_to_srcfile.get(code_hw)
        if not src_fn:
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
            renamed += 1
    print(f"✅ Okucia/Akcesoria: skopiowano {renamed}, pominięto {skipped}")
    return renamed

def extract_additional_profiles_from_csv(csv_path, vendor_profile):
    """
    Wyciąga profile z sekcji 'Profile dodatkowe' w CSV.
    
    Returns:
        set: Zbiór kodów profili (np. {"K518139", "K120470"})
    """
    try:
        rows = list(csv.reader(open(csv_path, "r", encoding="cp1250", errors="replace"), delimiter=";"))
    except Exception:
        rows = list(csv.reader(open(csv_path, "r", encoding="utf-8", errors="ignore"), delimiter=";"))
    
    profiles = set()
    in_additional_section = False
    
    for row in rows:
        r = [clean(c) for c in row]
        line = ";".join(r)
        
        # Wykryj sekcję
        if re.search(r"Profile\s+dodatkowe", line, re.IGNORECASE):
            in_additional_section = True
            continue
        
        # Koniec sekcji (następna sekcja lub pusta linia)
        if in_additional_section and r and r[0] and re.match(r"^(Akcesoria|Okucia|Izolacyjność)", r[0], re.IGNORECASE):
            in_additional_section = False
            continue
        
        # Parsuj profile w sekcji
        if in_additional_section:
            for cell in r:
                code = vendor_profile.parse_profile_code(cell)
                if code:
                    profiles.add(code)
    
    return profiles

def extract_color_codes_from_csv(csv_path):
    """
    Wykrywa WSZYSTKIE kody kolorów z wiersza 'Kolor profili:'.
    Obsługuje format CSV z kolorami rozdzielonymi średnikami.
    
    Przykład:
    "B4 [brązowy];I4 [czarny];D [srebrny]" → ["B4", "I4", "D"]
    """
    try:
        with open(csv_path, "r", encoding="cp1250", errors="replace") as f:
            reader = list(csv.reader(f, delimiter=";"))
    except Exception:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = list(csv.reader(f, delimiter=";"))
    
    colors = []
    
    for i, row in enumerate(reader):
        if any("Kolor profili:" in str(cell) for cell in row):
            for cell in row:
                if not cell or "Kolor profili:" in cell:
                    continue
                
                cell_upper = str(cell).upper()
                
                # Wyczyść znaki specjalne i polskie opisy
                cell_clean = re.sub(r'[\^\\[\]\'"\(\)*]', ' ', cell_upper)
                cell_clean = re.sub(r'\b(CZARNY|BRĄZOWY|ANODA|SREBRNY|SREBRNA|BIAŁY|MAT|MATOWY|LAKIEROWANY|NIETYPOWY|STANDARD)\b', '', cell_clean)
                cell_clean = cell_clean.strip()
                
                # KLUCZOWE: Split po średniku
                segments = [s.strip() for s in cell_clean.split(';') if s.strip()]
                
                for segment in segments:
                    # Pattern 1: Litera + cyfry (B4, I4, E6)
                    matches = re.findall(r'\b([A-Z]\d{1,2})\b', segment)
                    for m in matches:
                        if m not in ["X", "X1", "Y", "Y1"]:
                            colors.append(m)
                    
                    # Pattern 2: Pojedyncza litera (D, E, F, G, H)
                    matches = re.findall(r'(?:^|\s)([DBEFGH])(?:\s|$)', segment)
                    colors.extend(matches)
                    
                    # Pattern 3: ST (jeśli chcesz zachować)
                    # Odkomentuj jeśli ST to kod koloru:
                    # if 'ST' in segment and segment.strip() == 'ST':
                    #     colors.append('ST')
    
    # Usuń duplikaty zachowując kolejność
    seen = set()
    unique = [c for c in colors if not (c in seen or seen.add(c))]
    
    if unique:
        print(f"    🎨 Wykryte kody kolorów: {', '.join(unique)}")
    else:
        print(f"    ⚠️ Nie wykryto kodów kolorów")
    
    return unique

def main():
    print("=" * 60)
    print("REORGANIZACJA BAZY OBRAZKÓW (NOWA STRUKTURA)")
    print("=" * 60)
    
    check_authorization()
    
    print("\n[0/7] Wybierz dostawcę profili...")
    vendor_profile = select_vendor()
    if not vendor_profile:
        messagebox.showerror("Błąd", "Nie wybrano dostawcy.")
        return
    vendor_key = vendor_profile.KEY
    print(f"✓ Wybrano: {vendor_profile.NAME}\n")
    
    print("[1/7] Wybierz projekt...")
    projects_folder = os.path.join(BASE_PATH, "projects")
    project_name = select_project_from_list(projects_folder)
    if not project_name:
        messagebox.showerror("Błąd", "Nie wybrano projektu.")
        return
    print(f"✓ Wybrano: {project_name}\n")
    
    print("[2/7] Wybierz plik .MET...")
    met_file = select_file("MET", "Wybierz plik .MET")
    if not met_file:
        return
    print(f"✓ Wybrano: {os.path.basename(met_file)}\n")
    
    print("[3/7] Wybierz plik CSV...")
    csv_file = select_file("CSV", "Wybierz plik LP_dane.csv")
    if not csv_file:
        return
    print(f"✓ Wybrano: {os.path.basename(csv_file)}\n")
    print("    Wykrywanie koloru projektu...")
    confirm_detected_colors(csv_file)
    #detected_colors = extract_color_codes_from_csv(csv_file)  # Wywołaj NOWĄ funkcję
    #if detected_colors:
     #   print(f"    ✓ Wykryto {len(detected_colors)} kolory: {', '.join(detected_colors)}")
        #project_color = select_primary_color(detected_colors)  # Dialog wyboru
    #else:
     #   print("    ⚠️ Nie wykryto koloru - okucia bez sufiksu X")
      #  project_color = None
    #print(f"    → Kolor projektu: {project_color or 'BRAK'}\n")
    
    print("[4/7] Wybierz plik RK_images.html...")
    rk_html = select_file("HTML", "Wybierz RK_images.html")
    if not rk_html:
        return
    print(f"✓ Wybrano: {os.path.basename(rk_html)}\n")
    
    print("[5/7] Wybierz folder RK_images.files...")
    rk_images_dir = select_folder("Wybierz folder RK_images.files")
    if not rk_images_dir:
        return
    print(f"✓ Wybrano: {os.path.basename(rk_images_dir)}\n")
    
    print("[6/7] Wybierz plik LP_images.html...")
    lp_html = select_file("HTML", "Wybierz LP_images.html")
    if not lp_html:
        return
    print(f"✓ Wybrano: {os.path.basename(lp_html)}\n")
    
    print("[7/7] Wybierz folder LP_images.files...")
    lp_images_dir = select_folder("Wybierz folder LP_images.files")
    if not lp_images_dir:
        return
    print(f"✓ Wybrano: {os.path.basename(lp_images_dir)}\n")
    
    print("=" * 60)
    print(f"PRZETWARZANIE - Dostawca: {vendor_profile.NAME}")
    print("=" * 60)
    
    system = validate_and_choose_system(csv_file, extract_system_from_csv)
    if not system:
        messagebox.showerror("Błąd", "Nie podano systemu - przerywam.")
        return
    
    global OUTPUT_VIEWS_DIR, OUTPUT_PROFILES_DIR, OUTPUT_HARDWARE_DIR
    OUTPUT_VIEWS_DIR = os.path.join(PROJECTS_IMAGES, project_name, "views")
    OUTPUT_PROFILES_DIR = os.path.join(IMAGES_DB, vendor_key, "profiles", system)
    OUTPUT_HARDWARE_DIR = os.path.join(IMAGES_DB, vendor_key, "hardware")
    
    os.makedirs(OUTPUT_VIEWS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PROFILES_DIR, exist_ok=True)
    os.makedirs(OUTPUT_HARDWARE_DIR, exist_ok=True)
    
    print(f"\n📁 Zapisuję do:")
    print(f"  Views:    {OUTPUT_VIEWS_DIR}")
    print(f"  Profiles: {OUTPUT_PROFILES_DIR}")
    print(f"  Hardware: {OUTPUT_HARDWARE_DIR}\n")
    
    print("[KROK 1/4] Przetwarzanie rzutów...")
    prefix = get_project_prefix_from_met(met_file)
    positions = get_positions_from_csv(csv_file)
    print(f"✓ Znaleziono {len(positions)} pozycji")
    rk_images = get_rk_images_from_html(rk_html)
    print(f"✓ Znaleziono {len(rk_images)} obrazków w RK.html")
    rename_views(positions, rk_images, rk_images_dir, prefix, OUTPUT_VIEWS_DIR)
    
    print("\n[KROK 2/4] Przetwarzanie profili...")
    # Profile z HTML
    rename_profiles_from_lp_html(lp_html, lp_images_dir, OUTPUT_PROFILES_DIR, vendor_profile)

    # Profile dodatkowe z CSV
    additional_profiles = extract_additional_profiles_from_csv(csv_file, vendor_profile)
    if additional_profiles:
        print(f"⚠️ Znaleziono {len(additional_profiles)} profili dodatkowych w CSV: {', '.join(sorted(additional_profiles))}")
        print(f"   Upewnij się, że obrazki są w folderze LP_images.files")
    
    print("\n[KROK 3/4] Parsowanie okuć z CSV...")
    #print(f"    DEBUG: Przekazuję kolor: {project_color}")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)
    print(f"✓ Znaleziono {len(hardware_codes)} kodów okuć")
    
    print("\n[KROK 4/4] Przetwarzanie okuć...")
    code_to_srcfile = build_hardware_mapping_from_lp_html(lp_html, lp_images_dir, vendor_profile)  # ← Dodaj color_code
    rename_hardware(hardware_codes, code_to_srcfile, lp_images_dir, OUTPUT_HARDWARE_DIR)
    
    log_audit("IMAGES_PROCESSED", {"project": project_name, "vendor": vendor_key, "system": system, "positions": len(positions), "hardware": len(hardware_codes)})
    
    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)
    messagebox.showinfo("Sukces!", f"Obrazki przetworzone!\n\nProjekt: {project_name}\nSystem: {system}\nPozycje: {len(positions)}\nOkucia: {len(hardware_codes)}")

if __name__ == "__main__":
    main()
