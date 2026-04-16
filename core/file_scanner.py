# core/file_scanner.py
"""
Moduł odpowiedzialny za skanowanie folderów i dokumentów.

Zawiera logikę:
- wyszukiwania folderów projektów
- wyboru projektanta z GUI
- skanowania dokumentów w folderze projektu
- ekstrakcji dat z nazw plików
"""

import datetime
import os
import re
import tkinter as tk
from tkinter import SINGLE, Listbox, Scrollbar

from config import ZLECENIA_LOCAL

# ==========================================
# WYSZUKIWANIE PROJEKTÓW
# ==========================================


def find_project_folder(base_path: str, project_number: str, max_depth: int = 2) -> list[str]:
    """
    Rekurencyjnie szuka folderu zawierającego numer projektu w nazwie.

    Args:
        base_path: ścieżka bazowa do przeszukania
        project_number: numer projektu do znalezienia
        max_depth: maksymalna głębokość rekurencji

    Returns:
        Lista pasujących ścieżek
    """
    candidates = []
    pn_lower = project_number.lower()

    def _walk(path: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for entry in os.scandir(path):
                if entry.is_dir(follow_symlinks=False):
                    if pn_lower in entry.name.lower():
                        candidates.append(entry.path)
                    else:
                        _walk(entry.path, depth + 1)
        except PermissionError:
            pass

    _walk(base_path, 0)
    return candidates


def select_designer_and_find_project(project_number: str) -> str | None:
    """
    Flow:
      1. Odczytuje podfoldery ZLECENIA_LOCAL → lista projektantów
      2. Użytkownik wybiera projektanta z okna dialogowego
      3. W folderze projektanta szuka podfolderu pasującego do numeru projektu
      4. Jeśli znajdzie → zwraca pełną ścieżkę
      5. Jeśli nie → manual select_folder

    Args:
        project_number: numer projektu do znalezienia

    Returns:
        Ścieżka do folderu projektu lub None
    """
    # Import funkcji select_folder z gui.gui (unikamy cyklicznych importów)
    from gui.gui import select_folder

    # Odczytaj projektantów
    try:
        designers = sorted(
            [
                d
                for d in os.listdir(ZLECENIA_LOCAL)
                if os.path.isdir(os.path.join(ZLECENIA_LOCAL, d))
            ]
        )
    except Exception as e:
        print(f"⚠️ Nie można odczytać {ZLECENIA_LOCAL}: {e}")
        return select_folder("Wybierz folder z dokumentacją projektu")

    if not designers:
        return select_folder("Wybierz folder z dokumentacją projektu")

    # Okno z Listbox
    root = tk.Tk()
    root.title("Wybór projektanta")
    root.geometry("400x300")
    root.attributes("-topmost", True)

    label = tk.Label(
        root,
        text=f"Wybierz projektanta ({ZLECENIA_LOCAL}):",
        wraplength=380,
        justify=tk.LEFT,
    )
    label.pack(pady=10, padx=10)

    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    scrollbar = Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(
        frame,
        yscrollcommand=scrollbar.set,
        height=10,
        width=50,
        selectmode=SINGLE,
        font=("Arial", 10),
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    for designer in designers:
        listbox.insert(tk.END, designer)

    selected_designer = None

    def on_select():
        nonlocal selected_designer
        selection = listbox.curselection()
        if selection:
            selected_designer = designers[selection[0]]
            root.destroy()

    def on_cancel():
        root.destroy()

    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    ok_btn = tk.Button(button_frame, text="OK", command=on_select, width=10)
    ok_btn.pack(side=tk.LEFT, padx=5)

    cancel_btn = tk.Button(button_frame, text="Anuluj", command=on_cancel, width=10)
    cancel_btn.pack(side=tk.LEFT, padx=5)

    root.mainloop()

    if not selected_designer:
        return select_folder("Wybierz folder z dokumentacją projektu")

    designer_path = os.path.join(ZLECENIA_LOCAL, selected_designer)
    print(f"📁 Projektant: {selected_designer}")

    # Szukaj folderu projektu
    candidates = find_project_folder(designer_path, project_number, max_depth=2)

    if len(candidates) == 1:
        print(f"✅ Znaleziono folder dokumentacji: {candidates[0]}")
        return candidates[0]

    elif len(candidates) > 1:
        # Kilka pasujących — zapytaj użytkownika
        root2 = tk.Tk()
        root2.title("Wybór folderu projektu")
        root2.geometry("500x300")
        root2.attributes("-topmost", True)

        label2 = tk.Label(
            root2,
            text=f"Znaleziono kilka folderów dla {project_number}.\nWybierz właściwy:",
            wraplength=480,
            justify=tk.LEFT,
        )
        label2.pack(pady=10, padx=10)

        frame2 = tk.Frame(root2)
        frame2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar2 = Scrollbar(frame2)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

        listbox2 = Listbox(
            frame2,
            yscrollcommand=scrollbar2.set,
            height=10,
            width=60,
            selectmode=SINGLE,
            font=("Arial", 9),
        )
        listbox2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.config(command=listbox2.yview)

        for _, cand in enumerate(candidates):
            display = os.path.basename(cand)
            listbox2.insert(tk.END, display)

        selected_path = None

        def on_select2():
            nonlocal selected_path
            selection = listbox2.curselection()
            if selection:
                selected_path = candidates[selection[0]]
                root2.destroy()

        def on_cancel2():
            root2.destroy()

        button_frame2 = tk.Frame(root2)
        button_frame2.pack(pady=10)

        ok_btn2 = tk.Button(button_frame2, text="OK", command=on_select2, width=10)
        ok_btn2.pack(side=tk.LEFT, padx=5)

        cancel_btn2 = tk.Button(button_frame2, text="Anuluj", command=on_cancel2, width=10)
        cancel_btn2.pack(side=tk.LEFT, padx=5)

        root2.mainloop()

        if selected_path:
            return selected_path
        else:
            return select_folder("Wybierz folder z dokumentacją projektu")

    else:
        print(f"⚠️ Nie znaleziono folderu dla {project_number} w {designer_path}")
        return select_folder("Wybierz folder z dokumentacją projektu")


# ==========================================
# EKSTRAKCJA DAT
# ==========================================


def extract_date_from_filename(filename: str, folder_name: str = "") -> str:
    """
    Wyciąga datę z nazwy pliku w formacie DD.MM.YYYY.

    Szuka wzorców:
      - DD-MM-YY (np. 2-12-25, 23-01-26)
      - DD-MM-YYYY (np. 23-01-2026)
      - DD.MM.YY (np. 2.12.25)
      - DD.MM.YYYY (np. 23.01.2026)
      - YYYY-MM-DD (np. 2025-12-02)

    Jeśli nie znaleziona w pliku → szuka w nazwie folderu projektu.
    Fallback: dzisiejsza data.

    Returns:
        DD.MM.YYYY
    """
    # Pattern: DD-MM-YY lub DD-MM-YYYY
    match = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", filename)
    if match:
        day, month, year = match.groups()
        day, month = int(day), int(month)
        year = int(year)

        if year < 100:
            year = 2000 + year if year <= 50 else 1900 + year

        try:
            date_obj = datetime.datetime(year, month, day)
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass

    # Pattern: DD.MM.YY lub DD.MM.YYYY
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", filename)
    if match:
        day, month, year = match.groups()
        day, month = int(day), int(month)
        year = int(year)

        if year < 100:
            year = 2000 + year if year <= 30 else 1900 + year

        try:
            date_obj = datetime.datetime(year, month, day)
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass

    # Pattern: YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", filename)
    if match:
        year, month, day = match.groups()
        try:
            date_obj = datetime.datetime(int(year), int(month), int(day))
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            pass

    # Szukaj w nazwie folderu
    if folder_name:
        match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", folder_name)
        if match:
            year, month, day = match.groups()
            try:
                date_obj = datetime.datetime(int(year), int(month), int(day))
                return date_obj.strftime("%d.%m.%Y")
            except ValueError:
                pass

    # Fallback
    return datetime.datetime.now().strftime("%d.%m.%Y")


# ==========================================
# SKANOWANIE DOKUMENTÓW
# ==========================================


def scan_project_documents(doc_folder: str, project_folder_name: str = "") -> list[dict]:
    """
    Skanuje folder projektu — zwraca dokumenty z podziałem na typy.

    Args:
        doc_folder: ścieżka do folderu z dokumentacją
        project_folder_name: nazwa folderu projektu (do fallback na datę)

    Returns:
        Lista dokumentów z metadanymi
    """
    from config import RELATIVE_DEPTH_TO_BASE

    if not doc_folder or not os.path.isdir(doc_folder):
        return []

    found = []
    seen_types = {}

    try:
        entries = os.listdir(doc_folder)
    except PermissionError:
        print(f"⚠️ Brak dostępu do folderu: {doc_folder}")
        return []

    for filename in sorted(entries):
        filepath = os.path.join(doc_folder, filename)

        if not os.path.isfile(filepath):
            continue

        name_lower = filename.lower()
        ext = os.path.splitext(filename)[1].lower()
        name_no_ext = os.path.splitext(filename)[0]

        # Skip recover files dla DWG
        if ext == ".dwg" and "recover" in name_lower:
            continue

        label = None
        doc_type = None
        only_local = False

        if ext == ".dwg":
            label = "Rysunek .DWG"
            doc_type = "DWG"
        elif ext in (".met", ".rey", ".ali"):
            label = f"Plik .{ext[1:].upper()}"
            doc_type = ext[1:].upper()
            only_local = True
        elif ext == ".pdf":
            if name_no_ext.upper().startswith("LP") or name_lower.startswith("lista produkcyjna"):
                label = "Lista Produkcyjna"
                doc_type = "LP"
            elif name_no_ext.upper().startswith("LC") or name_lower.startswith("lista cięcia"):
                label = "Lista Cięcia"
                doc_type = "LC"
            elif name_no_ext.upper().startswith("RYS") or name_lower.startswith("rysunek"):
                label = "Rysunek"
                doc_type = "RYS"
            elif name_no_ext.upper().startswith("RK") or name_lower.startswith(
                "rysunek konstrukcyjny"
            ):
                label = "Rysunek Konstrukcyjny"
                doc_type = "RK"

        if not label:
            continue

        date_str = extract_date_from_filename(filename, project_folder_name)

        # Unikaj duplikatów
        if doc_type not in seen_types:
            seen_types[doc_type] = 0
        else:
            seen_types[doc_type] += 1
            label = f"{label} ({seen_types[doc_type] + 1})"

        seen_types[doc_type] += 1

        # Helper do ścieżek
        def _url_encode(path_str: str) -> str:
            return path_str.replace(" ", "%20")

        def _local_to_relative(local_path: str, is_local: bool = True) -> str:
            from config import ZLECENIA_LOCAL

            local_norm = local_path.replace("\\", "/")
            zlecenia_local_norm = ZLECENIA_LOCAL.replace("\\", "/")

            if is_local:
                return _url_encode(local_norm)

            if local_norm.lower().startswith(zlecenia_local_norm.lower()):
                suffix = local_norm[len(zlecenia_local_norm) :].lstrip("/")
                rel = f"{RELATIVE_DEPTH_TO_BASE}/Zlecenia/{suffix}"
                return _url_encode(rel)

            return _url_encode(local_norm)

        if only_local:
            local_link = _local_to_relative(filepath, is_local=True)
            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": local_link,
                    "type": "local_only",
                }
            )
        else:
            local_link = _local_to_relative(filepath, is_local=True)
            network_link = _local_to_relative(filepath, is_local=False)

            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": local_link,
                    "type": "network_local",
                }
            )
            found.append(
                {
                    "name": label,
                    "date": date_str,
                    "path": network_link,
                    "type": "network_remote",
                }
            )

    return found
