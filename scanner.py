"""
PriceDrop Scanner v2 — Hoofdscript
Scrapt 14+ webshops incl. Tweakers Pricewatch, verifieert prijzen tegen marktwaarde, detecteert nep-kortingen.

Gebruik:
    python scanner.py          # Eenmalige scan
    python scanner.py --loop   # Continue scan (elke 15 min)
"""

import sys
import os
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    MIN_DISCOUNT_PERCENT, MIN_DISCOUNT_EUROS, MIN_ORIGINAL_PRICE,
    SCAN_INTERVAL_MINUTES, ACTIVE_SCRAPERS, MAX_PRICE_CHECKS,
)
from database import save_deal, update_deal_verification, get_recent_deals, start_scan_log, finish_scan_log, get_connection
from notifier import notify_deal, generate_html_report, send_windows_notification

# Importeer alle scrapers
from scrapers import bolcom, coolblue, amazon_nl, amazon_de, mediamarkt
from scrapers import pepper, mydealz, alternate, megekko, wehkamp, bcc, saturn, ibood
from scrapers import tweakers

SCRAPER_MAP = {
    "bolcom": bolcom,
    "coolblue": coolblue,
    "amazon_nl": amazon_nl,
    "amazon_de": amazon_de,
    "mediamarkt": mediamarkt,
    "pepper": pepper,
    "mydealz": mydealz,
    "tweakers": tweakers,
    "alternate": alternate,
    "megekko": megekko,
    "wehkamp": wehkamp,
    "bcc": bcc,
    "saturn": saturn,
    "ibood": ibood,
}


import re as _re

# === LAND-MAPPING: shop → land code ===
SHOP_COUNTRY = {
    "bolcom": "NL", "coolblue": "NL", "mediamarkt": "NL",
    "amazon_nl": "NL", "alternate": "NL", "megekko": "NL",
    "bcc": "NL", "wehkamp": "NL", "ibood": "NL",
    "pepper": "NL",  # nl.pepper.com = NL deals
    "tweakers": "NL",  # Tweakers Pricewatch = NL prijsvergelijker
    "amazon_de": "DE", "saturn": "DE", "mydealz": "DE",
}

COUNTRY_FLAGS = {
    "NL": "\U0001f1f3\U0001f1f1", "DE": "\U0001f1e9\U0001f1ea",
    "BE": "\U0001f1e7\U0001f1ea", "EU": "\U0001f1ea\U0001f1fa",
}


# === DUITS → NEDERLANDS vertaalwoordenboek ===
_DE_NL_WORDS = {
    # Basis
    "und": "en", "mit": "met", "für": "voor", "oder": "of", "nicht": "niet",
    "nur": "alleen", "bei": "bij", "auch": "ook", "nach": "naar", "noch": "nog",
    "über": "over", "unter": "onder", "aber": "maar", "bis": "tot",
    "sehr": "zeer", "alle": "alle", "jetzt": "nu", "hier": "hier",
    # Product-gerelateerd
    "schwarz": "zwart", "weiß": "wit", "rot": "rood", "blau": "blauw",
    "grün": "groen", "grau": "grijs", "gelb": "geel", "silber": "zilver",
    "gold": "goud", "klein": "klein", "groß": "groot", "neu": "nieuw",
    "alt": "oud", "schnell": "snel", "leicht": "licht",
    # Tech
    "Kopfhörer": "koptelefoon", "Lautsprecher": "luidspreker", "Tastatur": "toetsenbord",
    "Maus": "muis", "Bildschirm": "beeldscherm", "Drucker": "printer",
    "Festplatte": "harde schijf", "Speicher": "geheugen", "Akku": "accu",
    "Ladegerät": "oplader", "Kabel": "kabel", "Hülle": "hoes", "Tasche": "tas",
    "Staubsauger": "stofzuiger", "Kühlschrank": "koelkast", "Waschmaschine": "wasmachine",
    "Spülmaschine": "vaatwasser", "Kaffeemaschine": "koffiemachine",
    # Shopping
    "Angebot": "aanbieding", "Rabatt": "korting", "Versand": "verzending",
    "kostenlos": "gratis", "Preis": "prijs", "Gutschein": "kortingscode",
    "Preisfehler": "prijsfout", "Stück": "stuk", "Set": "set", "Pack": "pak",
    "Lieferung": "levering", "Garantie": "garantie", "Zubehör": "accessoire",
}

