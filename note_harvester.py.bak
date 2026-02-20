# note_harvester.py
"""
Note Harvester — Moduł do wyciągania uwag z dokumentacji Markdown.

Ten moduł:
1. Skanuje foldery z wygenerowaną dokumentacją (.md)
2. Wyciąga uwagi/notatki z sekcji konstrukcyjnych
3. Zapisuje do centralnej bazy danych (data/uwagi_db.json)
4. Umożliwia przeglądanie i eksport uwag

Struktura uwagi:
{
    "project_number": "P241031",
    "position": "Poz_1",
    "system": "MB-70",
    "note": "Treść uwagi",
    "date_extracted": "20.02.2025",
    "source_file": "path/to/file.md"
}
"""

import os
import re
import json
import datetime
from typing import Dict, List, Optional, Any


# ==========================================
# KONFIGURACJA
# ==========================================

try:
    from config import DOCUMENTATION_PROJECTS_PATH
except ImportError:
    DOCUMENTATION_PROJECTS_PATH = "./output"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
UWAGI_DB_PATH = os.path.join(DATA_DIR, "uwagi_db.json")


# ==========================================
# HELPERS — ŚCIEŻKI
# ==========================================


def ensure_data_dir() -> None:
    """Upewnia się że folder data/ istnieje."""
    os.makedirs(DATA_DIR, exist_ok=True)


def get_uwagi_db_path() -> str:
    """Zwraca ścieżkę do bazy uwag."""
    ensure_data_dir()
    return UWAGI_DB_PATH


# ==========================================
# EKSTRAKCJA UWAG
# ==========================================


