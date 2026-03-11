# core/context_builder.py
"""
Moduł odpowiedzialny za budowanie kontekstu danych dla szablonu dokumentacji.

Zawiera logikę:
- pobierania danych z CSV i bazy produktów
- budowania struktur systemów, pozycji, profili i okuć
- przygotowania kompletnego kontekstu dla Jinja2
"""

import datetime
import os
import re
from typing import Any

from config import AUTHOR_NAME, PROJECTS_IMAGES

# ==========================================
# HELPERS — PROJEKT
# ==========================================


def parse_project_name(folder_name: str) -> dict[str, str]:
    """
    Rozbija nazwę folderu na części (Klient, Numer, Opis).

    Input: "2025-18-12_Produkcja Beddeleem_ P241031 BMEIA AUSTRIA"
    Output: {"client": "Produkcja Beddeleem", "number": "P241031", "desc": "BMEIA AUSTRIA"}
    """
    name_clean = re.sub(r"^\d{4}[-.]\d{2}[-.]\d{2}[_ ]?", "", folder_name).strip()
    match = re.search(r"\b(P\d{5,6})\b", name_clean)

    if match:
        number = match.group(1)
        parts = name_clean.split(number)
        client = parts[0].strip(" _-")
        desc = parts[1].strip(" _-") if len(parts) > 1 else ""
        return {"client": client, "number": number, "desc": desc}
    else:
        return {"client": name_clean, "number": "", "desc": ""}


def get_view_for_position(project_name: str, pos_num: str) -> str:
    """
    Szuka pliku graficznego rzutu dla danej pozycji.

    Returns:
        Ścieżka relatywna dla Markdowna lub placeholder
    """
    views_dir = os.path.join(PROJECTS_IMAGES, project_name, "views")
    pattern = os.path.join(views_dir, f"*Poz_{pos_num}.jpg")

    import glob

    found_files = glob.glob(pattern)

    if found_files:
        full_path = found_files[0]
        filename = os.path.basename(full_path)
        safe_project_name = project_name.replace(" ", "%20")
        return f"../../projects_images/{safe_project_name}/views/{filename}"

    return "../../logo.png"  # Placeholder


# ==========================================
# HELPERS — PROFILE
# ==========================================


def get_profiles_for_position(
    csv_path: str,
    pos_num: str,
    vendor_key: str,
    vendor_cls: Any,
    sys_name: str,
    product_db: dict,
) -> list[dict]:
    """
    Pobiera i grupuje profile dla danej pozycji.

    Returns:
        Lista profili z metadanymi
    """
    from parsers.csv_parser import get_data_for_position

    raw_data = get_data_for_position(csv_path, pos_num, vendor_cls, product_db)
    grouped = {}

    for prof in raw_data["profiles"]:
        raw_code = prof["code"]
        normalized_code = vendor_cls.parse_profile_code(raw_code)
        display_code = normalized_code if normalized_code else raw_code

        if display_code not in grouped:
            sys_folder = sys_name.upper()
            img_filename = f"{display_code}.jpg"
            img_path = f"../../images_db/{vendor_key}/profiles/{sys_folder}/{img_filename}"

            grouped[display_code] = {
                "code": display_code,
                "desc": prof["desc"],
                "image_path": img_path.replace(" ", "%20"),
                "quantities": [],
                "dimensions": [],
                "locations": [],
            }
        else:
            if not grouped[display_code]["desc"] and prof["desc"]:
                grouped[display_code]["desc"] = prof["desc"]

        if prof["quantity"]:
            grouped[display_code]["quantities"].append(prof["quantity"])
        if prof["dimensions"]:
            grouped[display_code]["dimensions"].append(prof["dimensions"])
        if prof["location"] and prof["location"] != "—":
            grouped[display_code]["locations"].append(prof["location"])

    processed_profiles = []
    for code, data in grouped.items():
        unique_locs = list(dict.fromkeys(data["locations"]))
        processed_profiles.append(
            {
                "code": code,
                "desc": data["desc"],
                "image_path": data["image_path"],
                "quantity": "<br>".join(data["quantities"]),
                "dimensions": "<br>".join(data["dimensions"]),
                "location": "<br>".join(unique_locs) if unique_locs else "—",
            }
        )

    return processed_profiles


# ==========================================
# HELPERS — OKUCIA
# ==========================================


