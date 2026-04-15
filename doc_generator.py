# doc_generator.py
"""
Generator Dokumentacji — Punkt Wejścia

Ten moduł jest teraz cienkim kontrolerem który:
1. Pobiera dane od użytkownika (CSV, ZM, projekt, vendor)
2. Buduje kontekst używając core.context_builder
3. Renderuje dokument używając core.document_updater

Logika biznesowa została przeniesiona do:
- core/catalogs.py — katalogi systemowe i okucia
- core/versioning.py — wersjonowanie i indeks
- core/file_scanner.py — skanowanie dokumentów
- core/document_updater.py — renderowanie Markdown
- core/context_builder.py — budowanie kontekstu
"""

import os
import sys

# Dodaj root do path dla importów
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.context_builder import prepare_context
from core.document_updater import render_markdown
from gui.gui import select_file, select_folder, select_vendor

# ==========================================
# MAIN — TRYB INTERAKTYWNY
# ==========================================


def main():
    """
    Główna funkcja uruchamiająca generator w trybie interaktywnym.
    """
    print("🚀 Tryb Interaktywny Generatora Dokumentacji")
    print("=" * 50)

    # === KROK 1: Wybór pliku CSV ===
    csv_path = select_file("CSV", "Wybierz plik LP_dane.csv (Ilości)")
    if not csv_path:
        print("❌ Anulowano wybór pliku CSV.")
        return

    # === KROK 2: Wybór pliku ZM ===
    zm_path = select_file("CSV", "Wybierz plik ZM_dane.csv (Baza Wiedzy)")
    if not zm_path:
        print("❌ Anulowano wybór pliku ZM.")
        return

    # === KROK 3: Wybór folderu projektu ===
    from config import PROJECTS_IMAGES

    base_proj_dir = PROJECTS_IMAGES
    print(f"📂 Wybierz folder projektu (rzuty) w: {base_proj_dir}")
    project_dir = select_folder("Wybierz folder projektu (zrzuty)")
    if not project_dir:
        print("❌ Anulowano wybór projektu.")
        return

    project_name = os.path.basename(project_dir)
    print(f"✅ Wybrano projekt: {project_name}")

    # === KROK 4: Wybór dostawcy ===
    vendor_profile = select_vendor()
    if not vendor_profile:
        print("❌ Anulowano wybór dostawcy.")
        return

    vendor_key = vendor_profile.KEY
    print(f"✅ Wybrano dostawcę: {vendor_key}")

    # === KROK 5: Wybór folderu dokumentacji ===
    print("\n📂 Wybierz folder z dokumentacją projektu")
    doc_folder = select_folder("Wybierz folder z dokumentacją projektu")

    if not doc_folder:
        print("⚠️ Nie wybrano folderu dokumentacji — sekcja Dokumentacja będzie pusta.")
        doc_folder = ""
    else:
        print(f"✅ Folder dokumentacji: {doc_folder}")

    # === KROK 6: Generowanie ===
    print("\n⚙️  Generowanie dokumentacji...")
    print("=" * 50)

    if os.path.exists(csv_path):
        # Buduj kontekst
        ctx = prepare_context(
            csv_file=csv_path,
            zm_file=zm_path,
            project_folder_name=project_name,
            vendor_key=vendor_key,
            doc_folder=doc_folder,
        )

        # Renderuj dokument
        render_markdown(ctx)

        print("\n" + "=" * 50)
        print("✅ Generowanie zakończone!")
    else:
        print(f"❌ Plik nie istnieje: {csv_path}")


if __name__ == "__main__":
    main()
