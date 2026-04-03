"""
PriceDrop Scanner — Deploy naar GitHub Pages.
Genereert de webapp HTML en pusht naar docs/ folder.
GitHub Pages serveert vanuit docs/ op main branch.
URL: https://thegaveryahoo.github.io/pricedrop/
"""

import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")


def deploy():
    """Genereer HTML en push naar GitHub Pages."""
    from upload_ha import generate_html

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

    # Fix manifest paths voor GitHub Pages (geen /local/ prefix)
    manifest_path = os.path.join(DOCS_DIR, "pricedrop_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            content = f.read()
        content = content.replace("/local/pricedrop.html", "/pricedrop/")
        content = content.replace("/local/pricedrop_icon.svg", "/pricedrop/pricedrop_icon.svg")
        with open(manifest_path, "w") as f:
            f.write(content)

    # Fix SW paths voor GitHub Pages
    sw_path = os.path.join(DOCS_DIR, "pricedrop_sw.js")
    if os.path.exists(sw_path):
        with open(sw_path, "r") as f:
            content = f.read()
        content = content.replace("/local/pricedrop_manifest.json", "/pricedrop/pricedrop_manifest.json")
        content = content.replace("/local/pricedrop_icon.svg", "/pricedrop/pricedrop_icon.svg")
        with open(sw_path, "w") as f:
            f.write(content)

    # Fix HTML: manifest en SW paths
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace('href="/local/pricedrop_manifest.json"', 'href="/pricedrop/pricedrop_manifest.json"')
    html = html.replace("'/local/pricedrop_sw.js'", "'/pricedrop/pricedrop_sw.js'")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

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
