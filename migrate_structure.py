import os
import re
import shutil
import json
import hashlib
import getpass
import socket
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog, messagebox

# --- KONFIGURACJA ---
BASE_PATH = r"Z:\Pawel_Pisarski\Dokumentacja"
MD_FOLDER = os.path.join(BASE_PATH, "MD")
PDF_FOLDER = os.path.join(BASE_PATH, "PDF")
IMAGES_DB_FOLDER = os.path.join(BASE_PATH, "images_db")

PROJECTS_FOLDER = os.path.join(BASE_PATH, "projects")
PROJECTS_IMAGES_FOLDER = os.path.join(BASE_PATH, "projects_images")

CONFIG_FILE = os.path.join(BASE_PATH, "config", "config.json")
AUTH_FILE = os.path.join(BASE_PATH, "config", "authorized_users.json")
AUDIT_LOG = os.path.join(BASE_PATH, "logs", "audit_log.jsonl")

# --- BEZPIECZEŃSTWO: AUTORYZACJA ---

def check_authorization():
    """Sprawdza czy użytkownik ma uprawnienia do uruchamiania skryptu."""
    current_user = getpass.getuser()
    
    if not os.path.exists(AUTH_FILE):
        print("⚠️ Brak pliku autoryzacji. Tworzę domyślny...")
        create_default_auth_file()
    
    with open(AUTH_FILE, 'r', encoding='utf-8') as f:
        auth_data = json.load(f)
    
    authorized = auth_data.get('authorized_editors', [])
    
    if current_user not in authorized:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Brak uprawnień",
            f"Użytkownik '{current_user}' nie ma uprawnień do uruchamiania tego skryptu.\n\n"
            f"Autoryzowani użytkownicy: {', '.join(authorized)}\n\n"
            f"Skontaktuj się z administratorem."
        )
        print(f"❌ BRAK UPRAWNIEŃ: Użytkownik '{current_user}' próbował uruchomić skrypt")
        log_audit("UNAUTHORIZED_ACCESS_ATTEMPT", {"user": current_user, "script": "migrate_structure.py"})
        exit(1)
    
    print(f"✅ Autoryzacja OK: {current_user}")

def create_default_auth_file():
    """Tworzy domyślny plik autoryzacji."""
    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    
    default_auth = {
        "authorized_editors": [
            getpass.getuser(),  # Aktualny użytkownik
            "pawel.pisarski",
            "PawelPisarski",
            "PP"
        ],
        "authorized_viewers": ["*"],
        "admin": getpass.getuser()
    }
    
    with open(AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_auth, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Utworzono plik autoryzacji: {AUTH_FILE}")

# --- BEZPIECZEŃSTWO: AUDIT LOG ---

def log_audit(action, details):
    """Zapisuje akcję do logu audytu."""
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "action": action,
        "details": details
    }
    
    with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

# --- BEZPIECZEŃSTWO: FILE HASH ---

