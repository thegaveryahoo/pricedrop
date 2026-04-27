"""
PriceDrop Scanner — Deploy naar GitHub Pages.
Genereert de webapp HTML en pusht naar docs/ folder.
GitHub Pages serveert vanuit docs/ op main branch.
URL: https://thegaveryahoo.github.io/pricedrop/
"""

import os
import sys
import json
import sqlite3
import subprocess
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
TEMPLATE_PATH = os.path.join(PROJECT_DIR, "pricedrop_app.html")
APP_VERSION = "4.0.2"


def get_all_deals():
    """Haal alle deals uit de database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM deals ORDER BY discount_percent DESC")
    deals = [dict(row) for row in c.fetchall()]
    conn.close()
    return deals


def generate_html():
    """Genereer de webapp HTML met embedded deal data."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    deals = get_all_deals()
    now = datetime.now().strftime("%d-%m-%Y %H:%M")
    version = datetime.now().strftime("%Y%m%d%H%M")

    # Haal scan info op
    from database import get_last_scan
    last_scan = get_last_scan()
    shops_count = last_scan["shops_scanned"] if last_scan else 0

    # Vervang placeholders
    html = template.replace("__DEAL_DATA__", json.dumps(deals, ensure_ascii=False))
    html = html.replace("__VERSION__", version)
    html = html.replace("__SCAN_TIME__", now)
    html = html.replace("__SCAN_SHOPS__", str(shops_count))
    html = html.replace("__APP_VERSION__", APP_VERSION)

    return html


def deploy():
    """Genereer HTML en push naar GitHub Pages."""
    print("[GitHub] HTML genereren...")
    html = generate_html()

    # Schrijf naar docs/index.html (GitHub Pages entry point)
    os.makedirs(DOCS_DIR, exist_ok=True)
    index_path = os.path.join(DOCS_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Kopieer manifest + icoon + SW naar docs/
    for fname in ["pricedrop_manifest.json", "pricedrop_icon.svg", "pricedrop_sw.js"]:
        src = os.path.join(PROJECT_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DOCS_DIR, fname))

    print(f"[GitHub] docs/index.html geschreven ({len(html)} bytes)")

    # Op GitHub Actions doet de workflow zelf git add/commit/push
    if os.environ.get("GITHUB_ACTIONS"):
        print("[GitHub] Draait op GitHub Actions — git push wordt door workflow gedaan")
    else:
        # Lokaal: probeer git push
        try:
            os.chdir(PROJECT_DIR)
            subprocess.run(["git", "add", "docs/"], check=True, capture_output=True)
            result = subprocess.run(["git", "status", "--porcelain", "docs/"], capture_output=True, text=True)
            if result.stdout.strip():
                subprocess.run(["git", "commit", "-m", "Update deals data"], check=True, capture_output=True)
                subprocess.run(["git", "push"], check=True, capture_output=True)
                print("[GitHub] Gepusht naar GitHub Pages!")
                print("[GitHub] URL: https://thegaveryahoo.github.io/pricedrop/")
            else:
                print("[GitHub] Geen wijzigingen om te pushen")
        except subprocess.CalledProcessError as e:
            print(f"[GitHub] Git fout: {e.stderr if e.stderr else e}")
        except Exception as e:
            print(f"[GitHub] Fout: {e}")

    return True


if __name__ == "__main__":
    deploy()
