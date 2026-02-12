# tests/conftest.py
import os
import sys
import pytest
import tempfile
import shutil

# Dodaj folder scripts/ do ścieżki - działa na dysku sieciowym
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# Debug - odkomentuj jeśli problemy z importami
# print(f"SCRIPTS_DIR: {SCRIPTS_DIR}")
# print(f"sys.path: {sys.path[:3]}")


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def sample_image(tmp_dir):
    img_path = os.path.join(tmp_dir, "img0.jpg")
    with open(img_path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0")
    return img_path


@pytest.fixture
def sample_csv(tmp_dir):
    csv_path = os.path.join(tmp_dir, "LP_dane.csv")
    content = (
        "System:;\n"
        ";MB-78EI HI;\n"
        "Poz. 1;;MB-78EI;Drzwi;\n"
        "Poz. 2;;MB-78EI;Okno;\n"
        "Kolor profili:;B4 [brązowy];I4 [czarny];D [srebrny]\n"
        "Akcesoria;\n"
        "8000;965;D;\n"
        "8000;4431;;\n"
        "8A022;27I4;;\n"
        "Profile dodatkowe;\n"
        "K51 8139;;\n"
        "Okucia;\n"
        "8032;2073;;\n"
    )
    with open(csv_path, "w", encoding="cp1250") as f:
        f.write(content)
    return csv_path


@pytest.fixture
def sample_html(tmp_dir):
    html_path = os.path.join(tmp_dir, "LP_images.html")
    images_dir = os.path.join(tmp_dir, "LP_images.files")
    os.makedirs(images_dir)

    for i in range(5):
        with open(os.path.join(images_dir, f"img{i}.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0")

    html = """<html><body><table>
    <tr><td></td><td>K51 8395 4R8017</td><td><img src="LP_images.files/img0.jpg"></td></tr>
    <tr><td></td><td>K51 8143 4R8017</td><td></td></tr>
    <tr><td></td><td></td><td><img src="LP_images.files/img1.jpg"></td></tr>
    <tr><td></td><td>120 470</td><td><img src="LP_images.files/img2.jpg"></td></tr>
    <tr><td></td><td>8000 965 D</td><td><img src="LP_images.files/img3.jpg"></td></tr>
    <tr><td></td><td>8A022 27I4</td><td><img src="LP_images.files/img4.jpg"></td></tr>
    </table></body></html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html_path, images_dir