import os
import re
import csv
import shutil
from collections import defaultdict
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import json
import hashlib
import getpass
import socket
from datetime import datetime

# --- BEZPIECZEŃSTWO ---
BASE_PATH = r"Z:\Pawel_Pisarski\Dokumentacja"
AUTH_FILE = os.path.join(BASE_PATH, "config", "authorized_users.json")
AUDIT_LOG = os.path.join(BASE_PATH, "logs", "audit_log.jsonl")

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


# --- KONFIGURACJA - NOWA STRUKTURA ---
PROJECTS_IMAGES = os.path.join(BASE_PATH, "projects_images")
IMAGES_DB = os.path.join(BASE_PATH, "images_db")

# Będzie ustawione dynamicznie w main()
OUTPUT_VIEWS_DIR = None
OUTPUT_PROFILES_DIR = None  
OUTPUT_HARDWARE_DIR = None

CONFLICTS_DIR = "_conflicts"

PREFERRED_EXT_ORDER = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]
ENABLE_CONFLICT_MODE = True
MAX_PREFIX_LENGTH = 25

# --- VENDOR PROFILES (wtyczki dla dostawców) ---

class VendorProfile:
    """Bazowa klasa dla profili dostawców."""
    
    NAME = "Generic"
    
    # Regex dla profili (K-kody)
    PROFILE_RE = None
    
    # Regex dla okuć/akcesoriów
    HARDWARE_RE = None
    
    # Regex dla tokenów kolorów
    COLOR_TOKEN_RE = None
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        """Zwraca bazowy kod profilu (bez koloru)."""
        raise NotImplementedError
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        """Zwraca kod okucia/akcesoria (z X zamiast koloru jeśli dotyczy)."""
        raise NotImplementedError


class AluProfProfile(VendorProfile):
    """Profil dla Aluprof/MB-CAD."""
    
    NAME = "Aluprof / MB-CAD"
    
    PROFILE_RE = re.compile(r"\b(K\d{2})\s*(\d{4})\b", re.IGNORECASE)
    
    # Kody 3-6 znaków (cyfry lub 8A/8H) + spacja + 1-4 cyfry + opcjonalne litery/cyfry
    HARDWARE_RE = re.compile(
        r"\b([0-9A-H]{3,6})\s+(\d{1,4}[A-Z]?\d*)\b",
        re.IGNORECASE
    )
    
    COLOR_TOKEN_RE = re.compile(r"^(?:[A-Z]\d|[0-9])[A-Z0-9]{1,5}$", re.IGNORECASE)
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        """
        'K41 5223 4R7016' -> 'K415223' (ignoruje kolor)
        """
        t = clean(code_text).upper()
        m = cls.PROFILE_RE.search(t)
        if not m:
            return ""
        return f"{m.group(1).upper()}{m.group(2)}"
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        """
        '8000 969' -> '80000969'
        '8000 969 P4' -> '8000969X'
        '8043 503 A4' -> '8043503X'
        '121 169' -> '121169'
        """
        t = clean(code_text)
        m = cls.HARDWARE_RE.search(t)
        if not m:
            return ""
        
        part1 = m.group(1)  # 8000, 8043, 121, 8A022
        part2 = m.group(2)  # 969, 503, 27I4, 169
        
        # Sprawdź czy part2 zawiera litery (token koloru)
        has_color_suffix = bool(re.search(r"[A-Z]", part2))
        
        if has_color_suffix:
            # Usuń WSZYSTKIE litery i zostaw tylko cyfry + X na końcu
            part2_clean = re.sub(r"[A-Z]+", "", part2)
            return f"{part1}{part2_clean}X"
        else:
            # Kod bez koloru
            # Dla standardowych 4-cyfrowych kodów uzupełnij part2 do 4 cyfr
            if len(part1) == 4 and part2.isdigit() and len(part2) < 4:
                return f"{part1}{part2.zfill(4)}"
            else:
                return f"{part1}{part2}"


class ReynersProfile(VendorProfile):
    """Profil dla Reynaers - DO UZUPEŁNIENIA."""
    
    NAME = "Reynaers"
    
    # TODO: Dodaj konkretne regexy po zebraniu przykładów
    PROFILE_RE = re.compile(r"\b(K\d{2})\s*(\d{4})\b", re.IGNORECASE)  # placeholder
    HARDWARE_RE = re.compile(r"\b([0-9A-Z]{3,6})[\s\-](\d{1,4}[A-Z]?\d*)\b", re.IGNORECASE)
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        # TODO: Uzupełnij po analizie danych Reynaers
        return AluProfProfile.parse_profile_code(code_text)
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        # TODO: Uzupełnij po analizie danych Reynaers
        return AluProfProfile.parse_hardware_code(code_text)


