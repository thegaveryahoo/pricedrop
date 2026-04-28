"""
Pepper.com NL scraper — via RSS feed (geen Playwright, geen bot-detectie).
RSS heeft huidige prijs + beschrijving met vergelijkingsprijzen.

v3.0: Volledig herschreven op RSS+requests. Playwright verwijderd.
"""

import re
import requests
import xml.etree.ElementTree as ET
import html
from scrapers.base import parse_dutch_price

PEPPER_RSS_URLS = [
    "https://nl.pepper.com/rss/nieuw",
    "https://nl.pepper.com/rss/heetste",
]

BLOCKED_MERCHANTS = [
    'aliexpress', 'ali express', 'banggood', 'gearbest', 'geekbuying',
    'tomtop', 'cafago', 'lightinthebox', 'wish.com', 'temu', 'shein',
    'dhgate', 'miniinthebox', 'dealextreme', 'dx.com', 'goboo',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, text/xml, */*',
    'Accept-Language': 'nl-NL,nl;q=0.9',
}

NS = {
    'pepper': 'http://www.pepper.com/rss',
    'media':  'http://search.yahoo.com/mrss/',
    'dc':     'http://purl.org/dc/elements/1.1/',
    'content':'http://purl.org/rss/1.0/modules/content/',
}


def _extract_prices_from_desc(desc_html, current_price):
    """Zoek originele prijs in de HTML-beschrijving van de deal."""
    if not desc_html:
        return None
    text = html.unescape(desc_html)
    # Alle prijspatronen vinden
    found = []
    for m in re.findall(r'€\s*([\d.,]+)', text):
        p = parse_dutch_price('€' + m)
        if p and p > 0:
            found.append(p)
    if not found or not current_price:
        return None
    # Originele prijs = hoogste prijs in beschrijving die groter is dan current
    candidates = [p for p in found if p > current_price * 1.05 and p < current_price * 20]
    return max(candidates) if candidates else None


def _extract_discount_from_title(title):
    """Haal kortingspercentage uit de titel als het er expliciet in staat."""
    m = re.search(r'(\d{2,3})\s*%\s*(korting|off|rabatt|aus|goedkoper)', title, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def scrape(browser=None):
    """Scrape nl.pepper.com via RSS. browser-argument genegeerd (compatibiliteit)."""
    deals = []
    seen_urls = set()

    for rss_url in PEPPER_RSS_URLS:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            r.raise_for_status()

            # Strip namespace prefixes zodat ET ze herkent
            xml_text = r.text
            root = ET.fromstring(xml_text)
            channel = root.find('channel')
            if channel is None:
                continue

            items = channel.findall('item')
            print(f"[Pepper] {len(items)} items in {rss_url.split('/')[-1]}")

            for item in items:
                try:
                    title = (item.findtext('title') or '').strip()
                    if not title or len(title) < 5:
                        continue

                    link = (item.findtext('link') or item.findtext('guid') or '').strip()
                    # <link> is soms tekst-node na tag in ET — fallback via guid
                    if not link:
                        guid_el = item.find('guid')
                        link = guid_el.text.strip() if guid_el is not None else ''

                    if link in seen_urls:
                        continue
                    seen_urls.add(link)

                    # Winkel + prijs uit pepper:merchant
                    merchant_el = item.find('pepper:merchant', NS)
                    shop_name = 'Pepper deal'
                    current_price = None
                    if merchant_el is not None:
                        shop_name = merchant_el.get('name', 'Pepper deal')[:30]
                        price_str = merchant_el.get('price', '')
                        current_price = parse_dutch_price(price_str)

                    # China-filter
                    if any(b in f"{shop_name} {title}".lower() for b in BLOCKED_MERCHANTS):
                        continue

                    # Probeer originele prijs te vinden in beschrijving
                    desc_html = item.findtext('description') or ''
                    original_price = _extract_prices_from_desc(desc_html, current_price)

                    # Bereken korting
                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                    else:
                        # Laatste kans: korting uit titel
                        pct = _extract_discount_from_title(title)
                        if pct and pct >= 30 and current_price:
                            discount = pct
                            # Bereken original_price terug
                            original_price = round(current_price / (1 - pct / 100), 2)
                        else:
                            continue  # Geen bruikbare kortingsinfo

                    if discount < 30:
                        continue

                    deals.append({
                        "product_name": title[:200],
                        "shop": f"Pepper ({shop_name})",
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": round(discount, 1),
                        "url": link,
                    })

                except Exception:
                    continue

        except Exception as e:
            print(f"[Pepper] Fout bij {rss_url}: {e}")

    print(f"[Pepper] Totaal: {len(deals)} bruikbare deals")
    return deals
