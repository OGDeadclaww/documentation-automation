# gui.py
"""
Dialogi i okna GUI (tkinter).
Wybór plików, projektów, dostawców, systemów.
"""
import os
import re
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from difflib import get_close_matches

from config import PREFERRED_EXT_ORDER, MAX_PREFIX_LENGTH, KNOWN_SYSTEMS
from vendors import VENDOR_PROFILES, list_vendors


# ============================================
# WYBÓR DOSTAWCY
# ============================================

def select_vendor():
    """
    Wyświetla okno wyboru dostawcy profili.
    
    Returns:
        Klasa VendorProfile lub None jeśli anulowano
    """
    root = tk.Tk()
    root.withdraw()

    vendors = list_vendors()  # [(key, name), ...]

    choice_window = tk.Toplevel()
    choice_window.title("Wybierz dostawcę profili")
    choice_window.geometry("400x300")

    tk.Label(
        choice_window,
        text="Wybierz dostawcę systemu profili:",
        font=("Arial", 12, "bold")
    ).pack(pady=10)

    selected_vendor = tk.StringVar(value=vendors[0][0])

    for key, name in vendors:
        tk.Radiobutton(
            choice_window,
            text=name,
            variable=selected_vendor,
            value=key,
            font=("Arial", 10)
        ).pack(anchor="w", padx=20, pady=5)

    result = {"vendor": None}

    def on_confirm():
        result["vendor"] = selected_vendor.get()
        choice_window.destroy()

    def on_cancel():
        choice_window.destroy()

    tk.Button(
        choice_window, text="Potwierdź", command=on_confirm,
        font=("Arial", 10), bg="#4CAF50", fg="white", width=15
    ).pack(side="left", padx=20, pady=20)

    tk.Button(
        choice_window, text="Anuluj", command=on_cancel,
        font=("Arial", 10), bg="#f44336", fg="white", width=15
    ).pack(side="right", padx=20, pady=20)

    choice_window.wait_window()

    if not result["vendor"]:
        return None

    vendor_profile = VENDOR_PROFILES[result["vendor"]]
    print(f"✓ Wybrano dostawcę: {vendor_profile.NAME}")
    return vendor_profile


# ============================================
# WYBÓR PLIKÓW I FOLDERÓW
# ============================================

def select_file(file_type: str, title: str) -> str:
    """
    Otwiera dialog wyboru pliku.
    
    Args:
        file_type: Typ pliku ("MET", "CSV", "HTML", "ALL")
        title: Tytuł okna dialogowego
    
    Returns:
        str: Ścieżka do pliku lub None jeśli anulowano
    """
    root = tk.Tk()
    root.withdraw()

    filetypes = {
        "MET":  [("MET files", "*.MET"), ("All files", "*.*")],
        "CSV":  [("CSV files", "*.csv"), ("All files", "*.*")],
        "HTML": [("HTML files", "*.html"), ("All files", "*.*")],
        "ALL":  [("All files", "*.*")],
    }

    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes.get(file_type, filetypes["ALL"])
    )
    return file_path if file_path else None


def select_folder(title: str) -> str:
    """
    Otwiera dialog wyboru folderu.
    
    Args:
        title: Tytuł okna dialogowego
    
    Returns:
        str: Ścieżka do folderu lub None jeśli anulowano
    """
    root = tk.Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title=title)
    return folder_path if folder_path else None


# ============================================
# WYBÓR PROJEKTU
# ============================================

def select_project_from_list(projects_folder: str) -> str:
    """
    Wyświetla listę projektów do wyboru.
    Projekty to foldery zaczynające się od "20" (rok).
    
    Args:
        projects_folder: Ścieżka do folderu z projektami
    
    Returns:
        str: Nazwa wybranego projektu lub None
    """
    if not os.path.exists(projects_folder):
        messagebox.showerror("Błąd", f"Brak folderu: {projects_folder}")
        return None

    projects = sorted([
        d for d in os.listdir(projects_folder)
        if os.path.isdir(os.path.join(projects_folder, d)) and d.startswith("20")
    ], reverse=True)

    if not projects:
        messagebox.showerror("Błąd", "Brak projektów w folderze")
        return None

    root = tk.Tk()
    root.withdraw()

    choice_window = tk.Toplevel()
    choice_window.title("Wybierz projekt")
    choice_window.geometry("600x500")

    tk.Label(
        choice_window,
        text=f"Znaleziono {len(projects)} projektów:",
        font=("Arial", 12, "bold")
    ).pack(pady=10)

    # Lista z scrollbarem
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

    for project in projects:
        listbox.insert(tk.END, project)

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

    listbox.bind("<Double-Button-1>", lambda e: on_select())

    btn_frame = tk.Frame(choice_window)
    btn_frame.pack(pady=10)

    tk.Button(
        btn_frame, text="Wybierz", command=on_select,
        font=("Arial", 10), bg="#4CAF50", fg="white", width=15
    ).pack(side="left", padx=10)

    tk.Button(
        btn_frame, text="Anuluj", command=on_cancel,
        font=("Arial", 10), bg="#f44336", fg="white", width=15
    ).pack(side="left", padx=10)

    choice_window.wait_window()
    return selected_project["value"]