class AliplastProfile(VendorProfile):
    """Profil dla Aliplast - DO UZUPEŁNIENIA."""
    
    NAME = "Aliplast"
    
    # TODO: Dodaj konkretne regexy po zebraniu przykładów
    PROFILE_RE = re.compile(r"\b(K\d{2})\s*(\d{4})\b", re.IGNORECASE)  # placeholder
    HARDWARE_RE = re.compile(r"\b([0-9A-Z]{3,6})[\s\-](\d{1,4}[A-Z]?\d*)\b", re.IGNORECASE)
    
    @classmethod
    def parse_profile_code(cls, code_text: str) -> str:
        # TODO: Uzupełnij po analizie danych Aliplast
        return AluProfProfile.parse_profile_code(code_text)
    
    @classmethod
    def parse_hardware_code(cls, code_text: str) -> str:
        # TODO: Uzupełnij po analizie danych Aliplast
        return AluProfProfile.parse_hardware_code(code_text)


class GenericProfile(VendorProfile):
    """Profil uniwersalny - bardzo liberalny, bez zfill."""
    
    NAME = "Inny / Generic"
    
    # Bardzo liberalne wzorce
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
        
        # Usuń litery z part2 i dodaj X
        has_color = bool(re.search(r"[A-Z]", part2))
        if has_color:
            part2_clean = re.sub(r"[A-Z]+", "", part2)
            return f"{part1}{part2_clean}X"
        else:
            # NIE używamy zfill dla generic
            return f"{part1}{part2}"


# Dostępne profile
VENDOR_PROFILES = {
    "aluprof": AluProfProfile,
    "reynaers": ReynersProfile,
    "aliplast": AliplastProfile,
    "generic": GenericProfile,
}

# --- REGEX PATTERNS (wspólne) ---
POZ_LINE_RE = re.compile(r"Poz\.\s*(\d+)")
SECTION_RE = re.compile(r"^(Profile|Akcesoria|Okucia)\b", re.IGNORECASE)

# --- GUI FUNKCJE ---

def select_vendor():
    """Okno wyboru dostawcy."""
    root = tk.Tk()
    root.withdraw()
    
    vendors = list(VENDOR_PROFILES.keys())
    vendor_names = [VENDOR_PROFILES[v].NAME for v in vendors]
    
    # Tworzymy okno wyboru
    choice_window = tk.Toplevel()
    choice_window.title("Wybierz dostawcę profili")
    choice_window.geometry("400x300")
    
    tk.Label(
        choice_window,
        text="Wybierz dostawcę systemu profili:",
        font=("Arial", 12, "bold")
    ).pack(pady=10)
    
    selected_vendor = tk.StringVar(value=vendors[0])
    
    for vendor, name in zip(vendors, vendor_names):
        tk.Radiobutton(
            choice_window,
            text=name,
            variable=selected_vendor,
            value=vendor,
            font=("Arial", 10)
        ).pack(anchor="w", padx=20, pady=5)
    
    result = {"vendor": None}
    
    def on_confirm():
        result["vendor"] = selected_vendor.get()
        choice_window.destroy()
    
    def on_cancel():
        choice_window.destroy()
    
    tk.Button(
        choice_window,
        text="Potwierdź",
        command=on_confirm,
        font=("Arial", 10),
        bg="#4CAF50",
        fg="white",
        width=15
    ).pack(side="left", padx=20, pady=20)
    
    tk.Button(
        choice_window,
        text="Anuluj",
        command=on_cancel,
        font=("Arial", 10),
        bg="#f44336",
        fg="white",
        width=15
    ).pack(side="right", padx=20, pady=20)
    
    choice_window.wait_window()
    
    if not result["vendor"]:
        return None
    
    vendor_profile = VENDOR_PROFILES[result["vendor"]]
    print(f"✓ Wybrano dostawcę: {vendor_profile.NAME}")
    return vendor_profile


