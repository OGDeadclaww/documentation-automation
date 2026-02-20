# core/versioning.py
"""
Moduł odpowiedzialny za wersjonowanie dokumentacji i zarządzanie indeksem projektów.

Zawiera logikę:
- wyliczania następnej wersji dokumentu
- aktualizacji indeksu projektów (project_index.json)
- czyszczenia nazw systemów
"""

import os
import json
from typing import Dict, List


# ==========================================
# KONFIGURACJA
# ==========================================

# Importy z config.py
try:
    from config import DOCUMENTATION_PROJECTS_PATH, IGNORED_SYSTEM_SUFFIXES
except ImportError:
    # Fallback dla testów
    DOCUMENTATION_PROJECTS_PATH = "./output"
    IGNORED_SYSTEM_SUFFIXES = ["HI", "SI", "ST"]


# ==========================================
# WERSJONOWANIE
# ==========================================


def get_next_version(md_output_path: str, project_number: str) -> str:
    """
    Wylicza następną wersję dokumentacji.

    Logika:
    - Plik MD nie istnieje → v1.0 (nowy projekt)
    - Plik MD istnieje + wersja w JSON zaczyna się od 1.x → v2.0
    - Plik MD istnieje + wersja >= 2.x → bump minor (2.0→2.1→2.2)

    Args:
        md_output_path: pełna ścieżka do pliku MD
        project_number: numer projektu (klucz w project_index.json)

    Returns:
        str: np. "1.0", "2.0", "2.1"
    """
    index_path = os.path.join(DOCUMENTATION_PROJECTS_PATH, "project_index.json")

    # Odczytaj aktualną wersję z JSON
    current_version = None
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
            current_version = index.get(project_number, {}).get("version", None)
        except (json.JSONDecodeError, KeyError):
            current_version = None

    # Plik MD nie istnieje → zawsze v1.0
    if not os.path.exists(md_output_path):
        print("📄 Nowy plik MD → v1.0")
        return "1.0"

    # Plik MD istnieje ale brak wersji w JSON → v2.0
    if current_version is None:
        print("📄 Plik MD istnieje, brak wersji w JSON → v2.0")
        return "2.0"

    # Parsuj aktualną wersję
    try:
        parts = current_version.split(".")
        major = int(parts[0])
        minor = int(parts[1])
    except (ValueError, IndexError):
        print(f"⚠️ Nie można sparsować wersji '{current_version}' → v2.0")
        return "2.0"

    # Wersja 1.x + plik istnieje → v2.0 (ręczna edycja → nowa major)
    if major == 1:
        print(f"📄 Wersja {current_version} + plik istnieje → v2.0")
        return "2.0"

    # Wersja 2.x+ → bump minor
    next_version = f"{major}.{minor + 1}"
    print(f"📄 Bump minor: {current_version} → {next_version}")
    return next_version


# ==========================================
# CZYSZCZENIE NAZW SYSTEMÓW
# ==========================================


def get_clean_system_name(raw_name: str) -> str:
    """
    Czyści nazwę systemu z nieistotnych końcówek (HI, SI, ST),
    ale zostawia BP, EI itp.
    """
    if not raw_name:
        return "UNKNOWN"

    parts = raw_name.split()
    clean_parts = []

    for p in parts:
        sub_parts = p.split("-")
        filtered_sub = [
            sp for sp in sub_parts if sp.upper() not in IGNORED_SYSTEM_SUFFIXES
        ]
        clean_parts.append("-".join(filtered_sub))

    return " ".join(clean_parts).strip()


# ==========================================
# INDEKS PROJEKTÓW
# ==========================================


def update_project_index(context: Dict, version: str) -> None:
    """
    Aktualizuje indeks projektów + zapisuje wersję i historię.

    Args:
        context: słownik z danymi projektu
        version: aktualna wersja dokumentu
    """
    index_path = os.path.join(DOCUMENTATION_PROJECTS_PATH, "project_index.json")

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except json.JSONDecodeError:
            index = {}
    else:
        index = {}

    proj_num = context.get("project_number") or "UNKNOWN"

    # Historia wersji
    history_entry = {
        "version": version,
        "date": context.get("generation_date", ""),
        "author": context.get("author", ""),
    }

    existing = index.get(proj_num, {})
    version_history = existing.get("version_history", [])
    version_history.append(history_entry)

    # Statystyki użycia
    usage_by_system = {}
    all_hardware = set()
    all_profiles = set()

    systems_data = context.get("systems_data", {})
    for sys_name, positions in systems_data.items():
        if sys_name not in usage_by_system:
            usage_by_system[sys_name] = {"profiles": set(), "hardware": set()}

        for pos in positions:
            for prof in pos.get("profiles", []):
                usage_by_system[sys_name]["profiles"].add(prof.get("code", ""))
                all_profiles.add(prof.get("code", ""))
            for hw in pos.get("hardware", []):
                usage_by_system[sys_name]["hardware"].add(hw.get("code", ""))
                all_hardware.add(hw.get("code", ""))

    usage_json = {
        sys: {
            "profiles": sorted(list(data["profiles"])),
            "hardware": sorted(list(data["hardware"])),
        }
        for sys, data in usage_by_system.items()
    }

    index[proj_num] = {
        "date": context.get("generation_date", ""),
        "client": context.get("project_client", ""),
        "desc": context.get("project_desc", ""),
        "folder": context.get("project_folder_name", ""),
        "systems": context.get("systems", []),
        "version": version,
        "version_history": version_history,
        "stats": {
            "hardware_count": len(all_hardware),
            "profiles_count": len(all_profiles),
        },
        "usage_by_system": usage_json,
    }

    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"💾 Zaktualizowano indeks: v{version}")
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać indeksu: {e}")


def get_version_history(project_number: str) -> List[Dict]:
    """
    Pobiera historię wersji dla danego projektu z indeksu.

    Args:
        project_number: numer projektu

    Returns:
        Lista wpisów historii wersji
    """
    index_path = os.path.join(DOCUMENTATION_PROJECTS_PATH, "project_index.json")

    if not os.path.exists(index_path):
        return []

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        return index.get(project_number, {}).get("version_history", [])
    except (json.JSONDecodeError, KeyError):
        return []
