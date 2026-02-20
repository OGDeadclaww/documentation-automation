# note_harvester.py
"""
Note Harvester — Moduł do wyciągania uwag z dokumentacji Markdown.

Ten moduł:
1. Skanuje foldery z wygenerowaną dokumentacją (.md)
2. Wyciąga uwagi/notatki z sekcji konstrukcyjnych
3. Zapisuje do centralnej bazy danych (data/uwagi_db.json)
4. Umożliwia przeglądanie i eksport uwag
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

    Wykrywa wzorce:
    1. Sekcje "UWAGI" — listy pod nagłówkiem Uwagi/Notatki
    2. Tabelka okuć — kolumna "Uwagi" (ostatnia kolumna)
    3. Placeholdery — __BALOON_NOTES_PLACEHOLDER__POZ_X__
    """
    notes = []

    if not os.path.exists(md_file_path):
        return notes

    try:
        with open(md_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
    except Exception as e:
        print(f"⚠️ Nie można odczytać pliku: {e}")
        return notes

    project_number = extract_project_number(md_file_path)
    project_folder = os.path.basename(os.path.dirname(md_file_path))

    # ==========================================
    # WZORZEC 1: Sekcje UWAGI (listy pod nagłówkiem)
    # ==========================================
    in_uwagi_section = False

    for line in lines:
        ls = line.strip()

        # Wykryj początek sekcji UWAGI
        if re.match(r"#{1,4}\s*(UWAGI|Uwagi|NOTATKI|Notatki)", ls, re.IGNORECASE):
            in_uwagi_section = True
            continue

        # Wykryj koniec sekcji (nowy nagłówek)
        if in_uwagi_section and ls.startswith("#"):
            in_uwagi_section = False
            continue

        # Parsuj elementy w sekcji UWAGI
        if in_uwagi_section and ls.startswith("- "):
            # Skip "Brak Uwag"
            if "Brak Uwag" in ls or "Brak uwag" in ls:
                continue

            # Usuń prefix listy (- [ ], - )
            clean = re.sub(r"^[-*]\s*\[.\]\s*", "", ls)
            clean = re.sub(r"^[-*]\s*", "", clean).strip()

            if clean and len(clean) > 5:
                notes.append(
                    {
                        "project_number": project_number,
                        "project_folder": project_folder,
                        "position": "GENERAL",
                        "system": "ALL",
                        "hardware_code": None,
                        "note": clean,
                        "source_type": "uwagi_section",
                        "date_extracted": datetime.datetime.now().strftime("%d.%m.%Y"),
                        "source_file": md_file_path,
                    }
                )

    # ==========================================
    # WZORZEC 2: Tabelka — kolumna Uwagi
    # ==========================================
    for line in lines:
        ls = line.strip()
        if ls.startswith("|") and "|" in ls:
            cols = [c.strip() for c in ls.split("|") if c.strip()]
            # Potrzebujemy min. 6 kolumn (Kod, Opis, Rysunek, Katalog, Status, Uwagi)
            if len(cols) >= 6:
                code = cols[0].strip("`")
                uwagi = cols[-1].strip()

                # Wyczyść z emoji
                clean_u = re.sub(r"[🔴✅📐]", "", uwagi).strip()

                # Sprawdź czy to nie jest puste lub placeholder
                if (
                    clean_u
                    and len(clean_u) > 3
                    and clean_u not in ["—", "", "Brak", "N/A"]
                ):
                    notes.append(
                        {
                            "project_number": project_number,
                            "project_folder": project_folder,
                            "position": "UNKNOWN",
                            "system": "UNKNOWN",
                            "hardware_code": code,
                            "note": clean_u,
                            "source_type": "table_uwagi",
                            "date_extracted": datetime.datetime.now().strftime(
                                "%d.%m.%Y"
                            ),
                            "source_file": md_file_path,
                        }
                    )

    # ==========================================
    # WZORZEC 3: Placeholdery
    # ==========================================
    for match in re.finditer(r"__BALOON_NOTES_PLACEHOLDER__POZ_(\w+)__", content):
        notes.append(
            {
                "project_number": project_number,
                "project_folder": project_folder,
                "position": f"Poz_{match.group(1)}",
                "note": "[Uwaga do wypełnienia]",
                "source_type": "placeholder",
                "date_extracted": datetime.datetime.now().strftime("%d.%m.%Y"),
                "source_file": md_file_path,
            }
        )

    return notes


def extract_project_number(md_file_path: str) -> str:
    """
    Wyciąga numer projektu z ścieżki lub nazwy pliku.
    """
    folder_name = os.path.basename(os.path.dirname(md_file_path))
    match = re.search(r"\b(P\d{5,6})\b", folder_name)
    if match:
        return match.group(1)

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
    """Ładuje bazę uwag z pliku JSON."""
    if not os.path.exists(UWAGI_DB_PATH):
        return []

    try:
        with open(UWAGI_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Nie można odczytać bazy uwag: {e}")
        return []


def save_uwagi_db(notes: List[Dict]) -> bool:
    """Zapisuje bazę uwag do pliku JSON."""
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
    """
    existing = load_uwagi_db()

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
            if update_existing:
                idx = existing_index[key]
                existing[idx]["date_extracted"] = new_note["date_extracted"]
                existing[idx]["source_file"] = new_note["source_file"]
                updated_count += 1
        else:
            existing.append(new_note)
            updated_count += 1

    save_uwagi_db(existing)
    return updated_count


# ==========================================
# EKSPORT I RAPORTY
# ==========================================


def export_uwagi_to_csv(output_path: str = None) -> Optional[str]:
    """Eksportuje bazę uwag do pliku CSV."""
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
        "hardware_code",
        "note",
        "source_type",
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
    """Zwraca podsumowanie bazy uwag."""
    notes = load_uwagi_db()

    if not notes:
        return {"total": 0}

    by_status = {}
    for note in notes:
        status = note.get("source_type", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    by_project = {}
    for note in notes:
        proj = note.get("project_number", "UNKNOWN")
        by_project[proj] = by_project.get(proj, 0) + 1

    return {
        "total": len(notes),
        "by_source_type": by_status,
        "by_project": by_project,
        "last_extracted": (
            max(n.get("date_extracted", "") for n in notes) if notes else None
        ),
    }


# ==========================================
# CLI
# ==========================================


def cli_harvest() -> None:
    """Tryb CLI: Skanuj projekty i zaktualizuj bazę uwag."""
    print("🔍 Note Harvester — Skanowanie projektów...")
    print("=" * 50)

    notes = scan_projects_for_notes()

    if not notes:
        print("⚠️ Nie znaleziono żadnych uwag")
        return

    print(f"\n📊 Znaleziono {len(notes)} uwag")
    merged = merge_uwagi_db(notes)
    print(f"✅ Zaktualizowano bazę: {merged} zmian")

    summary = get_uwagi_summary()
    print("\n📋 Podsumowanie:")
    print(f"  Total: {summary.get('total', 0)}")
    print(f"  Po źródle: {summary.get('by_source_type', {})}")
    print(f"  Po projektach: {summary.get('by_project', {})}")


def cli_export() -> None:
    """Tryb CLI: Eksportuj bazę uwag do CSV."""
    print("📊 Note Harvester — Eksport do CSV...")
    print("=" * 50)

    output_path = export_uwagi_to_csv()
    if output_path:
        print(f"✅ Wyeksportowano do: {output_path}")


def cli_summary() -> None:
    """Tryb CLI: Pokaż podsumowanie bazy uwag."""
    print("📋 Note Harvester — Podsumowanie...")
    print("=" * 50)

    summary = get_uwagi_summary()

    if summary.get("total", 0) == 0:
        print("⚠️ Brak uwag w bazie")
        return

    print(f"Total uwag: {summary.get('total', 0)}")
    print(f"Po źródle: {summary.get('by_source_type', {})}")
    print(f"Po projektach: {summary.get('by_project', {})}")


def main():
    """Główna funkcja CLI."""
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
