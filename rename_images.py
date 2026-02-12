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
    AUTH_FILE,
    AUDIT_LOG,
    POZ_LINE_RE,
    SECTION_RE,
    KNOWN_SYSTEMS
)

def check_authorization():
    current_user = getpass.getuser()
    if not os.path.exists(AUTH_FILE):
        os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
        auth = {"authorized_editors": [current_user, "pawel.pisarski", "PawelPisarski"], "authorized_viewers": ["*"]}
        with open(AUTH_FILE, 'w', encoding='utf-8') as f:
            json.dump(auth, f, indent=2, ensure_ascii=False)
        return
    with open(AUTH_FILE, 'r', encoding='utf-8') as f:
        auth_data = json.load(f)
    if current_user not in auth_data.get('authorized_editors', []):
        messagebox.showerror("Brak uprawnień", f"Użytkownik '{current_user}' nie ma uprawnień.")
        exit(1)
    print(f"✅ Autoryzacja OK: {current_user}")

def log_audit(action, details):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    log_entry = {"timestamp": datetime.now().isoformat(), "user": getpass.getuser(), 
                 "hostname": socket.gethostname(), "action": action, "details": details}
    with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

# --- VENDOR PROFILES ---
class VendorProfile:
    NAME = "Generic"
    PROFILE_RE = None
    HARDWARE_RE = None
    COLOR_TOKEN_RE = None
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        raise NotImplementedError
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        raise NotImplementedError

class AluProfProfile(VendorProfile):
    NAME = "Aluprof"
    PROFILE_RE = re.compile(r"\b(K\d{2})\s*(\d{4})\b", re.IGNORECASE)
    
    # POPRAWIONY REGEX
    HARDWARE_RE = re.compile(
        r"\b([0-9A-Z]{3,6})\s+(\d{2,4})\s*([A-Z]\d?|[A-Z]{1,2}\d|\d[A-Z])?\b",
        re.IGNORECASE
    )
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        t = clean(code_text).upper()
        m = cls.PROFILE_RE.search(t)
        if not m:
            return ""
        return f"{m.group(1).upper()}{m.group(2)}"
    
    @classmethod
    def parse_hardware_code(cls, code_text: str, color_suffix=None) -> str:
        """
        Parsuje kod okuć Aluprof.
        
        Przykłady:
        - "8000 965 D" → "8000965X" (kolor D)
        - "8A022 27I4" → "8A02227X" (kolor I4)
        - "8010 544 B4" → "8010544X" (kolor B4)
        - "967 D" → "967X" (kolor D)
        """
        t = clean(code_text)
        m = cls.HARDWARE_RE.search(t)
        if not m:
            return ""
        
        part1 = m.group(1).upper()
        part2 = m.group(2)
        part3 = m.group(3) or ""
        
        # Usuń litery z part2 (cyfry)
        part2_clean = re.sub(r"[A-Z]", "", part2)
        
        # Jeśli wykryto kolor GDZIEKOLWIEK
        if part3 or color_suffix:
            return f"{part1}{part2_clean}X"
        else:
            # Dopasuj długość (stare zachowanie)
            if len(part1) == 4 and len(part2_clean) < 4:
                return f"{part1}{part2_clean.zfill(4)}"
            return f"{part1}{part2_clean}"


class GenericProfile(VendorProfile):
    NAME = "Inny / Generic"
    PROFILE_RE = re.compile(r"\b([A-Z]\d{2})\s*(\d{3,5})\b", re.IGNORECASE)
    HARDWARE_RE = re.compile(r"\b([0-9A-Z]{3,8})[\s\-/.](\d{1,5}[A-Z]?\d*)\b", re.IGNORECASE)
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        t = clean(code_text).upper()
        m = cls.PROFILE_RE.search(t)
        if not m:
            return ""
        return f"{m.group(1).upper()}{m.group(2)}"
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        t = clean(code_text)
        m = cls.HARDWARE_RE.search(t)
        if not m:
            return ""
        part1 = m.group(1)
        part2 = m.group(2)
        has_color = bool(re.search(r"[A-Z]", part2))
        if has_color:
            part2_clean = re.sub(r"[A-Z]+", "", part2)
            return f"{part1}{part2_clean}X"
        else:
            return f"{part1}{part2}"

