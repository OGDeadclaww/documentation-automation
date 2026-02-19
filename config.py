# config.py
"""
Konfiguracja aplikacji rename_images.
Wszystkie stałe, ścieżki i ustawienia w jednym miejscu.
"""

import os
import re

# ============================================
# ŚCIEŻKI BAZOWE
# ============================================
BASE_PATH = r"Z:\Pawel_Pisarski\Dokumentacja"
PROJECTS_IMAGES = os.path.join(BASE_PATH, "projects_images")
IMAGES_DB = os.path.join(BASE_PATH, "images_db")

# Katalogi systemowe (PDF)
CATALOGS_PATH = r"Z:\Pawel_Pisarski\Katalogi"

# Zlecenia — lokalna kopia robocza
ZLECENIA_LOCAL = r"C:\Users\pawel\Desktop\Zlecenia"

# Zlecenia — kopia sieciowa
ZLECENIA_NETWORK = r"Z:\Pawel_Pisarski\Zlecenia"

# Pliki JOB
JOB_PATH_LOCAL = r"C:\JOB\Lotti"
JOB_PATH_NETWORK = r"Z:\JOB\Lotti"

# Dokumentacja wyjściowa (MD powstaje tutaj)
DOCUMENTATION_PROJECTS_PATH = r"Z:\Pawel_Pisarski\Dokumentacja\projects"

# Głębokość relatywna z folderu projektu do Pawel_Pisarski/
# projects/FOLDER_PROJEKTU/Dokumentacja.md
# ../   = projects/
# ../../ = Dokumentacja/
# ../../../ = Pawel_Pisarski/
RELATIVE_DEPTH_TO_BASE = "../../.."

# Będzie ustawione dynamicznie w main()
OUTPUT_VIEWS_DIR = None
OUTPUT_PROFILES_DIR = None
OUTPUT_HARDWARE_DIR = None

# ============================================
# USTAWIENIA KONFLIKTÓW
# ============================================
CONFLICTS_DIR = "_conflicts"
ENABLE_CONFLICT_MODE = True

# ============================================
# PREFERENCJE PLIKÓW
# ============================================
PREFERRED_EXT_ORDER = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]
MAX_PREFIX_LENGTH = 25

# ============================================
# BEZPIECZEŃSTWO
# ============================================
AUTH_FILE = os.path.join(BASE_PATH, "config", "authorized_users.json")
AUDIT_LOG = os.path.join(BASE_PATH, "logs", "audit_log.jsonl")

# ============================================
# REGEX PATTERNS
# ============================================
POZ_LINE_RE = re.compile(r"Poz\.\s*(\d+)")
SECTION_RE = re.compile(
    r"^(Profile|Profile dodatkowe|Akcesoria|Okucia)\b", re.IGNORECASE
)

# ============================================
# ZNANE SYSTEMY (dla walidacji)
# ============================================
KNOWN_SYSTEMS = [
    # Aluprof
    "mb-45",
    "mb-59s",
    "mb-60",
    "mb-70",
    "mb-77hs",
    "mb-78ei",
    "mb-86",
    "mb-86n",
    "mb-86si",
    "mb-118ei",
    "mb-104",
    "mb-sr50n",
    "mb-79n",
    # Reynaers
    "masterline-8",
    "cs-68",
    "cs-77",
    "cs-86",
    "cs-104",
    "cp-130",
    "cp-155",
    "slimline-38",
    "hi-finity",
    # Inne
    "imperial",
    "smart",
    "genesis",
]