def get_hardware_for_position(
    csv_path: str,
    pos_num: str,
    vendor_key: str,
    vendor_cls: Any,
    sys_name: str,
    product_db: dict,
    all_hardware_map: dict,
) -> list[dict]:
    """
    Pobiera i przetwarza okucia dla danej pozycji.

    Returns:
        Lista okuć z metadanymi i linkami do katalogów
    """
    from core.catalogs import build_hardware_catalog_link
    from parsers.csv_parser import get_data_for_position

    pos_data = get_data_for_position(csv_path, pos_num, vendor_cls, product_db)
    hardware_list = []

    for hw in pos_data["hardware"]:
        raw_code = hw["code"]
        desc = hw["desc"]
        normalized_code = vendor_cls.parse_profile_code(raw_code)
        display_code = normalized_code if normalized_code else raw_code

        # Dodaj do globalnej mapy
        if display_code not in all_hardware_map:
            all_hardware_map[display_code] = {
                "desc": desc,
                "sys_name": sys_name,
            }

        safe_code = display_code.replace(" ", "%20")
        checklist_id = f"{display_code.replace(' ', '_')}_{pos_num}"

        # Wylicz link + sprawdź istnienie pliku
        catalog_link, file_exists = build_hardware_catalog_link(vendor_key, sys_name, display_code)

        status_icon = "✅" if file_exists else "🔴"
        status_text = "" if file_exists else "Brak w katalogu"

        hardware_list.append(
            {
                "code": display_code,
                "desc": desc,
                "quantity": hw["quantity"],
                "image_path": f"../../images_db/{vendor_key}/hardware/{safe_code}.jpg",
                "catalog_link": catalog_link,
                "file_exists": file_exists,
                "status_icon": status_icon,
                "status_text": status_text,
                "checklist_id": checklist_id,
            }
        )

    hardware_list.sort(key=lambda x: x["code"])
    return hardware_list


# ==========================================
# HELPERS — DOKUMENTY
# ==========================================


def build_job_links(timestamp: str) -> list[dict]:
    """
    Zwraca wiersze dla JOB (lokalny i sieciowy).
    """
    from config import JOB_PATH_LOCAL, RELATIVE_DEPTH_TO_Z

    def _url_encode(path_str: str) -> str:
        return path_str.replace(" ", "%20")

    local_norm = JOB_PATH_LOCAL.replace("\\", "/")
    job_network_rel = f"{RELATIVE_DEPTH_TO_Z}/JOB/Lotti/"

    local_link = _url_encode(f"{local_norm}/")
    network_link = _url_encode(job_network_rel)

    return [
        {
            "name": "Plik JOB",
            "date": timestamp,
            "path": local_link,
            "type": "network_local",
        },
        {
            "name": "Plik JOB",
            "date": timestamp,
            "path": network_link,
            "type": "network_remote",
        },
    ]


def build_documents_list(
    doc_folder: str,
    project_folder_name: str,
    timestamp: str,
) -> list[dict]:
    """
    Buduje listę dokumentów z folderu projektu + wiersze JOB.
    """
    from core.file_scanner import scan_project_documents

    documents = []

    # Skanuj folder
    scanned = scan_project_documents(doc_folder, project_folder_name)
    documents.extend(scanned)

    # Dodaj wiersze JOB
    job_links = build_job_links(timestamp)
    documents.extend(job_links)

    return documents


# ==========================================
# HELPERS — KATALOGI
# ==========================================


def build_catalogs_list(
    systems_map: dict[str, list],
    vendor_key: str,
) -> list[dict]:
    """
    Buduje listę katalogów systemowych.
    """
    from core.catalogs import find_system_catalog

    catalogs = []
    for sys_name in systems_map.keys():
        cat = find_system_catalog(vendor_key, sys_name)
        if cat:
            catalogs.append(cat)
        else:
            catalogs.append(
                {
                    "name": sys_name.upper(),
                    "date": "—",
                    "path": "#",
                    "status_icon": "⚪",
                    "status_text": "Brak katalogu",
                }
            )

    return catalogs


# ==========================================
# GŁÓWNA FUNKCJA — BUDOWANIE KONTEKSTU
# ==========================================