_DE_NL_PATTERN = _re.compile(
    r'\b(' + '|'.join(_re.escape(k) for k in sorted(_DE_NL_WORDS.keys(), key=len, reverse=True)) + r')\b',
    _re.IGNORECASE
)


def translate_to_dutch(name, source_country=""):
    """Vertaal Duitse productnamen naar Nederlands (best-effort)."""
    if source_country != "DE":
        return name
    def _replace(m):
        word = m.group(0)
        key = word if word in _DE_NL_WORDS else word.capitalize() if word.capitalize() in _DE_NL_WORDS else word.lower()
        replacement = _DE_NL_WORDS.get(key, _DE_NL_WORDS.get(word.capitalize(), word))
        # Behoud hoofdletter als origineel die had
        if word[0].isupper() and not replacement[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        return replacement
    return _DE_NL_PATTERN.sub(_replace, name)


# === CHINA / NIET-EU FILTER ===
_BLOCKED_SOURCES = [
    'aliexpress', 'ali express', 'banggood', 'gearbest', 'geekbuying',
    'tomtop', 'cafago', 'lightinthebox', 'wish.com', 'temu', 'shein',
    'dhgate', 'miniinthebox', 'dealextreme', 'dx.com', 'goboo',
    'joom', 'geekmaxi', 'gshopper', 'hekka',
]

# URLs die op China-shops wijzen
_BLOCKED_URLS = [
    'aliexpress.com', 'aliexpress.ru', 'ali.ski', 'a.]iexpress',
    'banggood.com', 'gearbest.com', 'temu.com', 'shein.com',
    'dhgate.com', 'wish.com', 'lightinthebox.com',
]


def is_china_deal(deal):
    """Check of een deal van een Chinese/niet-EU bron komt."""
    text = f"{deal.get('shop', '')} {deal.get('product_name', '')}".lower()
    url = deal.get('url', '').lower()
    # Check merchant/titel
    if any(blocked in text for blocked in _BLOCKED_SOURCES):
        return True
    # Check URL
    if any(blocked in url for blocked in _BLOCKED_URLS):
        return True
    return False


# Woorden die duiden op verzamel-deals / niet-specifieke producten
_VAGUE_PATTERNS = _re.compile(
    r'(?i)(meerdere\s+(spellen|producten|artikelen|items))'
    r'|(\bsale\b.*laagste\s+prijs)'
    r'|(\bdiverse\b)'
    r'|(\btot\s+\d+%\s+korting\b)'
    r'|(\bverschillende\b)'
    r'|(\bstarting\s+from\b)'
    r'|(\bab\s+\d)'
    r'|(\bvanaf\s+€)'
    r'|(\bmix\s*pack\b)'
    r'|(\bassortiment\b)'
    r'|(\bauswahl\b)'
)


def is_vague_deal(name):
    """Detecteer of een deal een verzamel-actie is in plaats van een specifiek product."""
    if _VAGUE_PATTERNS.search(name):
        return True
    # Te korte namen zijn vaak vaag
    words = name.strip().split()
    if len(words) < 3:
        return True
    return False


def filter_deals(deals, scraper_name=""):
    """Filter deals op de configuratie-criteria + verwijder vage/China-deals + voeg metadata toe."""
    filtered = []
    skipped_vague = 0
    skipped_china = 0

    # Bepaal land voor deze scraper
    country = SHOP_COUNTRY.get(scraper_name, "EU")

    for d in deals:
        if d["discount_percent"] < MIN_DISCOUNT_PERCENT:
            continue
        if d["original_price"] < MIN_ORIGINAL_PRICE:
            continue
        discount_euros = d["original_price"] - d["current_price"]
        if discount_euros < MIN_DISCOUNT_EUROS:
            continue
        if d["current_price"] <= 0 or d["original_price"] <= d["current_price"]:
            continue
        # Filter vage verzamel-deals
        if is_vague_deal(d["product_name"]):
            skipped_vague += 1
            continue
        # Filter China/AliExpress
        if is_china_deal(d):
            skipped_china += 1
            continue

        # Voeg land toe (scraper of deal-specifiek)
        deal_country = d.get("_country", country)
        d["country"] = deal_country
        d["country_flag"] = COUNTRY_FLAGS.get(deal_country, "")

        # Vertaal Duitse titels naar Nederlands
        d["product_name"] = translate_to_dutch(d["product_name"], deal_country)

        filtered.append(d)
    if skipped_vague:
        print(f"    ({skipped_vague} vage verzamel-deals overgeslagen)")
    if skipped_china:
        print(f"    ({skipped_china} China/niet-EU deals geblokkeerd)")
    return filtered


def cleanup_old_deals(max_age_hours=48):
    """Verwijder deals ouder dan max_age_hours uit de database."""
    from database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM deals WHERE found_at < datetime('now', ?)", (f"-{max_age_hours} hours",))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"[Cleanup] {deleted} verlopen deals verwijderd (ouder dan {max_age_hours}u)")


def run_scan():
    """Voer een volledige scan uit van alle actieve scrapers + prijsverificatie."""
    # Ruim oude deals op VOOR de scan
    cleanup_old_deals(48)

    scan_id = start_scan_log()

    print(f"\n{'='*60}")
    print(f"  PriceDrop Scanner v2 — {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    print(f"  {len(ACTIVE_SCRAPERS)} shops | Drempel: {MIN_DISCOUNT_PERCENT}%+ korting")
    print(f"{'='*60}\n")

    from playwright.sync_api import sync_playwright
    from scrapers.base import random_user_agent

    all_deals = []
    new_deals = []
    shops_scanned = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        def _make_context(browser_inst):
            ctx = browser_inst.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="nl-NL",
                user_agent=random_user_agent(),
            )
            ctx.set_default_timeout(25000)           # 25s voor alle impliciete waits
            ctx.set_default_navigation_timeout(30000) # 30s voor navigatie
            return ctx

        context = _make_context(browser)

        # === STAP 1: Scrape alle shops ===

        for scraper_name in ACTIVE_SCRAPERS:
            if scraper_name not in SCRAPER_MAP:
                print(f"[!] Onbekende scraper: {scraper_name}")
                continue

            scraper = SCRAPER_MAP[scraper_name]
            print(f"\n--- {scraper_name.upper()} ---")
            
            deals = None
            error = None

            try:
                deals = scraper.scrape(context)
            except Exception as e:
                error = str(e)
            
            if error:
                print(f"[{scraper_name}] ⚠️ {error}")
                # Na ELKE fout (timeout of crash): herstel context zodat zombie-thread
                # de context van de volgende scraper niet kan corrumperen
                print(f"[{scraper_name}] 🔄 Context reset na fout...")
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    context = _make_context(browser)
                    print(f"[{scraper_name}] ✅ Nieuwe context klaar")
                except Exception as recovery_err:
                    print(f"[{scraper_name}] ❌ Context-recovery mislukt: {recovery_err} — herstart browser...")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"],
                    )
                    context = _make_context(browser)
                    print(f"[{scraper_name}] ✅ Nieuwe browser + context klaar")
                continue  # skip naar volgende scraper
            
            if deals:
                print(f"[{scraper_name}] {len(deals)} deals gevonden (voor filter)")
                filtered = filter_deals(deals, scraper_name)
                print(f"[{scraper_name}] {len(filtered)} deals na filter")
                all_deals.extend(filtered)
                shops_scanned += 1
            else:
                print(f"[{scraper_name}] 0 deals gevonden")

        # --- einde scraper-loop ---

        # === STAP 1b: Importeer iBood bookmarklet deals (indien aanwezig) ===
        ibood_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ibood_deals.json")
        if os.path.exists(ibood_json_path):
            try:
                with open(ibood_json_path, "r", encoding="utf-8") as f:
                    ibood_deals = json.load(f)
                if isinstance(ibood_deals, list) and ibood_deals:
                    print(f"\n--- iBOOD BOOKMARKLET ---")
                    print(f"[iBood] {len(ibood_deals)} deals uit ibood_deals.json")
                    filtered_ibood = filter_deals(ibood_deals, "ibood")
                    print(f"[iBood] {len(filtered_ibood)} deals na filter")
                    all_deals.extend(filtered_ibood)
                    shops_scanned += 1
                # Verwijder het bestand na import
                os.remove(ibood_json_path)
                print(f"[iBood] ibood_deals.json verwerkt en verwijderd")
            except Exception as e:
                print(f"[iBood] Fout bij importeren ibood_deals.json: {e}")

        # === STAP 2: Sla deals op ===
        for deal in all_deals:
            is_new = save_deal(
                deal["product_name"],
                deal["shop"],
                deal["current_price"],
                deal["original_price"],
                deal["discount_percent"],
                deal["url"],
                country=deal.get("country", ""),
                country_flag=deal.get("country_flag", ""),
            )
            if is_new:
                new_deals.append(deal)

        # === STAP 3: Prijsverificatie (top deals) ===
        if new_deals and MAX_PRICE_CHECKS > 0:
            print(f"\n--- PRIJSVERIFICATIE ({min(len(new_deals), MAX_PRICE_CHECKS)} deals) ---")
            try:
                from price_checker import verify_deals_batch
                # iBood deals ALTIJD eerst verifiëren (opgeblazen adviesprijs)
                ibood_deals = [d for d in new_deals if 'ibood' in d.get('shop', '').lower() or d.get('_force_verify')]
                other_deals = sorted([d for d in new_deals if d not in ibood_deals],
                                     key=lambda x: x["discount_percent"], reverse=True)
                top_deals = (ibood_deals + other_deals)[:MAX_PRICE_CHECKS]
                results = verify_deals_batch(top_deals, context, max_checks=MAX_PRICE_CHECKS)

                for deal, result in zip(top_deals, results):
                    if result["is_verified"]:
                        # Update in database
                        # We moeten het deal ID opzoeken
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("SELECT id FROM deals WHERE url = ? AND current_price = ? ORDER BY id DESC LIMIT 1",
                                  (deal["url"], deal["current_price"]))
                        row = c.fetchone()
                        conn.close()
                        if row:
                            update_deal_verification(
                                row["id"],
                                result["market_price"],
                                result["real_discount_percent"],
                                result["is_fake_discount"],
                                tweakers_price=result.get("tweakers_price"),
                                verification_source=result.get("verification_source", ""),
                            )
                            # Update ook het in-memory deal object
                            deal["market_price"] = result["market_price"]
                            deal["real_discount_percent"] = result["real_discount_percent"]
                            deal["is_fake_discount"] = result["is_fake_discount"]
                            deal["is_verified"] = True
            except Exception as e:
                print(f"[Verificatie] FOUT: {e}")

        # === STAP 3b: Marktplaats prijscheck (top deals) ===
        if new_deals:
            mp_checks = min(len(new_deals), 10)
            print(f"\n--- MARKTPLAATS CHECK ({mp_checks} deals) ---")
            try:
                from marktplaats_checker import check_marktplaats_batch
                from database import update_deal_marktplaats
                top = sorted(new_deals, key=lambda x: x["discount_percent"], reverse=True)[:mp_checks]
                mp_results = check_marktplaats_batch(top, context, max_checks=mp_checks)

                for deal, mp in zip(top, mp_results):
                    if mp:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("SELECT id FROM deals WHERE url = ? AND current_price = ? ORDER BY id DESC LIMIT 1",
                                  (deal["url"], deal["current_price"]))
                        row = c.fetchone()
                        conn.close()
                        if row:
                            profit = mp["median_price"] - deal["current_price"]
                            update_deal_marktplaats(row["id"], mp["avg_price"], mp["median_price"], mp["num_listings"], profit)
                            deal["mp_median_price"] = mp["median_price"]
                            deal["mp_profit"] = profit
                            deal["mp_listings"] = mp["num_listings"]
            except Exception as e:
                print(f"[Marktplaats] FOUT: {e}")

        # === STAP 3c: Kortingscodes zoeken ===
        try:
            from coupon_checker import find_coupons_for_deals
            print(f"\n--- KORTINGSCODES ZOEKEN ---")
            find_coupons_for_deals(all_deals, context)
        except Exception as e:
            print(f"[Coupons] FOUT: {e}")

        browser.close()

    # === STAP 4: Verzendkosten toevoegen ===
    try:
        from shipping import add_shipping_to_deals
        add_shipping_to_deals(all_deals)
    except Exception as e:
        print(f"[Shipping] FOUT: {e}")

    # === STAP 5: Notificaties ===
    real_deals = [d for d in new_deals if not d.get("is_fake_discount", False)]

    if real_deals:
        print(f"\n*** {len(real_deals)} ECHTE NIEUWE DEALS GEVONDEN! ***\n")
        for deal in sorted(real_deals, key=lambda x: x["discount_percent"], reverse=True):
            resale = deal["original_price"] * 0.75
            profit = resale - deal["current_price"]
            verified = " [GEVERIFIEERD]" if deal.get("is_verified") else ""
            market = f" (markt: €{deal['market_price']:.2f})" if deal.get("market_price") else ""
            print(f"  -{deal['discount_percent']:.0f}% | €{deal['current_price']:.2f} (was €{deal['original_price']:.2f}){market}{verified}")
            print(f"    {deal['product_name'][:70]}")
            print(f"    {deal['shop']} — {deal['url'][:80]}")
            print()
            notify_deal(deal)

    fake_deals = [d for d in new_deals if d.get("is_fake_discount", False)]
    if fake_deals:
        print(f"\n[!] {len(fake_deals)} deals met NEP-KORTING gedetecteerd (overgeslagen)")

    if not new_deals:
        print(f"\nGeen nieuwe deals gevonden.")

    # === STAP 6: Deploy naar GitHub Pages ===
    try:
        from deploy_github import deploy
        print("\n--- Deploy naar GitHub Pages ---")
        deploy()
    except Exception as e:
        print(f"[GitHub] Deploy mislukt: {e}")

    # Scan log afronden
    finish_scan_log(scan_id, shops_scanned, len(all_deals), len(new_deals))

    # Samenvatting
    print(f"\n{'='*60}")
    print(f"  Scan compleet: {shops_scanned} shops | {len(all_deals)} deals | {len(new_deals)} nieuw")
    if all_deals:
        best = max(all_deals, key=lambda x: x["discount_percent"])
        print(f"  Beste deal: -{best['discount_percent']:.0f}% op {best['product_name'][:40]} ({best['shop']})")
    print(f"{'='*60}")

    return all_deals, new_deals


def main():
    if "--loop" in sys.argv:
        print(f"PriceDrop Scanner v2 — Continue modus (elke {SCAN_INTERVAL_MINUTES} min)")
        send_windows_notification("PriceDrop v2", f"Scanner gestart — {len(ACTIVE_SCRAPERS)} shops, elke {SCAN_INTERVAL_MINUTES} min")

        while True:
            try:
                run_scan()
            except Exception as e:
                print(f"\n[FOUT] Scan mislukt: {e}")

            next_scan = datetime.now().strftime('%H:%M')
            print(f"\nVolgende scan over {SCAN_INTERVAL_MINUTES} minuten (nu: {next_scan})...")
            time.sleep(SCAN_INTERVAL_MINUTES * 60)
    else:
        run_scan()


if __name__ == "__main__":
    main()