def extract_notes_from_markdown(md_file_path: str) -> List[Dict]:
    """
    Wyciąga uwagi z pojedynczego pliku Markdown.

    Szuka wzorców:
    - __BALOON_NOTES_PLACEHOLDER__POZ_X__
    - Sekcji z uwagami konstrukcyjnymi
    - Komentarzy w formacie <!-- note: ... -->

    Args:
        md_file_path: ścieżka do pliku .md

    Returns:
        Lista uwag z metadanymi
    """
    notes = []

    if not os.path.exists(md_file_path):
        print(f"⚠️ Plik nie istnieje: {md_file_path}")
        return notes

    try:
        with open(md_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ Nie można odczytać pliku: {e}")
        return notes

    # Ekstrahuj numer projektu z nazwy pliku/folderu
    project_number = extract_project_number(md_file_path)
    project_folder = os.path.basename(os.path.dirname(md_file_path))

    # Pattern 1: Placeholdery uwag
    placeholder_pattern = r"__BALOON_NOTES_PLACEHOLDER__POZ_(\w+)__"
    for match in re.finditer(placeholder_pattern, content):
        position = match.group(1)
        notes.append(
            {
                "project_number": project_number,
                "project_folder": project_folder,
                "position": f"Poz_{position}",
                "system": "UNKNOWN",  # Trzeba będzie powiązać z kontekstem
                "note": "[Uwaga do wypełnienia]",
                "status": "pending",
                "date_extracted": datetime.datetime.now().strftime("%d.%m.%Y"),
                "source_file": md_file_path,
            }
        )

    # Pattern 2: Komentarze HTML <!-- note: ... -->
    comment_pattern = r"<!--\s*note:\s*(.*?)\s*-->"
    for match in re.finditer(comment_pattern, content, re.DOTALL):
        note_text = match.group(1).strip()
        # Spróbuj wyciągnąć pozycję z kontekstu
        pos_match = re.search(
            r"Poz_(\w+)", content[max(0, match.start() - 100) : match.start()]
        )
        position = f"Poz_{pos_match.group(1)}" if pos_match else "UNKNOWN"

        notes.append(
            {
                "project_number": project_number,
                "project_folder": project_folder,
                "position": position,
                "system": "UNKNOWN",
                "note": note_text,
                "status": "extracted",
                "date_extracted": datetime.datetime.now().strftime("%d.%m.%Y"),
                "source_file": md_file_path,
            }
        )

    # Pattern 3: Sekcje z uwagami (### Uwagi, ## Notatki, itp.)
    section_pattern = r"#{1,3}\s*(Uwagi|Notatki|Komentarze)\s*\n(.*?)(?=\n#{1,3}|\Z)"
    for match in re.finditer(section_pattern, content, re.DOTALL | re.IGNORECASE):
        _ = match.group(1)  # Unused - section title not needed
        section_content = match.group(2).strip()

        # Podziel na poszczególne uwagi (po liniach)
        for line in section_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("-"):
                notes.append(
                    {
                        "project_number": project_number,
                        "project_folder": project_folder,
                        "position": "GENERAL",
                        "system": "ALL",
                        "note": line,
                        "status": "extracted",
                        "date_extracted": datetime.datetime.now().strftime("%d.%m.%Y"),
                        "source_file": md_file_path,
                    }
                )

    return notes


def extract_project_number(md_file_path: str) -> str:
    """
    Wyciąga numer projektu z ścieżki lub nazwy pliku.

    Przykłady:
    - .../P241031_BMEIA/file.md → P241031
    - .../Projekt_P241031/file.md → P241031
    """
    # Spróbuj z nazwy folderu
    folder_name = os.path.basename(os.path.dirname(md_file_path))
    match = re.search(r"\b(P\d{5,6})\b", folder_name)
    if match:
        return match.group(1)

    # Spróbuj z nazwy pliku
    file_name = os.path.basename(md_file_path)
    match = re.search(r"\b(P\d{5,6})\b", file_name)
    if match:
        return match.group(1)

    return "UNKNOWN"


# ==========================================
# SKANOWANIE PROJEKTÓW
# ==========================================


def scan_projects_for_notes(
    base_path: str = None,
    recursive: bool = True,
) -> List[Dict]:
    """
    Skanuje foldery projektów w poszukiwaniu plików .md z uwagami.

    Args:
        base_path: ścieżka bazowa (domyślnie DOCUMENTATION_PROJECTS_PATH)
        recursive: czy szukać rekurencyjnie

    Returns:
        Lista wszystkich znalezionych uwag
    """
    if base_path is None:
        base_path = DOCUMENTATION_PROJECTS_PATH

    all_notes = []

    if not os.path.exists(base_path):
        print(f"⚠️ Ścieżka nie istnieje: {base_path}")
        return all_notes

    # Znajdź wszystkie pliki .md
    md_files = []
    if recursive:
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(os.path.join(root, file))
    else:
        md_files = [
            os.path.join(base_path, f)
            for f in os.listdir(base_path)
            if f.endswith(".md")
        ]

    print(f"📄 Znaleziono {len(md_files)} plików .md")

    # Ekstrahuj uwagi z każdego pliku
    for md_file in md_files:
        notes = extract_notes_from_markdown(md_file)
        all_notes.extend(notes)
        if notes:
            print(f"  ✅ {os.path.basename(md_file)}: {len(notes)} uwag")

    return all_notes


# ==========================================
# BAZA DANYCH UWAG
# ==========================================


def load_uwagi_db() -> List[Dict]:
    """
    Ładuje bazę uwag z pliku JSON.

    Returns:
        Lista uwag lub pusta lista jeśli plik nie istnieje
    """
    if not os.path.exists(UWAGI_DB_PATH):
        return []

    try:
        with open(UWAGI_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Nie można odczytać bazy uwag: {e}")
        return []


def save_uwagi_db(notes: List[Dict]) -> bool:
    """
    Zapisuje bazę uwag do pliku JSON.

    Args:
        notes: lista uwag do zapisania

    Returns:
        True jeśli zapisano sukcesem
    """
    try:
        ensure_data_dir()
        with open(UWAGI_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
        print(f"💾 Zapisano {len(notes)} uwag do {UWAGI_DB_PATH}")
        return True
    except Exception as e:
        print(f"❌ Nie można zapisać bazy uwag: {e}")
        return False


def merge_uwagi_db(new_notes: List[Dict], update_existing: bool = True) -> int:
    """
    Scal nowe uwagi z istniejącą bazą.

    Args:
        new_notes: nowe uwagi do dodania
        update_existing: czy aktualizować istniejące uwagi

    Returns:
        Liczba dodanych/zaktualizowanych uwag
    """
    existing = load_uwagi_db()

    # Tworzymy indeks istniejących uwag
    existing_index = {}
    for i, note in enumerate(existing):
        key = (
            note.get("project_number", ""),
            note.get("position", ""),
            note.get("note", ""),
        )
        existing_index[key] = i

    updated_count = 0

    for new_note in new_notes:
        key = (
            new_note.get("project_number", ""),
            new_note.get("position", ""),
            new_note.get("note", ""),
        )

        if key in existing_index:
            # Uwaga już istnieje
            if update_existing:
                idx = existing_index[key]
                # Aktualizuj datę i status
                existing[idx]["date_extracted"] = new_note["date_extracted"]
                existing[idx]["source_file"] = new_note["source_file"]
                updated_count += 1
        else:
            # Nowa uwaga
            existing.append(new_note)
            updated_count += 1

    save_uwagi_db(existing)
    return updated_count


# ==========================================
# EKSPORT I RAPORTY
# ==========================================


def export_uwagi_to_csv(output_path: str = None) -> Optional[str]:
    """
    Eksportuje bazę uwag do pliku CSV.

    Args:
        output_path: ścieżka wyjściowa (domyślnie data/uwagi_export.csv)

    Returns:
        Ścieżka do wyeksportowanego pliku
    """
    import csv

    notes = load_uwagi_db()
    if not notes:
        print("⚠️ Brak uwag do eksportu")
        return None

    if output_path is None:
        output_path = os.path.join(DATA_DIR, "uwagi_export.csv")

    fieldnames = [
        "project_number",
        "project_folder",
        "position",
        "system",
        "note",
        "status",
        "date_extracted",
        "source_file",
    ]

    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(notes)

        print(f"📊 Wyeksportowano {len(notes)} uwag do {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Nie można wyeksportować uwag: {e}")
        return None


def get_uwagi_summary() -> Dict[str, Any]:
    """
    Zwraca podsumowanie bazy uwag.

    Returns:
        Dict ze statystykami
    """
    notes = load_uwagi_db()

    if not notes:
        return {"total": 0}

    # Grupowanie po statusie
    by_status = {}
    for note in notes:
        status = note.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    # Grupowanie po projekcie
    by_project = {}
    for note in notes:
        proj = note.get("project_number", "UNKNOWN")
        by_project[proj] = by_project.get(proj, 0) + 1

    # Grupowanie po pozycji
    by_position = {}
    for note in notes:
        pos = note.get("position", "UNKNOWN")
        by_position[pos] = by_position.get(pos, 0) + 1

    return {
        "total": len(notes),
        "by_status": by_status,
        "by_project": by_project,
        "by_position": by_position,
        "last_extracted": (
            max(n.get("date_extracted", "") for n in notes) if notes else None
        ),
    }


# ==========================================
# CLI — INTERFEJS LINII POLECEŃ
# ==========================================


def cli_harvest() -> None:
    """
    Tryb CLI: Skanuj projekty i zaktualizuj bazę uwag.
    """
    print("🔍 Note Harvester — Skanowanie projektów...")
    print("=" * 50)

    notes = scan_projects_for_notes()

    if not notes:
        print("⚠️ Nie znaleziono żadnych uwag")
        return

    print(f"\n📊 Znaleziono {len(notes)} uwag")

    merged = merge_uwagi_db(notes)
    print(f"✅ Zaktualizowano bazę: {merged} zmian")

    # Podsumowanie
    summary = get_uwagi_summary()
    print("\n📋 Podsumowanie:")
    print(f"  Total: {summary.get('total', 0)}")
    print(f"  Po statusie: {summary.get('by_status', {})}")
    print(f"  Ostatnia ekstrakcja: {summary.get('last_extracted', 'N/A')}")


def cli_export() -> None:
    """
    Tryb CLI: Eksportuj bazę uwag do CSV.
    """
    print("📊 Note Harvester — Eksport do CSV...")
    print("=" * 50)

    output_path = export_uwagi_to_csv()

    if output_path:
        print(f"✅ Wyeksportowano do: {output_path}")


def cli_summary() -> None:
    """
    Tryb CLI: Pokaż podsumowanie bazy uwag.
    """
    print("📋 Note Harvester — Podsumowanie...")
    print("=" * 50)

    summary = get_uwagi_summary()

    if summary.get("total", 0) == 0:
        print("⚠️ Brak uwag w bazie")
        return

    print(f"Total uwag: {summary.get('total', 0)}")
    print(f"Po statusie: {summary.get('by_status', {})}")
    print(f"Po projektach: {summary.get('by_project', {})}")
    print(f"Ostatnia ekstrakcja: {summary.get('last_extracted', 'N/A')}")


# ==========================================
# MAIN
# ==========================================


def main():
    """
    Główna funkcja CLI.
    """
    import sys

    if len(sys.argv) < 2:
        print("Note Harvester — Wyciąganie uwag z dokumentacji Markdown")
        print("=" * 50)
        print("Użycie:")
        print("  python note_harvester.py harvest  — Skanuj i zaktualizuj bazę")
        print("  python note_harvester.py export   — Eksportuj do CSV")
        print("  python note_harvester.py summary  — Pokaż podsumowanie")
        print("  python note_harvester.py          — To menu")
        return

    command = sys.argv[1].lower()

    if command == "harvest":
        cli_harvest()
    elif command == "export":
        cli_export()
    elif command == "summary":
        cli_summary()
    else:
        print(f"❌ Nieznana komenda: {command}")
        main()


if __name__ == "__main__":
    main()
