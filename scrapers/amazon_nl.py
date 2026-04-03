"""
Amazon.nl deals scraper — scant de deals-pagina op prijsfouten.
"""

from playwright.sync_api import sync_playwright
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


AMAZON_NL_URLS = [
    "https://www.amazon.nl/deals?ref_=nav_cs_gb",
]


def scrape(browser):
    """Scrape Amazon.nl deals. Geeft lijst van deal-dicts terug."""
    deals = []

    for url in AMAZON_NL_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            })
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)

            # Scroll om meer deals te laden
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1500)

            # Zoek deal cards
            cards = page.query_selector_all('[data-testid="product-card"], [data-deal-id]')
            print(f"[Amazon.nl] {len(cards)} deal cards gevonden")

            for card in cards:
                try:
                    # Product naam
                    name_el = card.query_selector("span.a-truncate-full.a-offscreen")
                    if not name_el:
                        name_el = card.query_selector("img")
                        name = name_el.get_attribute("alt") if name_el else None
                    else:
                        name = name_el.inner_text().strip()

                    if not name or len(name) < 5:
                        continue

                    # Product URL
                    link_el = card.query_selector('a[data-testid="product-card-link"], a[href*="/dp/"]')
                    product_url = link_el.get_attribute("href") if link_el else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.amazon.nl{product_url}"

                    # ASIN als fallback
                    asin = card.get_attribute("data-asin")
                    if not product_url and asin:
                        product_url = f"https://www.amazon.nl/dp/{asin}"

                    if not product_url:
                        continue

                    # Prijzen via accessible text
                    price_offscreens = card.query_selector_all("span.a-offscreen")
                    current_price = None
                    original_price = None

                    for span in price_offscreens:
                        text = span.inner_text().strip()
                        if "Aanbiedingsprijs" in text or "Dealprijs" in text:
                            current_price = parse_dutch_price(text)
                        elif "Advies" in text or "Vorige" in text or "Was" in text:
                            original_price = parse_dutch_price(text)

                    # Fallback: pak alle a-price elementen
                    if not current_price:
                        price_els = card.query_selector_all("span.a-price:not(.a-text-price) span.a-offscreen")
                        for el in price_els:
                            p = parse_dutch_price(el.inner_text())
                            if p and (current_price is None or p < current_price):
                                current_price = p

                    if not original_price:
                        orig_els = card.query_selector_all("span.a-price.a-text-price span.a-offscreen")
                        for el in orig_els:
                            p = parse_dutch_price(el.inner_text())
                            if p and (original_price is None or p > (current_price or 0)):
                                original_price = p

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Amazon.nl",
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
            print(f"[Amazon.nl] Fout bij {url}: {e}")

    return deals
