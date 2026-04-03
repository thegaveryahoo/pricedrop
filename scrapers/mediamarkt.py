"""
MediaMarkt.nl deals scraper — scant aanbiedingen op extreme kortingen.
"""

from playwright.sync_api import sync_playwright
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


MEDIAMARKT_URLS = [
    "https://www.mediamarkt.nl/nl/list/televisie-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/laptop-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/smartphone-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/audio-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/gaming-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/tablet-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/monitor-aanbiedingen",
    "https://www.mediamarkt.nl/nl/list/smartwatch-aanbiedingen",
]


def scrape(browser):
    """Scrape MediaMarkt.nl aanbiedingen. Geeft lijst van deal-dicts terug."""
    deals = []

    for url in MEDIAMARKT_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)

            # Wacht op product cards (React SPA)
            try:
                page.wait_for_selector('[data-test="mms-product-card"]', timeout=10000)
            except Exception:
                print(f"[MediaMarkt] Geen producten gevonden op {url}")
                page.close()
                continue

            page.wait_for_timeout(2000)

            # Scroll om meer te laden
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            cards = page.query_selector_all('[data-test="mms-product-card"]')
            print(f"[MediaMarkt] {len(cards)} producten op {url.split('/')[-1]}")

            for card in cards:
                try:
                    # Product naam
                    name_el = card.query_selector('[data-test="product-title"]')
                    name = name_el.inner_text().strip() if name_el else None
                    if not name:
                        continue

                    # Product URL
                    link_el = card.query_selector('a[data-test="mms-router-link-product-list-item-link"], a[href*="/product/"]')
                    product_url = link_el.get_attribute("href") if link_el else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.mediamarkt.nl{product_url}"

                    if not product_url:
                        continue

                    # Originele prijs (doorstreept)
                    strike_el = card.query_selector('[data-test="mms-strike-price-type-map"] span[aria-hidden="true"]')
                    original_price = None
                    if strike_el:
                        text = strike_el.inner_text().strip()
                        if "€" in text:
                            original_price = parse_dutch_price(text)

                    # Huidige prijs
                    price_div = card.query_selector('[data-test="mms-price"]')
                    current_price = None
                    if price_div:
                        # Haal alle spans met aria-hidden=true die met € beginnen
                        price_spans = price_div.query_selector_all('span[aria-hidden="true"]')
                        for span in price_spans:
                            text = span.inner_text().strip()
                            if text.startswith("€"):
                                p = parse_dutch_price(text)
                                if p and p > 0:
                                    # Als we al een originele prijs hebben, kies de lagere als huidige
                                    if original_price and p < original_price:
                                        current_price = p
                                    elif not original_price and (current_price is None or p < current_price):
                                        current_price = p

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "MediaMarkt",
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
            print(f"[MediaMarkt] Fout bij {url}: {e}")

    return deals