def select_file(file_type, title):
    """Otwiera okno wyboru pojedynczego pliku."""
    root = tk.Tk()
    root.withdraw()
    
    filetypes = {
        "MET": [("MET files", "*.MET"), ("All files", "*.*")],
        "CSV": [("CSV files", "*.csv"), ("All files", "*.*")],
        "HTML": [("HTML files", "*.html"), ("All files", "*.*")],
        "ALL": [("All files", "*.*")]
    }
    
    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes.get(file_type, filetypes["ALL"])
    )
    
    return file_path if file_path else None

def select_folder(title):
    """Otwiera okno wyboru folderu."""
    root = tk.Tk()
    root.withdraw()
    
    folder_path = filedialog.askdirectory(title=title)
    
    return folder_path if folder_path else None

def clean(t):
    return " ".join(str(t or "").replace("\xa0", " ").split())

def get_project_prefix_from_met(met_filepath):
    """
    Tworzy prefiks z nazwy .MET z możliwością edycji przez użytkownika.
    """
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
    """Zwraca listę numerów pozycji z pliku CSV."""
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

def find_existing_file(images_dir: str, filename_from_html: str):
    """Szuka pliku z różnymi rozszerzeniami."""
    base, _ = os.path.splitext(filename_from_html)
    candidates = [filename_from_html] + [base + ext for ext in PREFERRED_EXT_ORDER]
    
    for c in candidates:
        if os.path.exists(os.path.join(images_dir, c)):
            return c
    return None

def choose_preferred_filename(filenames: list) -> str:
    """Wybiera plik wg preferencji rozszerzeń."""
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

# ==================== RZUTY ====================

