# core/document_updater.py
"""
Moduł odpowiedzialny za renderowanie dokumentacji Markdown.

Zawiera logikę:
- renderowania szablonu Jinja2
- formatowania wymiarów i nazw
- zapisu plików wyjściowych
"""

import os
import re
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader


# ==========================================
# KONFIGURACJA
# ==========================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

try:
    from config import DOCUMENTATION_PROJECTS_PATH
except ImportError:
    DOCUMENTATION_PROJECTS_PATH = "./output"


# ==========================================
# FORMATOWANIE
# ==========================================


def format_dimensions(value: str) -> str:
    """
    Formatuje wymiary — kąty w nawiasach owijane w italic.

    Przykład:
        Input:  "1234x567 (45°)"
        Output: "1234x567 *(45°)*"
    """
    if not value or not isinstance(value, str):
        return value

    # Szuka nawiasów zawierających ' lub ° (kąty) i owija w * (italic)
    return re.sub(r"(\([^)]*[°'][^)]*\))", r"*\1*", value)


def strip_date_from_folder_name(folder_name: str) -> str:
    """
    Usuwa datę z początku nazwy folderu projektu.

    Przykład:
        Input:  "2025-18-12_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
        Output: "Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    """
    cleaned = re.sub(r"^\d{4}[-.]\d{2}[-.]\d{2}[_ ]?", "", folder_name).strip()
    return cleaned


def get_output_filename(project_folder_name: str) -> str:
    """
    Generuje nazwę pliku wyjściowego MD na podstawie nazwy folderu.

    Args:
        project_folder_name: nazwa folderu projektu

    Returns:
        Nazwa pliku z rozszerzeniem .md
    """
    clean_name = strip_date_from_folder_name(project_folder_name)
    return f"{clean_name}.md"


# ==========================================
# RENDEROWANIE
# ==========================================


def render_markdown(
    context: Dict,
    output_filename: Optional[str] = None,
    template_name: str = "project_doc.md.j2",
) -> Optional[str]:
    """
    Renderuje szablon Jinja2 do pliku MD w folderze projektu.

    Args:
        context: słownik z danymi do szablonu
        output_filename: opcjonalna nazwa pliku wyjściowego
        template_name: nazwa szablonu Jinja2

    Returns:
        Ścieżka do wygenerowanego pliku lub None w przypadku błędu
    """
    from core.versioning import get_next_version, update_project_index

    # Inicjalizacja Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters["format_dim"] = format_dimensions

    try:
        template = env.get_template(template_name)
    except Exception as e:
        print(f"❌ Błąd ładowania szablonu: {e}")
        return None

    # Nazwa pliku MD
    if output_filename is None:
        proj_folder = context.get("project_folder_name", "Dokumentacja")
        output_filename = get_output_filename(proj_folder)

    proj_folder_name = context.get("project_folder_name", "projekt")
    out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, proj_folder_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, output_filename)

    # Wylicz wersję PRZED renderowaniem
    version = get_next_version(out_path, context.get("project_number", "UNKNOWN"))

    # Nowy wpis historii
    new_history_entry = {
        "version": version,
        "date": context.get("generation_date", ""),
        "author": context.get("author", ""),
    }

    # Dodaj nowy wpis do historii
    updated_history = context.get("version_history", []) + [new_history_entry]

    # Zaktualizuj kontekst
    context["doc_version"] = version
    context["version_history"] = updated_history

    # Renderuj
    rendered = template.render(context)

    # Zapisz plik
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✅ Wygenerowano: {os.path.abspath(out_path)} (v{version})")
    print(f"📋 Historia: {[e['version'] for e in updated_history]}")

    # Zapisz do indeksu
    update_project_index(context, version)

    return out_path
