"""
Coolblue scraper — gebruikt JSON-LD structured data (meest betrouwbaar).
Scant aanbiedingen en tweedekans pagina's.
"""

import json
from playwright.sync_api import sync_playwright
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


COOLBLUE_URLS = [
    "https://www.coolblue.nl/aanbiedingen",
    "https://www.coolblue.nl/aanbiedingen/laptops",
    "https://www.coolblue.nl/aanbiedingen/smartphones",
    "https://www.coolblue.nl/aanbiedingen/televisies",
    "https://www.coolblue.nl/aanbiedingen/tablets",
    "https://www.coolblue.nl/aanbiedingen/koptelefoons",
    "https://www.coolblue.nl/aanbiedingen/smartwatches",
    "https://www.coolblue.nl/aanbiedingen/gaming",
    "https://www.coolblue.nl/aanbiedingen/stofzuigers",
]


def scrape(browser):
    """Scrape Coolblue aanbiedingen. Geeft lijst van deal-dicts terug."""
    deals = []

    for url in COOLBLUE_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            # Methode 1: JSON-LD (meest betrouwbaar)
            json_ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.inner_text())
                    if isinstance(data, dict) and data.get("@type") == "ItemList":
                        for item in data.get("itemListElement", []):
                            name = item.get("name", "")
                            product_url = item.get("url", "")
                            offers = item.get("offers", {})
                            current_price = float(offers.get("price", 0))

                            if name and current_price > 0:
                                # JSON-LD heeft geen originele prijs, die halen we uit HTML
                                deals.append({
                                    "product_name": name[:200],
                                    "shop": "Coolblue",
                                    "current_price": current_price,
                                    "original_price": None,  # wordt later ingevuld
                                    "discount_percent": 0,
                                    "url": product_url,
                                    "_needs_original": True,
                                })
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

            # Methode 2: HTML parsing voor originele prijzen
            cards = page.query_selector_all("div.product-card, [class*='product-card']")
            for card in cards:
                try:
                    # Zoek adviesprijs
                    all_text = card.inner_text()
                    if "Adviesprijs" not in all_text and "Van " not in all_text:
                        continue

                    # Haal link en naam
                    link = card.query_selector('a[href*="/product/"]')
                    if not link:
                        continue
                    product_url = link.get_attribute("href")
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.coolblue.nl{product_url}"

                    name = link.inner_text().strip()
                    if not name or len(name) < 3:
                        continue

                    # Zoek alle prijzen in de card
                    spans = card.query_selector_all("span")
                    prices = []
                    for span in spans:
                        text = span.inner_text().strip()
                        p = parse_dutch_price(text)
                        if p and p > 0:
                            prices.append(p)

                    if len(prices) >= 2:
                        prices.sort()
                        current_price = prices[0]
                        original_price = prices[-1]

                        if original_price > current_price:
                            discount = ((original_price - current_price) / original_price) * 100

                            # Update bestaande deal of voeg nieuwe toe
                            updated = False
                            for d in deals:
                                if d["url"] == product_url and d.get("_needs_original"):
                                    d["original_price"] = original_price
                                    d["discount_percent"] = round(discount, 1)
                                    d.pop("_needs_original", None)
                                    updated = True
                                    break

                            if not updated:
                                deals.append({
                                    "product_name": name[:200],
                                    "shop": "Coolblue",
                                    "current_price": current_price,
                                    "original_price": original_price,
                                    "discount_percent": round(discount, 1),
                                    "url": product_url,
                                })

                except Exception:
                    continue

            page.close()
            respectful_delay()

        except Exception as e:
            print(f"[Coolblue] Fout bij {url}: {e}")
            continue

    # Verwijder deals zonder originele prijs
    deals = [d for d in deals if d.get("original_price") and d["discount_percent"] > 0]
    return deals
