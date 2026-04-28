"""
mydealz.de scraper — via RSS feed (geen Playwright, geen bot-detectie).
Focust op trending deals + nieuwe deals.

v3.0: Volledig herschreven op RSS+requests. Playwright verwijderd.
"""

import re
import requests
import xml.etree.ElementTree as ET
import html
from scrapers.base import parse_dutch_price

MYDEALZ_RSS_URLS = [
    "https://www.mydealz.de/rss/trending",
    "https://www.mydealz.de/rss/new",
]

BLOCKED_MERCHANTS = [
    'aliexpress', 'ali express', 'banggood', 'gearbest', 'geekbuying',
    'tomtop', 'cafago', 'lightinthebox', 'wish.com', 'temu', 'shein',
    'dhgate', 'miniinthebox', 'dealextreme', 'dx.com', 'goboo',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, text/xml, */*',
    'Accept-Language': 'de-DE,de;q=0.9,nl;q=0.8',
}

NS = {
    'pepper': 'http://www.pepper.com/rss',
    'media':  'http://search.yahoo.com/mrss/',
    'dc':     'http://purl.org/dc/elements/1.1/',
}


def _clean_title(title):
    """Verwijder temperatuur-prefix van mydealz titles (bv '103° - Titel')."""
    return re.sub(r'^\d+°\s*-\s*', '', title).strip()


def _extract_prices_from_desc(desc_html, current_price):
    """Zoek originele prijs in de HTML-beschrijving."""
    if not desc_html or not current_price:
        return None
    text = html.unescape(desc_html)
    found = []
    # Euro-bedragen in beide notaties: €12,99 of 12,99€
    for m in re.findall(r'€\s*([\d.,]+)|([\d.,]+)\s*€', text):
        raw = m[0] or m[1]
        p = parse_dutch_price('€' + raw)
        if p and p > 0:
            found.append(p)
    if not found:
        return None
    candidates = [p for p in found if p > current_price * 1.05 and p < current_price * 20]
    return max(candidates) if candidates else None


def _extract_discount_from_title(title):
    """Haal kortingspercentage uit titel."""
    m = re.search(r'(\d{2,3})\s*%\s*(off|korting|rabatt|aus|sparen|goedkoper)', title, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def scrape(browser=None):
    """Scrape mydealz.de via RSS. browser-argument genegeerd (compatibiliteit)."""
    deals = []
    seen_urls = set()

    for rss_url in MYDEALZ_RSS_URLS:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            r.raise_for_status()

            root = ET.fromstring(r.text)
            channel = root.find('channel')
            if channel is None:
                continue

            items = channel.findall('item')
            print(f"[mydealz] {len(items)} items in {rss_url.split('/')[-1]}")

            for item in items:
                try:
                    raw_title = (item.findtext('title') or '').strip()
                    title = _clean_title(raw_title)
                    if not title or len(title) < 5:
                        continue

                    link = (item.findtext('guid') or item.findtext('link') or '').strip()
                    if not link:
                        continue
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)

                    # Winkel + prijs uit pepper:merchant
                    merchant_el = item.find('pepper:merchant', NS)
                    shop_name = 'mydealz'
                    current_price = None
                    if merchant_el is not None:
                        shop_name = merchant_el.get('name', 'mydealz')[:30]
                        price_str = merchant_el.get('price', '')
                        current_price = parse_dutch_price(price_str)

                    # China-filter
                    if any(b in f"{shop_name} {title}".lower() for b in BLOCKED_MERCHANTS):
                        continue

                    # Originele prijs uit beschrijving
                    desc_html = item.findtext('description') or ''
                    original_price = _extract_prices_from_desc(desc_html, current_price)

                    # Korting berekenen
                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                    else:
                        pct = _extract_discount_from_title(title)
                        if pct and pct >= 30 and current_price:
                            discount = pct
                            original_price = round(current_price / (1 - pct / 100), 2)
                        else:
                            continue

                    if discount < 30:
                        continue

                    deals.append({
                        "product_name": title[:200],
                        "shop": f"mydealz ({shop_name})",
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": round(discount, 1),
                        "url": link,
                        "_country": "DE",
                    })

                except Exception:
                    continue

        except Exception as e:
            print(f"[mydealz] Fout bij {rss_url}: {e}")

    print(f"[mydealz] Totaal: {len(deals)} bruikbare deals")
    return deals
