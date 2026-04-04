"""
PriceDrop Scanner — Upload naar Home Assistant via File Editor Ingress API.
Maakt de webapp beschikbaar via Nabu Casa op:
https://zgzpkdqrutdjraanfe4bmk44zi0h8yrd.ui.nabu.casa/local/pricedrop.html
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

# Laad gevoelige config uit .env bestand
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_env = _load_env()

# HA configuratie — uit .env, NIET hardcoded
HA_IP = _env.get("HA_IP", "")
HA_PORT = int(_env.get("HA_PORT", "8123"))
HA_TOKEN = _env.get("HA_TOKEN", "")
HA_INGRESS_SLUG = _env.get("HA_INGRESS_SLUG", "")
HA_FILE_PATH = _env.get("HA_FILE_PATH", "/homeassistant/www/pricedrop.html")
NABU_CASA_URL = _env.get("NABU_CASA_URL", "")

# Pad naar template
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pricedrop_app.html")


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
    html = html.replace("__APP_VERSION__", "3.1.0")

    return html


def save_for_cors_upload(html_content):
    """Sla de HTML op in C:\\Users\\Dave\\ zodat de CORS server het kan serveren."""
    upload_path = os.path.join("C:\\Users\\Dave", "pricedrop_upload.html")
    with open(upload_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[Upload] Opgeslagen als {upload_path}")
    print(f"[Upload] Beschikbaar via CORS server: http://localhost:9876/pricedrop_upload.html")
    return upload_path


def upload_to_ha(html_content):
    """Upload de HTML naar Home Assistant via File Editor Ingress API."""
    import requests

    # Sla eerst op voor CORS server (fallback)
    save_for_cors_upload(html_content)

    # Probeer direct via HA ingress API met sessie
    url = f"http://{HA_IP}:{HA_PORT}/api/hassio/ingress/{HA_INGRESS_SLUG}/api/save"

    # Methode 1: via auth/token flow
    try:
        # Eerst een sessie krijgen via de HA auth API
        session = requests.Session()
        auth_url = f"http://{HA_IP}:{HA_PORT}/auth/token"

        # Gebruik de long-lived access token direct via headers
        headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "filename": HA_FILE_PATH,
            "text": html_content,
        }

        resp = session.post(url, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            print(f"[Upload] Succesvol geupload naar HA!")
            print(f"[Upload] Beschikbaar op: {NABU_CASA_URL}")
            return True
        else:
            print(f"[Upload] Direct upload niet gelukt (HTTP {resp.status_code})")
            print(f"[Upload] Gebruik de Chrome-methode (zie hieronder)")
    except Exception as e:
        print(f"[Upload] Direct upload mislukt: {e}")

    # Fallback: instructies voor handmatige upload via Chrome console
    print(f"\n[Upload] === HANDMATIGE UPLOAD VIA CHROME ===")
    print(f"[Upload] 1. Open: http://{HA_IP}:{HA_PORT}/hassio/ingress/{HA_INGRESS_SLUG}")
    print(f"[Upload] 2. Plak dit in de Chrome console (F12):")
    print(f"""
fetch('http://localhost:9876/pricedrop_upload.html')
  .then(r=>r.text())
  .then(c=>fetch('/api/hassio_ingress/{HA_INGRESS_SLUG}/api/save',{{
    method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'filename='+encodeURIComponent('{HA_FILE_PATH}')+'&text='+encodeURIComponent(c)
  }})).then(r=>r.json()).then(j=>console.log('Upload result:',j))
""")
    return False


def upload():
    """Genereer HTML en upload naar HA."""
    print("[Upload] HTML genereren met deal data...")
    html = generate_html()
    print(f"[Upload] HTML klaar ({len(html)} bytes, {len(get_all_deals())} deals)")
    print(f"[Upload] Uploaden naar {HA_FILE_PATH}...")
    success = upload_to_ha(html)
    return success


if __name__ == "__main__":
    upload()
