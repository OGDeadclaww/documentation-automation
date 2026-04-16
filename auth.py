# auth.py
"""
Autoryzacja użytkowników i logowanie audytowe.
"""

import getpass
import json
import os
import socket
from datetime import datetime
from tkinter import messagebox

from config import AUDIT_LOG, AUTH_FILE

# ============================================
# AUTORYZACJA
# ============================================


def get_current_user() -> str:
    """Zwraca nazwę bieżącego użytkownika systemu."""
    return getpass.getuser()


def check_authorization():
    """
    Sprawdza czy bieżący użytkownik ma uprawnienia do edycji.

    Przy pierwszym uruchomieniu tworzy plik konfiguracyjny
    z bieżącym użytkownikiem jako autoryzowanym.

    Raises:
        SystemExit: Gdy użytkownik nie ma uprawnień
    """
    current_user = get_current_user()

    # Pierwsze uruchomienie - utwórz plik
    if not os.path.exists(AUTH_FILE):
        _create_default_auth_file(current_user)
        print(f"✅ Utworzono plik autoryzacji. Użytkownik: {current_user}")
        return

    # Sprawdź uprawnienia
    auth_data = _load_auth_file()
    authorized = auth_data.get("authorized_editors", [])

    if current_user not in authorized:
        messagebox.showerror(
            "Brak uprawnień",
            f"Użytkownik '{current_user}' nie ma uprawnień do edycji.\n\n"
            f"Skontaktuj się z administratorem.",
        )
        exit(1)

    print(f"✅ Autoryzacja OK: {current_user}")


def _create_default_auth_file(current_user: str):
    """Tworzy domyślny plik autoryzacji."""
    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    auth = {
        "authorized_editors": [current_user, "pawel.pisarski", "PawelPisarski"],
        "authorized_viewers": ["*"],
    }
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(auth, f, indent=2, ensure_ascii=False)


def _load_auth_file() -> dict:
    """
    Wczytuje plik autoryzacji.

    Returns:
        dict: Dane autoryzacyjne

    Raises:
        FileNotFoundError: Gdy brak pliku
        json.JSONDecodeError: Gdy plik uszkodzony
    """
    with open(AUTH_FILE, encoding="utf-8") as f:
        return json.load(f)


# ============================================
# AUDIT LOG
# ============================================


def log_audit(action: str, details: dict):
    """
    Zapisuje wpis audytowy do pliku JSONL.

    Args:
        action: Nazwa akcji (np. "IMAGES_PROCESSED")
        details: Słownik ze szczegółami operacji

    Przykład:
        log_audit("IMAGES_PROCESSED", {
            "project": "2025-01-26_Klatka",
            "vendor": "aluprof",
            "system": "mb-78ei",
            "positions": 12,
            "hardware": 33
        })
    """
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "user": get_current_user(),
        "hostname": socket.gethostname(),
        "action": action,
        "details": details,
    }

    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