def prepare_context(
    csv_file: str,
    zm_file: str,
    project_folder_name: str,
    vendor_key: str,
    doc_folder: str,
) -> dict[str, Any]:
    """
    Buduje kompletny kontekst danych dla szablonu dokumentacji.

    Args:
        csv_file: ścieżka do pliku CSV z ilościami
        zm_file: ścieżka do pliku ZM z bazą wiedzy
        project_folder_name: nazwa folderu projektu
        vendor_key: klucz dostawcy (reynaers, aluprof, itp.)
        doc_folder: ścieżka do folderu z dokumentacją

    Returns:
        Słownik z kompletnym kontekstem dla Jinja2
    """
    from core.catalogs import build_hardware_catalog_link
    from core.versioning import get_version_history
    from parsers.csv_parser import get_positions_with_systems
    from parsers.db_builder import build_product_db
    from parsers.vendors import get_vendor_by_key

    print(f"⚙️  Generowanie danych dla: {project_folder_name}...")

    vendor_cls = get_vendor_by_key(vendor_key)
    proj_info = parse_project_name(project_folder_name)

    # Ścieżka wyjściowa PDF
    from config import DOCUMENTATION_PROJECTS_PATH

    proj_out_dir = os.path.join(DOCUMENTATION_PROJECTS_PATH, project_folder_name)
    pdf_filename = f"{project_folder_name}.pdf"
    pdf_output_path = os.path.join(proj_out_dir, pdf_filename).replace("\\", "/")

    # Baza produktów i systemy
    product_db = build_product_db(zm_file)
    systems_map = get_positions_with_systems(csv_file)
    timestamp = datetime.datetime.now().strftime("%d.%m.%Y")

    # Dokumenty
    documents = build_documents_list(doc_folder, project_folder_name, timestamp)

    # Katalogi
    catalogs = build_catalogs_list(systems_map, vendor_key)

    # Historia wersji
    proj_num = proj_info.get("number", "UNKNOWN")
    version_history = get_version_history(proj_num)

    # Kontekst bazowy
    context = {
        "project_folder_name": project_folder_name,
        "project_client": proj_info["client"],
        "project_number": proj_info["number"],
        "project_desc": proj_info["desc"],
        "logo_path": "../../logo.png",
        "pdf_output_path": pdf_output_path,
        "generation_date": timestamp,
        "systems": list(systems_map.keys()),
        "systems_data": {},
        "global_hardware": [],
        "documents": documents,
        "catalogs": catalogs,
        "instructions": [],
        "version_history": version_history,
        "doc_version": "1.0",  # placeholder, nadpisany w render_markdown
        "author": AUTHOR_NAME,
    }

    all_hardware_map = {}

    # Pętla po systemach i pozycjach
    for sys_name, positions in systems_map.items():
        system_entries = []

        for pos_num in positions:
            view_path = get_view_for_position(project_folder_name, pos_num)

            # Profile
            profiles = get_profiles_for_position(
                csv_file, pos_num, vendor_key, vendor_cls, sys_name, product_db
            )

            # Okucia
            hardware_list = get_hardware_for_position(
                csv_file,
                pos_num,
                vendor_key,
                vendor_cls,
                sys_name,
                product_db,
                all_hardware_map,
            )

            notes_placeholder = f"__BALOON_NOTES_PLACEHOLDER__POZ_{pos_num}__"

            system_entries.append(
                {
                    "number": pos_num,
                    "view_image_path": view_path,
                    "profiles": profiles,
                    "hardware": hardware_list,
                    "construction_notes": notes_placeholder,
                }
            )

        context["systems_data"][sys_name] = system_entries

    # Globalna tabela okuć
    for code, meta in sorted(all_hardware_map.items()):
        desc = meta["desc"]
        sys_name = meta["sys_name"]
        img_path = f"../../images_db/{vendor_key}/hardware/{code}.jpg"

        catalog_link, file_exists = build_hardware_catalog_link(vendor_key, sys_name, code)

        status_icon = "✅" if file_exists else "🔴"
        status_text = "Katalog OK" if file_exists else "Brak w katalogu"

        context["global_hardware"].append(
            {
                "code": code,
                "desc": desc,
                "image_path": img_path.replace(" ", "%20"),
                "catalog_link": catalog_link,
                "file_exists": file_exists,
                "status": f"{status_icon} {status_text}",
                "notes": "",
            }
        )

    return context