# ============================================
# PREFIKS DLA RZUTÓW
# ============================================

def get_project_prefix_from_met(met_filepath: str) -> str:
    """
    Generuje prefiks nazw plików na podstawie nazwy pliku .MET.
    Pozwala użytkownikowi edytować proponowany prefiks.
    
    Args:
        met_filepath: Ścieżka do pliku .MET
    
    Returns:
        str: Prefiks zakończony podkreślnikiem (np. "Klatka_schodowa_")
    """
    met_filename = os.path.basename(met_filepath)
    base_name = os.path.splitext(met_filename)[0]
    words = re.findall(r"\w+", base_name)
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


# ============================================
# WALIDACJA SYSTEMU
# ============================================

def validate_system_name(system: str) -> str:
    """
    Waliduje nazwę systemu profili.
    Sugeruje poprawki przy literówkach.
    
    Args:
        system: Nazwa systemu do walidacji
    
    Returns:
        str: Zwalidowana nazwa lub None
    """
    if not system:
        messagebox.showerror("Błąd", "Nie podano nazwy systemu!")
        return None

    system = system.lower().strip().replace(" ", "")

    if system in KNOWN_SYSTEMS:
        return system

    # Szukaj podobnych
    matches = get_close_matches(system, KNOWN_SYSTEMS, n=3, cutoff=0.6)

    if matches:
        root = tk.Tk()
        root.withdraw()
        suggestion = messagebox.askyesno(
            "Literówka?",
            f"Wpisano: {system}\n\n"
            f"Czy chodziło o: {matches[0]}?\n\n"
            f"TAK - użyj {matches[0]}\n"
            f"NIE - użyj '{system}'"
        )
        if suggestion:
            print(f"✅ Poprawiono: {system} → {matches[0]}")
            return matches[0]

    messagebox.showwarning(
        "Uwaga!",
        f"Używam: {system}\n\n"
        f"⚠️ To nieznany system!\n"
        f"Literówka spowoduje CHAOS w bazie danych."
    )
    return system


def validate_and_choose_system(csv_path: str, extract_system_fn) -> str:
    """
    Wykrywa system z CSV i pozwala użytkownikowi potwierdzić/poprawić.
    
    Args:
        csv_path: Ścieżka do pliku CSV
        extract_system_fn: Funkcja wyciągająca system z CSV
    
    Returns:
        str: Nazwa systemu lub None
    """
    detected = extract_system_fn(csv_path)

    if not detected:
        root = tk.Tk()
        root.withdraw()
        system = simpledialog.askstring(
            "System nieznany",
            f"Nie wykryto systemu w CSV.\n\n"
            f"Popularne systemy:\n{', '.join(KNOWN_SYSTEMS[:10])}\n\n"
            f"Wpisz system (małe litery, np. mb-77hs):"
        )
        if system:
            system = system.lower().strip().replace(" ", "")
        return validate_system_name(system)

    if detected in KNOWN_SYSTEMS:
        print(f"✅ System wykryty: {detected}")
        return detected

    # Nieznany - szukaj podobnych
    matches = get_close_matches(detected, KNOWN_SYSTEMS, n=1, cutoff=0.7)

    if matches:
        root = tk.Tk()
        root.withdraw()
        confirm = messagebox.askyesno(
            "Potwierdzenie systemu",
            f"Wykryto: {detected}\n\n"
            f"Czy chodziło o: {matches[0]}?\n\n"
            f"TAK - użyj {matches[0]}\n"
            f"NIE - użyj '{detected}'"
        )
        if confirm:
            print(f"✅ Poprawiono: {detected} → {matches[0]}")
            return matches[0]

    root = tk.Tk()
    root.withdraw()
    confirm = messagebox.askyesno(
        "Nieznany system",
        f"Wykryto: {detected}\n\n"
        f"To nowy system - kontynuować?\n\n"
        f"TAK - użyj '{detected}'\n"
        f"NIE - pozwól mi wpisać ręcznie"
    )

    if confirm:
        print(f"⚠️ Nowy system: {detected}")
        return detected

    corrected = simpledialog.askstring(
        "Popraw system",
        f"Wykryto: {detected}\n\n"
        f"Popularne:\n{', '.join(KNOWN_SYSTEMS[:8])}\n\n"
        f"Wpisz poprawną nazwę:",
        initialvalue=detected
    )
    if corrected:
        corrected = corrected.lower().strip().replace(" ", "")
    return validate_system_name(corrected)


# ============================================
# DIALOG KOLORÓW
# ============================================

def confirm_detected_colors(detected_colors: list):
    """
    Pokazuje okno informacyjne z wykrytymi kolorami.
    
    Args:
        detected_colors: Lista kodów kolorów (np. ["B4", "I4", "D"])
    """
    if not detected_colors:
        return

    root = tk.Tk()
    root.withdraw()

    colors_text = ", ".join(detected_colors)

    messagebox.showinfo(
        "Wykryte kolory okuć",
        f"Projekt zawiera {len(detected_colors)} kolory:\n\n"
        f"🎨 {colors_text}\n\n"
        f"Wszystkie okucia zostaną zapisane z sufiksem 'X'\n"
        f"(bez względu na kolor)."
    )

    print(f"    🎨 Kolory w projekcie: {colors_text}")