def get_rk_images_from_html(html_path):
    """Wyciąga listę plików rzutów z RK.html."""
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
    """
    Zmienia nazwy rzutów: img0.jpg -> et2_Piast_Poz_1.jpg
    Formuła: (pos - 1) * 2 = indeks obrazka
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
        
        # Auto-naprawa rozszerzenia
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

# ==================== PROFILE ====================

def rename_profiles_from_lp_html(html_path, images_dir, output_dir, vendor_profile):
    """
    Zmienia nazwy profili na bazowy kod (ignorując kolor).
    Używa parsera specyficznego dla dostawcy.
    """
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
        
        # Szukamy kodu w sąsiednich komórkach
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
    
    # Tryb konfliktów
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

# ==================== OKUCIA/AKCESORIA ====================

def parse_hardware_from_csv(csv_path, vendor_profile):
    """
    Parsuje kody okuć/akcesoriów z CSV.
    Używa parsera specyficznego dla dostawcy.
    """
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
        
        # Nowa pozycja
        mpos = POZ_LINE_RE.search(line)
        if mpos and "MB-" in line:
            current_pos = mpos.group(1)
            current_section = None
            continue
        
        if not current_pos:
            continue
        
        # Sekcje
        if r and r[0] and SECTION_RE.match(r[0]):
            sec = SECTION_RE.match(r[0]).group(1).capitalize()
            current_section = sec if sec in ["Akcesoria", "Okucia"] else None
            continue
        
        if current_section not in ["Akcesoria", "Okucia"]:
            continue
        
        # Nagłówek tabeli - NIE wychodź
        if any(c.lower().startswith("kod:") for c in r):
            pass
        
        # Szukamy kodu
        joined = " ".join([x for x in r if x])
        code_hw = vendor_profile.parse_hardware_code(joined)
        if not code_hw:
            continue
        
        # Opis z linii poniżej
        desc = ""
        if i + 1 < len(rows):
            next_row = [clean(c) for c in rows[i + 1]]
            next_desc = next_row[0] if next_row else ""
            # Sprawdź czy następna linia nie ma kodu
            if next_desc and not vendor_profile.parse_hardware_code(next_desc):
                desc = next_desc
        
        if code_hw not in hardware_codes:
            hardware_codes[code_hw] = {"desc": desc, "positions": set()}
        
        hardware_codes[code_hw]["positions"].add(current_pos)
    
    return hardware_codes

def build_hardware_mapping_from_lp_html(html_path, images_dir, vendor_profile):
    """
    Mapowanie code -> realny plik w LP_images.files.
    Używa parsera specyficznego dla dostawcy.
    """
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
        
        html_filename = os.path.basename(src)
        real = find_existing_file(images_dir, html_filename)
        
        if not real:
            continue
        
        tds = tr.find_all("td")
        img_td = img.find_parent("td")
        
        if img_td not in tds:
            continue
        
        idx = tds.index(img_td)
        code_text = ""
        
        # Sprawdź lewo i prawo
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
        
        tmp[code_hw].add(real)
    
    # Wybór preferowanego rozszerzenia
    out = {}
    for code_hw, files in tmp.items():
        files = list(files)
        out[code_hw] = choose_preferred_filename(files)
    
    return out

def rename_hardware(hardware_codes, code_to_srcfile, src_dir, output_dir):
    """
    Kopiuje obrazki okuć do images_db/hardware/ z nowymi nazwami.
    """
    os.makedirs(output_dir, exist_ok=True)
    renamed = 0
    skipped = 0
    
    for code_hw in hardware_codes.keys():
        src_fn = code_to_srcfile.get(code_hw)
        if not src_fn:
            skipped += 1
            continue
        
        src_path = os.path.join(src_dir, src_fn)
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

# ==================== MAIN ====================

def main():
    print("=" * 60)
    print("REORGANIZACJA BAZY OBRAZKÓW (NOWA STRUKTURA)")
    print("=" * 60)
    
    # BEZPIECZEŃSTWO
    check_authorization()
    
    # 0. Wybór dostawcy
    print("\n[0] Wybierz dostawcę systemu profili...")
    vendor_profile = select_vendor()
    if not vendor_profile:
        messagebox.showerror("Błąd", "Nie wybrano dostawcy. Przerywam.")
        return
    
    # GUI: Wybór plików i folderów
    print("\n📂 Wybierz pliki i foldery wejściowe...\n")
    
    # 1. Plik .MET
    print("[1/6] Wybierz plik .MET...")
    met_file = select_file("MET", "Wybierz plik .MET (dla nazwy projektu)")
    if not met_file:
        messagebox.showerror("Błąd", "Nie wybrano pliku .MET. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(met_file)}")
    
    # 2. Plik CSV
    print("\n[2/6] Wybierz plik CSV z danymi LP...")
    csv_file = select_file("CSV", "Wybierz plik LP_dane.csv")
    if not csv_file:
        messagebox.showerror("Błąd", "Nie wybrano pliku CSV. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(csv_file)}")
    
    # 3. Plik RK_images.html
    print("\n[3/6] Wybierz plik RK_images.html...")
    rk_html = select_file("HTML", "Wybierz plik RK_images.html")
    if not rk_html:
        messagebox.showerror("Błąd", "Nie wybrano pliku RK_images.html. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(rk_html)}")
    
    # 4. Folder RK_images.files
    print("\n[4/6] Wybierz folder RK_images.files...")
    rk_images_dir = select_folder("Wybierz folder RK_images.files")
    if not rk_images_dir:
        messagebox.showerror("Błąd", "Nie wybrano folderu RK_images.files. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(rk_images_dir)}")
    
    # 5. Plik LP_images.html
    print("\n[5/6] Wybierz plik LP_images.html...")
    lp_html = select_file("HTML", "Wybierz plik LP_images.html")
    if not lp_html:
        messagebox.showerror("Błąd", "Nie wybrano pliku LP_images.html. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(lp_html)}")
    
    # 6. Folder LP_images.files
    print("\n[6/6] Wybierz folder LP_images.files...")
    lp_images_dir = select_folder("Wybierz folder LP_images.files")
    if not lp_images_dir:
        messagebox.showerror("Błąd", "Nie wybrano folderu LP_images.files. Przerywam.")
        return
    print(f"✓ Wybrano: {os.path.basename(lp_images_dir)}")
    
    print("\n" + "=" * 60)
    print(f"PRZETWARZANIE - Dostawca: {vendor_profile.NAME}")
    print("=" * 60)
    
    # Wybór projektu
    projects_folder = os.path.join(BASE_PATH, "projects")
    projects = [d for d in os.listdir(projects_folder) 
                if os.path.isdir(os.path.join(projects_folder, d)) and d.startswith('20')]
    project_name = simpledialog.askstring("Projekt", 
        f"Znaleziono {len(projects)} projektów.\nPrzykłady: {projects[:3]}\n\nWpisz nazwę projektu:")
    if not project_name or project_name not in projects:
        messagebox.showerror("Błąd", "Nieprawidłowy projekt.")
        return
    
    # Wykryj system z CSV
    system = None
    with open(csv_file, "r", encoding="cp1250", errors="replace") as f:
        for line in f:
            if "System:" in line:
                m = re.search(r"System:\s*(.+)", line)
                if m:
                    system = re.sub(r"\s+(HI|SI|EI).*", "", m.group(1).split(";")[0], flags=re.I).lower()
                    break
    if not system:
        system = simpledialog.askstring("System", "Wpisz system (np. mb-77hs):")
    system = system.lower().strip()
    
    # Ustaw foldery wyjściowe (NOWA STRUKTURA!)
    global OUTPUT_VIEWS_DIR, OUTPUT_PROFILES_DIR, OUTPUT_HARDWARE_DIR
    vendor_key = "aluprof"  # lub result["vendor"] jeśli masz
    OUTPUT_VIEWS_DIR = os.path.join(PROJECTS_IMAGES, project_name, "views")
    OUTPUT_PROFILES_DIR = os.path.join(IMAGES_DB, vendor_key, "profiles", system)
    OUTPUT_HARDWARE_DIR = os.path.join(IMAGES_DB, vendor_key, "hardware")
    
    os.makedirs(OUTPUT_VIEWS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PROFILES_DIR, exist_ok=True)
    os.makedirs(OUTPUT_HARDWARE_DIR, exist_ok=True)
    
    print(f"\n✅ Zapisuję do:")
    print(f"  Views: {OUTPUT_VIEWS_DIR}")
    print(f"  Profiles: {OUTPUT_PROFILES_DIR}")
    print(f"  Hardware: {OUTPUT_HARDWARE_DIR}\n")
    
    # Pobierz prefiks projektu
    prefix = get_project_prefix_from_met(met_file)
    
    # Parsowanie CSV
    print("\n[KROK 1/4] Parsowanie CSV...")
    positions = get_positions_from_csv(csv_file)
    print(f"✓ Znaleziono {len(positions)} pozycji")
    
    # RZUTY
    print("\n[KROK 2/4] Przetwarzanie rzutów...")
    rk_images = get_rk_images_from_html(rk_html)
    print(f"✓ Znaleziono {len(rk_images)} obrazków w RK.html")
    rename_views(positions, rk_images, rk_images_dir, prefix, OUTPUT_VIEWS_DIR)
    
    # PROFILE
    print("\n[KROK 3/4] Przetwarzanie profili...")
    rename_profiles_from_lp_html(lp_html, lp_images_dir, OUTPUT_PROFILES_DIR, vendor_profile)
    
    # OKUCIA/AKCESORIA
    print("\n[KROK 4/4] Przetwarzanie okuć/akcesoriów...")
    hardware_codes = parse_hardware_from_csv(csv_file, vendor_profile)
    print(f"✓ Znaleziono {len(hardware_codes)} unikalnych kodów okuć")
    
    # DEBUG: Wypisz przykłady
    if hardware_codes:
        print("\n📋 Przykłady znalezionych kodów:")
        for i, (code, data) in enumerate(list(hardware_codes.items())[:10]):
            print(f"   {i+1}. {code} - {data['desc'][:40] if data['desc'] else 'brak opisu'}")
    
    code_to_srcfile = build_hardware_mapping_from_lp_html(lp_html, lp_images_dir, vendor_profile)
    print(f"✓ Mapowanie z HTML dla {len(code_to_srcfile)} kodów")
    
    rename_hardware(hardware_codes, code_to_srcfile, lp_images_dir, OUTPUT_HARDWARE_DIR)
    
    log_audit("IMAGES_PROCESSED", {"project": project_name, "system": system, 
                                    "positions": len(positions), "hardware": len(hardware_codes)})
    
    # Podsumowanie
    print("\n" + "=" * 60)
    print("✅ SUKCES! Baza obrazków gotowa:")
    print(f"   📁 {OUTPUT_VIEWS_DIR}/")
    print(f"   📁 {OUTPUT_PROFILES_DIR}/")
    print(f"   📁 {OUTPUT_HARDWARE_DIR}/")
    print("=" * 60)
    
    messagebox.showinfo(
        "Gotowe!",
        f"Baza obrazków została utworzona:\n\n"
        f"Dostawca: {vendor_profile.NAME}\n\n"
        f"📁 {OUTPUT_VIEWS_DIR}/\n"
        f"📁 {OUTPUT_PROFILES_DIR}/\n"
        f"📁 {OUTPUT_HARDWARE_DIR}/\n\n"
        f"Rzuty: {len(positions)} pozycji\n"
        f"Okucia: {len(hardware_codes)} kodów"
    )

if __name__ == "__main__":
    main()
