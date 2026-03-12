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
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# ==========================================
# KONFIGURACJA
# ==========================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

try:
    from config import DOCUMENTATION_PROJECTS_PATH, OPERATORS_DOCS_PATH
except ImportError:
    DOCUMENTATION_PROJECTS_PATH = "./output"
    OPERATORS_DOCS_PATH = "./operators"


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
# SKRÓTY DLA OPERATORÓW
# ==========================================


def create_pdf_shortcut(pdf_path: str, dir_name: str, file_prefix: str) -> bool:
    """
    Tworzy folder i skrót Windows (.lnk) do najnowszego PDF dla operatorów.

    Args:
        pdf_path: pełna ścieżka do PDF
        dir_name: nazwa folderu docelowego (np. 'P241031' lub '2025-11-17_DRZWI_EI60_SOLEC')
        file_prefix: prefix nazwy skrótu (np. 'P241031' lub 'DRZWI_EI60_SOLEC')
    """
    shortcut_dir = Path(OPERATORS_DOCS_PATH) / dir_name
    shortcut_path = shortcut_dir / f"{file_prefix}_Dokumentacja.lnk"

    try:
        shortcut_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Folder operatorów: {shortcut_dir}")
    except Exception as e:
        print(f"⚠️ Błąd tworzenia folderu: {e}")
        return False

    if shortcut_path.exists():
        shortcut_path.unlink()
        print(f"🗑️ Usunięto stary skrót: {shortcut_path.name}")

    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{pdf_path}"
$Shortcut.Description = "Dokumentacja {file_prefix}"
$Shortcut.Save()
"""

    try:
        subprocess.run(
            ["powershell", "-Command", ps_script], capture_output=True, text=True, check=True
        )
        print(f"✅ Utworzono skrót: {shortcut_path}")
        print(f"   → wskazuje na: {pdf_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Błąd PowerShell: {e.stderr}")
        return False
    except Exception as e:
        print(f"⚠️ Błąd tworzenia skrótu: {e}")
        return False


# ==========================================
# RENDEROWANIE
# ==========================================


def render_markdown(
    context: dict, output_filename: str = None, template_name: str = "project_doc.md.j2"
) -> str | None:
    """Renderuje szablon Jinja2 do pliku MD w folderze projektu."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters["format_dim"] = format_dimensions

    try:
        template = env.get_template(template_name)
    except Exception as e:
        print(f"❌ Błąd ładowania szablonu: {e}")
        return None

    if output_filename is None:
        proj_folder = context.get("project_folder_name", "Dokumentacja")
        clean_name = strip_date_from_folder_name(proj_folder)
        output_filename = f"{clean_name}.md"

    proj_folder_name = context.get("project_folder_name", "projekt")
    out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, proj_folder_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, output_filename)

    # Wylicz wersję PRZED renderowaniem
    from core.versioning import get_next_version, update_project_index

    version = get_next_version(out_path, context.get("project_number", "UNKNOWN"))

    # === POPRAWKA HISTORII v1.0 ===
    updated_history = context.get("version_history", [])

    # Jeśli podbijamy wersję, a historia jest pusta, wstrzykujemy v1.0
    if version != "1.0" and not updated_history:
        try:
            from datetime import datetime

            ctime = os.path.getctime(out_path)
            date_str = datetime.fromtimestamp(ctime).strftime("%d.%m.%Y")
        except Exception:
            date_str = context.get("generation_date", "Nieznana")

        updated_history.append(
            {"version": "1.0", "date": date_str, "author": "System (odtworzone)"}
        )

    # Nowy wpis historii dla obecnej generacji
    new_history_entry = {
        "version": version,
        "date": context.get("generation_date", ""),
        "author": context.get("author", ""),
    }
    updated_history.append(new_history_entry)

    # Zaktualizuj kontekst
    context["doc_version"] = version
    context["version_history"] = updated_history

    rendered = template.render(context)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✅ Wygenerowano: {os.path.abspath(out_path)} (v{version})")
    print(f"📋 Historia: {[e['version'] for e in updated_history]}")

    # Zapisz do indeksu
    update_project_index(context, version)

    # === AUTOMATYCZNY SKRÓT DLA OPERATORÓW ===
    pdf_path = context.get("pdf_output_path", "")
    project_number = context.get("project_number", "").strip()

    clean_name = strip_date_from_folder_name(proj_folder_name)

    if pdf_path:
        dir_name = project_number if project_number else proj_folder_name
        file_prefix = project_number if project_number else clean_name

        print("\n📂 Tworzenie skrótu dla operatorów...")
        create_pdf_shortcut(pdf_path, dir_name, file_prefix)
    else:
        print("⚠️ Pominięto skrót (brak ścieżki PDF)")

    return out_path