VENDOR_PROFILES = {
    "aluprof": AluProfProfile,
    "reynaers": AluProfProfile,
    "aliplast": AluProfProfile,
    "generic": GenericProfile,
}

# --- GUI FUNKCJE ---
def select_vendor():
    root = tk.Tk()
    root.withdraw()
    vendors = list(VENDOR_PROFILES.keys())
    vendor_names = [VENDOR_PROFILES[v].NAME for v in vendors]
    
    choice_window = tk.Toplevel()
    choice_window.title("Wybierz dostawcę profili")
    choice_window.geometry("400x300")
    tk.Label(choice_window, text="Wybierz dostawcę systemu profili:", font=("Arial", 12, "bold")).pack(pady=10)
    
    selected_vendor = tk.StringVar(value=vendors[0])
    for vendor, name in zip(vendors, vendor_names):
        tk.Radiobutton(choice_window, text=name, variable=selected_vendor, value=vendor, font=("Arial", 10)).pack(anchor="w", padx=20, pady=5)
    
    result = {"vendor": None}
    def on_confirm():
        result["vendor"] = selected_vendor.get()
        choice_window.destroy()
    def on_cancel():
        choice_window.destroy()
    
    tk.Button(choice_window, text="Potwierdź", command=on_confirm, font=("Arial", 10), bg="#4CAF50", fg="white", width=15).pack(side="left", padx=20, pady=20)
    tk.Button(choice_window, text="Anuluj", command=on_cancel, font=("Arial", 10), bg="#f44336", fg="white", width=15).pack(side="right", padx=20, pady=20)
    
    choice_window.wait_window()
    
    if not result["vendor"]:
        return None
    vendor_profile = VENDOR_PROFILES[result["vendor"]]
    print(f"✓ Wybrano dostawcę: {vendor_profile.NAME}")
    return vendor_profile

def select_file(file_type, title):
    root = tk.Tk()
    root.withdraw()
    filetypes = {
        "MET": [("MET files", "*.MET"), ("All files", "*.*")],
        "CSV": [("CSV files", "*.csv"), ("All files", "*.*")],
        "HTML": [("HTML files", "*.html"), ("All files", "*.*")],
        "ALL": [("All files", "*.*")]
    }
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes.get(file_type, filetypes["ALL"]))
    return file_path if file_path else None