def calculate_file_hash(filepath):
    """Oblicza SHA256 hash pliku."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# --- FUNKCJE POMOCNICZE ---

def extract_date_from_filename(filename):
    """Wyciąga datę z nazwy pliku (format polski: DD-MM-YY lub DD.MM.YY)."""
    patterns = [
        r'(\d{2})[-.](\d{2})[-.](\d{2})(?:\D|$)',
        r'(\d{2})[-.](\d{2})[-.](\d{4})(?:\D|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                continue
    return None

def get_file_creation_date(filepath):
    """Zwraca datę utworzenia pliku."""
    timestamp = os.path.getctime(filepath)
    return datetime.fromtimestamp(timestamp)

def ask_for_project_date(old_name, suggested_date):
    """Pyta użytkownika o datę projektu z możliwością edycji."""
    root = tk.Tk()
    root.withdraw()
    
    date_str = suggested_date.strftime("%Y-%m-%d")
    
    result = simpledialog.askstring(
        "Data projektu",
        f"Projekt: {old_name}\n\n"
        f"Wykryta/sugerowana data: {date_str}\n"
        f"(format: YYYY-MM-DD)\n\n"
        f"Edytuj datę lub naciśnij OK:",
        initialvalue=date_str
    )
    
    if not result:
        return suggested_date
    
    try:
        return datetime.strptime(result, "%Y-%m-%d")
    except ValueError:
        messagebox.showerror("Błąd", f"Nieprawidłowy format daty: {result}\nUżyto daty sugerowanej.")
        return suggested_date

def normalize_project_name(old_name):
    """Normalizuje nazwę projektu (bez daty)."""
    name = old_name
    
    # Usuń daty
    date_patterns = [
        r'[-\s]?\d{2}[-\.]\d{2}[-\.]\d{2,4}',
        r'[-\s]?PP\s*$',
    ]
    for pattern in date_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Zamień separatory na podkreślniki
    name = re.sub(r'[\s\-]+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    name = name[:50].rstrip('_')
    
    return name

def build_migration_plan(md_folder):
    """Buduje plan migracji."""
    plan = []
    md_files = [f for f in os.listdir(md_folder) if f.endswith('.md')]
    
    print(f"\n📂 Znaleziono {len(md_files)} plików .md\n")
    
    for md_file in sorted(md_files):
        old_path = os.path.join(md_folder, md_file)
        old_name = os.path.splitext(md_file)[0]
        
        date_from_name = extract_date_from_filename(md_file)
        if not date_from_name:
            date_from_name = get_file_creation_date(old_path)
        
        final_date = ask_for_project_date(old_name, date_from_name)
        clean_name = normalize_project_name(old_name)
        new_folder_name = f"{final_date.strftime('%Y-%m-%d')}_{clean_name}"
        
        plan.append({
            'old_path': old_path,
            'old_name': old_name,
            'new_folder': new_folder_name,
            'date': final_date,
            'md_filename': md_file
        })
    
    return plan

def show_migration_preview(plan):
    """Pokazuje podgląd migracji."""
    print("\n" + "=" * 80)
    print("📋 PODGLĄD MIGRACJI")
    print("=" * 80)
    
    for i, item in enumerate(plan, 1):
        print(f"\n{i}. {item['old_name']}")
        print(f"   → projects/{item['new_folder']}/")
    
    print("\n" + "=" * 80)
    
    root = tk.Tk()
    root.withdraw()
    
    confirm = messagebox.askyesno(
        "Potwierdzenie migracji",
        f"Znaleziono {len(plan)} projektów do migracji.\n\n"
        f"Szczegóły wyświetlone w konsoli.\n\n"
        f"Kontynuować migrację?"
    )
    
    return confirm

def create_backup(base_path):
    """Tworzy kopię zapasową."""
    backup_name = f"_backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    backup_path = os.path.join(base_path, backup_name)
    
    print(f"\n📦 Tworzenie kopii zapasowej...")
    print(f"   Lokalizacja: {backup_path}")
    
    os.makedirs(backup_path, exist_ok=True)
    
    for folder_name in ["MD", "PDF", "images_db"]:
        src = os.path.join(base_path, folder_name)
        dst = os.path.join(backup_path, folder_name)
        if os.path.exists(src):
            print(f"   Kopiuję: {folder_name}/...")
            shutil.copytree(src, dst)
    
    print(f"✅ Backup utworzony: {backup_path}\n")
    return backup_path

def update_image_paths_in_md(md_path, project_folder_name):
    """Aktualizuje ścieżki do obrazków w pliku .md."""
    with open(md_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    replacements = [
        (r'!\[\]\(images_db/views/([^)]+)\)', 
         rf'![](../../projects_images/{project_folder_name}/views/\1)'),
        (r'!\[\]\(images_db/profiles/([^)]+)\)', 
         r'![](../../images_db/aluprof/profiles/SYSTEM/\1)'),
        (r'!\[\]\(images_db/hardware/([^)]+)\)', 
         r'![](../../images_db/aluprof/hardware/\1)'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)

def migrate_project(item, projects_folder):
    """Migruje pojedynczy projekt."""
    new_project_folder = os.path.join(projects_folder, item['new_folder'])
    os.makedirs(new_project_folder, exist_ok=True)
    
    new_md_path = os.path.join(new_project_folder, item['md_filename'])
    shutil.copy2(item['old_path'], new_md_path)
    
    # Hash pliku
    file_hash = calculate_file_hash(new_md_path)
    
    # Aktualizuj ścieżki obrazków
    update_image_paths_in_md(new_md_path, item['new_folder'])
    
    # Zapisz metadata z hashem
    metadata = {
        "project_name": item['new_folder'],
        "original_name": item['old_name'],
        "created": item['date'].isoformat(),
        "migrated": datetime.now().isoformat(),
        "file_hash": file_hash,
        "author": getpass.getuser()
    }
    
    metadata_path = os.path.join(new_project_folder, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"✅ {item['new_folder']}/")

def main():
    print("=" * 80)
    print("MIGRACJA STRUKTURY DOKUMENTACJI - FAZA 1 (Security Enhanced)")
    print("=" * 80)
    
    # BEZPIECZEŃSTWO: Sprawdź autoryzację
    check_authorization()
    
    if not os.path.exists(MD_FOLDER):
        print(f"❌ Błąd: Folder {MD_FOLDER} nie istnieje!")
        return
    
    # Backup
    root = tk.Tk()
    root.withdraw()
    
    create_backup_choice = messagebox.askyesno(
        "Kopia zapasowa",
        "Czy utworzyć kopię zapasową przed migracją?\n\nRekomendowane: TAK"
    )
    
    backup_path = None
    if create_backup_choice:
        backup_path = create_backup(BASE_PATH)
        log_audit("BACKUP_CREATED", {"path": backup_path})
    
    # Plan migracji
    plan = build_migration_plan(MD_FOLDER)
    
    if not plan:
        print("❌ Brak plików .md do migracji.")
        return
    
    # Podgląd
    if not show_migration_preview(plan):
        print("\n❌ Migracja anulowana przez użytkownika.")
        log_audit("MIGRATION_CANCELLED", {"user": getpass.getuser()})
        return
    
    # Migracja
    os.makedirs(PROJECTS_FOLDER, exist_ok=True)
    os.makedirs(PROJECTS_IMAGES_FOLDER, exist_ok=True)
    
    print("\n🚀 Rozpoczynam migrację...\n")
    
    for item in plan:
        migrate_project(item, PROJECTS_FOLDER)
    
    # Log
    log_audit("MIGRATION_COMPLETED", {
        "projects_migrated": len(plan),
        "backup_path": backup_path
    })
    
    # Podsumowanie
    print("\n" + "=" * 80)
    print("✅ MIGRACJA ZAKOŃCZONA POMYŚLNIE!")
    print("=" * 80)
    print(f"\nPrzemigrowano: {len(plan)} projektów")
    print(f"Lokalizacja: {PROJECTS_FOLDER}/")
    
    if backup_path:
        print(f"\nKopia zapasowa: {backup_path}/")
    
    print(f"\nLog audytu: {AUDIT_LOG}")
    
    messagebox.showinfo(
        "Gotowe!",
        f"Migracja zakończona!\n\n"
        f"Przemigrowano: {len(plan)} projektów\n"
        f"Sprawdź folder: projects/"
    )

if __name__ == "__main__":
    main()
