"""
Core — Główna logika biznesowa generatora dokumentacji.

Moduły:
- catalogs — wyszukiwanie katalogów systemowych i okuć
- context_builder — budowanie kontekstu dla szablonów
- document_updater — renderowanie Markdown
- file_scanner — skanowanie folderów i dokumentów
- versioning — wersjonowanie i indeks projektów
"""

from core.catalogs import (
    # find_hardware_catalog_page,
    build_hardware_catalog_link,
    find_system_catalog,
    get_catalog_status,
)
from core.context_builder import (
    get_view_for_position,
    parse_project_name,
    prepare_context,
)
from core.document_updater import (
    format_dimensions,
    render_markdown,
    strip_date_from_folder_name,
)
from core.file_scanner import (
    extract_date_from_filename,
    find_project_folder,
    scan_project_documents,
    select_designer_and_find_project,
)
from core.versioning import (
    get_clean_system_name,
    get_next_version,
    get_version_history,
    update_project_index,
)

__all__ = [
    # catalogs
    "find_system_catalog",
    "find_hardware_catalog_page",
    "build_hardware_catalog_link",
    "get_catalog_status",
    # context_builder
    "prepare_context",
    "parse_project_name",
    "get_view_for_position",
    # document_updater
    "render_markdown",
    "format_dimensions",
    "strip_date_from_folder_name",
    # file_scanner
    "scan_project_documents",
    "extract_date_from_filename",
    "find_project_folder",
    "select_designer_and_find_project",
    # versioning
    "get_next_version",
    "update_project_index",
    "get_version_history",
    "get_clean_system_name",
]