def select_project_from_list(projects_folder):
    """
    Wyświetla listę projektów w oknie dialogowym do wyboru.
    
    Args:
        projects_folder: Ścieżka do folderu z projektami
    
    Returns:
        str: Nazwa wybranego projektu lub None
    """
    if not os.path.exists(projects_folder):
        messagebox.showerror("Błąd", f"Brak folderu: {projects_folder}")
        return None
    
    # Filtruj projekty (foldery zaczynające się od "20")
    projects = sorted([
        d for d in os.listdir(projects_folder)
        if os.path.isdir(os.path.join(projects_folder, d)) and d.startswith('20')
    ], reverse=True)  # Najnowsze na górze
    
    if not projects:
        messagebox.showerror("Błąd", "Brak projektów w folderze")
        return None
    
    # Okno wyboru
    root = tk.Tk()
    root.withdraw()
    
    choice_window = tk.Toplevel()
    choice_window.title("Wybierz projekt")
    choice_window.geometry("600x500")
    
    # Nagłówek
    tk.Label(
        choice_window,
        text=f"Znaleziono {len(projects)} projektów:",
        font=("Arial", 12, "bold")
    ).pack(pady=10)
    
    # Frame z listą i scrollbarem
    frame = tk.Frame(choice_window)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    listbox = tk.Listbox(
        frame,
        yscrollcommand=scrollbar.set,
        font=("Courier", 10),
        height=15
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # Wypełnij listę
    for project in projects:
        listbox.insert(tk.END, project)
    
    # Zaznacz pierwszy (najnowszy)
    listbox.selection_set(0)
    listbox.activate(0)
    
    selected_project = {"value": None}
    
    def on_select():
        selection = listbox.curselection()
        if selection:
            selected_project["value"] = projects[selection[0]]
            choice_window.destroy()
    
    def on_cancel():
        choice_window.destroy()
    
    def on_double_click(event):
        on_select()
    
    listbox.bind("<Double-Button-1>", on_double_click)
    
    # Przyciski
    btn_frame = tk.Frame(choice_window)
    btn_frame.pack(pady=10)
    
    tk.Button(
        btn_frame,
        text="Wybierz",
        command=on_select,
        font=("Arial", 10),
        bg="#4CAF50",
        fg="white",
        width=15
    ).pack(side="left", padx=10)
    
    tk.Button(
        btn_frame,
        text="Anuluj",
        command=on_cancel,
        font=("Arial", 10),
        bg="#f44336",
        fg="white",
        width=15
    ).pack(side="left", padx=10)
    
    choice_window.wait_window()
    return selected_project["value"]

def select_folder(title):
    root = tk.Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title=title)
    return folder_path if folder_path else None

def clean(t):
    return " ".join(str(t or "").replace("\xa0", " ").split())

def get_project_prefix_from_met(met_filepath):
    met_filename = os.path.basename(met_filepath)
    base_name = os.path.splitext(met_filename)[0]
    words = re.findall(r'\w+', base_name)
    auto_prefix = "_".join(words[:3])[:MAX_PREFIX_LENGTH] + "_"
    root = tk.Tk()
    root.withdraw()
    prefix = simpledialog.askstring(
        "Prefiks dla rzutów",
        f"Nazwa pliku .MET: {met_filename}\n\n"
        f"Proponowany prefiks dla rzutów:\n"
        f"Przykład: {auto_prefix}Poz_1.jpg\n\n"
        f"Edytuj prefiks (max {MAX_PREFIX_LENGTH} znaków):",
        initialvalue=auto_prefix
    )
    if not prefix:
        prefix = auto_prefix
    prefix = prefix[:MAX_PREFIX_LENGTH]
    if not prefix.endswith("_"):
        prefix += "_"
    print(f"✓ Prefiks dla rzutów: {prefix}")
    return prefix

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


def validate_system_name(system, known_systems):
    if not system:
        messagebox.showerror("Błąd", "Nie podano nazwy systemu!")
        return None
    system = system.lower().strip().replace(" ", "")
    if system in known_systems:
        return system
    from difflib import get_close_matches
    matches = get_close_matches(system, known_systems, n=3, cutoff=0.6)
    if matches:
        root = tk.Tk()
        root.withdraw()
        suggestion = messagebox.askyesno("Literówka?", f"Wpisano: {system}\n\nCzy chodziło o: {matches[0]}?\n\nTAK - użyj {matches[0]}\nNIE - użyj '{system}'")
        if suggestion:
            print(f"✅ Poprawiono: {system} → {matches[0]}")
            return matches[0]
    messagebox.showwarning("Uwaga!", f"Używam: {system}\n\n⚠️ To nieznany system!\nLiterówka spowoduje CHAOS w bazie danych.")
    return system

