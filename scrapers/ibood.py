"""
iBood.com scraper — duizenden deals, maar met notoir opgeblazen adviesprijs.
Scrapt de volledige aanbiedingen-pagina + deal van de dag.
Alle iBood deals worden VERPLICHT geverifieerd.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay


IBOOD_URLS = [
    "https://www.ibood.com/nl/s-nl/all-offers",  # Alle aanbiedingen
    "https://www.ibood.com/nl/nl/",               # Deal van de dag
]


def scrape(browser):
    deals = []

    for url in IBOOD_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(4000)

            # Scroll flink om meer deals te laden
            for _ in range(8):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1500)

            # iBood product cards — probeer meerdere selectors
            cards = page.query_selector_all('[class*="product-card"], [class*="ProductCard"], [class*="offer-card"]')
            if not cards:
                cards = page.query_selector_all('a[href*="/nl/s-nl/"][href*="-"]')
            if not cards:
                # Brede fallback: alle links met prijzen in de buurt
                cards = page.query_selector_all('article, [class*="card"], [class*="item"]')

            print(f"[iBood] {len(cards)} items op {url.split('/')[-1]}")

            for card in cards:
                try:
                    deal = _parse_ibood_card(card)
                    if deal:
                        deal["_force_verify"] = True
                        deals.append(deal)
                except Exception:
                    continue

            # Als geen cards gevonden: probeer de hele pagina te parsen
            if not cards or len(deals) == 0:
                page_deals = _parse_ibood_page(page, url)
                for d in page_deals:
                    d["_force_verify"] = True
                deals.extend(page_deals)

            page.close()
            respectful_delay()

        except Exception as e:
            print(f"[iBood] Fout bij {url}: {e}")

    # Dedup op URL
    seen = set()
    unique = []
    for d in deals:
        if d["url"] not in seen:
            seen.add(d["url"])
            unique.append(d)

    return unique


def _parse_ibood_card(card):
    """Parse een iBood product card."""
    # Naam
    name_el = card.query_selector('[class*="title"], [class*="name"], h2, h3, h4, strong')
    if not name_el:
        name_el = card.query_selector('span, p')
    name = name_el.inner_text().strip() if name_el else None
    if not name or len(name) < 5:
        return None

    # URL
    link = card if card.evaluate("el => el.tagName") == "A" else card.query_selector("a")
    product_url = link.get_attribute("href") if link else None
    if product_url and not product_url.startswith("http"):
        product_url = f"https://www.ibood.com{product_url}"
    if not product_url:
        return None

    # Prijzen
    all_text = card.inner_text()
    prices = []
    for match in re.findall(r'€\s*[\d.,]+', all_text):
        p = parse_dutch_price(match)
        if p and 0.5 < p < 50000:
            prices.append(p)

    # Doorgestreepte prijs (adviesprijs — NIET VERTROUWEN)
    strike_el = card.query_selector('s, del, [class*="old"], [class*="retail"], [class*="list"], [class*="from"], [class*="advice"]')
    original_price = parse_dutch_price(strike_el.inner_text()) if strike_el else None

    current_price = None
    if original_price and prices:
        # Laagste prijs die niet de originele is
        lower = [p for p in prices if p < original_price]
        current_price = min(lower) if lower else min(prices)
    elif len(prices) >= 2:
        prices.sort()
        current_price = prices[0]
        original_price = prices[-1]
    elif prices:
        current_price = prices[0]
        return None  # Geen vergelijkingsprijs

    if current_price and original_price and original_price > current_price and current_price > 0:
        discount = ((original_price - current_price) / original_price) * 100
        return {
            "product_name": name[:200],
            "shop": "iBood",
            "current_price": current_price,
            "original_price": original_price,
            "discount_percent": round(discount, 1),
            "url": product_url,
        }
    return None


def _parse_ibood_page(page, url):
    """Fallback: parse de hele pagina op prijsparen."""
    deals = []
    try:
        # Haal alle tekst en zoek prijsparen
        all_links = page.query_selector_all('a[href]')

        for link in all_links:
            try:
                href = link.get_attribute("href")
                if not href or "/nl/" not in href:
                    continue

                text = link.inner_text().strip()
                if len(text) < 10:
                    continue

                prices = []
                for match in re.findall(r'€\s*[\d.,]+', text):
                    p = parse_dutch_price(match)
                    if p and 0.5 < p < 50000:
                        prices.append(p)

                if len(prices) >= 2:
                    prices.sort()
                    current = prices[0]
                    original = prices[-1]
                    if original > current and current > 0:
                        discount = ((original - current) / original) * 100
                        if discount >= 30:
                            product_url = href if href.startswith("http") else f"https://www.ibood.com{href}"
                            # Extract naam (eerste regel van de tekst)
                            name = text.split('\n')[0].strip()[:200]
                            # Verwijder prijzen uit de naam
                            name = re.sub(r'€\s*[\d.,]+', '', name).strip()
                            if len(name) > 5:
                                deals.append({
                                    "product_name": name,
                                    "shop": "iBood",
                                    "current_price": current,
                                    "original_price": original,
                                    "discount_percent": round(discount, 1),
                                    "url": product_url,
                                })
            except Exception:
                continue

    except Exception:
        pass

    return deals