def validate_and_choose_system(csv_path):
    KNOWN_SYSTEMS = ["mb-45", "mb-59s", "mb-60", "mb-70", "mb-77hs", "mb-78ei", "mb-86", "mb-86n", "mb-86si", "mb-104", "mb-sr50n", "mb-79n", "cs-77", "cs-104", "cp-130", "masterline-8", "imperial", "smart", "genesis"]
    detected = extract_system_from_csv(csv_path)
    if not detected:
        root = tk.Tk()
        root.withdraw()
        system = simpledialog.askstring("System nieznany", f"Nie wykryto systemu w CSV.\n\nPopularne systemy:\n{', '.join(KNOWN_SYSTEMS[:10])}\n\nWpisz system (małe litery, np. mb-77hs):")
        if system:
            system = system.lower().strip().replace(" ", "")
        return validate_system_name(system, KNOWN_SYSTEMS)
    if detected in KNOWN_SYSTEMS:
        print(f"✅ System wykryty: {detected}")
        return detected
    from difflib import get_close_matches
    matches = get_close_matches(detected, KNOWN_SYSTEMS, n=1, cutoff=0.7)
    if matches:
        root = tk.Tk()
        root.withdraw()
        confirm = messagebox.askyesno("Potwierdzenie systemu", f"Wykryto: {detected}\n\nCzy chodziło o: {matches[0]}?\n\nTAK - użyj {matches[0]}\nNIE - użyj '{detected}'")
        if confirm:
            print(f"✅ Poprawiono: {detected} → {matches[0]}")
            return matches[0]
    root = tk.Tk()
    root.withdraw()
    confirm = messagebox.askyesno("Nieznany system", f"Wykryto: {detected}\n\nTo nowy system - kontynuować?\n\nTAK - użyj '{detected}'\nNIE - pozwól mi wpisać ręcznie")
    if confirm:
        print(f"⚠️ Nowy system: {detected}")
        return detected
    corrected = simpledialog.askstring("Popraw system", f"Wykryto: {detected}\n\nPopularne:\n{', '.join(KNOWN_SYSTEMS[:8])}\n\nWpisz poprawną nazwę:", initialvalue=detected)
    if corrected:
        corrected = corrected.lower().strip().replace(" ", "")
    return validate_system_name(corrected, KNOWN_SYSTEMS)
def find_existing_file(images_dir: str, filename_from_html: str):
    base, _ = os.path.splitext(filename_from_html)
    candidates = [filename_from_html] + [base + ext for ext in PREFERRED_EXT_ORDER]
    for c in candidates:
        if os.path.exists(os.path.join(images_dir, c)):
            return c
    return None

def extract_color_code_from_csv(csv_path):
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
            skipped += 1
            continue
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

def parse_hardware_from_csv(csv_path, vendor_profile):
    color_code = extract_color_code_from_csv(csv_path)
    
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


def build_hardware_mapping_from_lp_html(html_path, images_dir, vendor_profile):
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
        code_hw = vendor_profile.parse_hardware_code(code_text)
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
    vendor_key = "aluprof"
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
    
    system = validate_and_choose_system(csv_file)
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
    rename_profiles_from_lp_html(lp_html, lp_images_dir, OUTPUT_PROFILES_DIR, vendor_profile)
    
    print("\n[KROK 3/4] Parsowanie okuć z CSV...")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)
    print(f"✓ Znaleziono {len(hardware_codes)} kodów okuć")
    
    print("\n[KROK 4/4] Przetwarzanie okuć...")
    code_to_srcfile = build_hardware_mapping_from_lp_html(lp_html, lp_images_dir, vendor_profile)
    rename_hardware(hardware_codes, code_to_srcfile, lp_images_dir, OUTPUT_HARDWARE_DIR)
    
    log_audit("IMAGES_PROCESSED", {"project": project_name, "vendor": vendor_key, "system": system, "positions": len(positions), "hardware": len(hardware_codes)})
    
    print("\n" + "=" * 60)
    print("✅ GOTOWE!")
    print("=" * 60)
    messagebox.showinfo("Sukces!", f"Obrazki przetworzone!\n\nProjekt: {project_name}\nSystem: {system}\nPozycje: {len(positions)}\nOkucia: {len(hardware_codes)}")

if __name__ == "__main__":
    main()
