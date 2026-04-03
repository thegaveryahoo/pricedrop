"""
Amazon.de deals + warehouse scraper — scant op prijsfouten voor NL doorverkoop.
"""

from playwright.sync_api import sync_playwright
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


AMAZON_DE_URLS = [
    "https://www.amazon.de/deals?ref_=nav_cs_gb",
]

# Amazon.de outlet categorieen (elektronica focus)
AMAZON_DE_OUTLET_URLS = [
    "https://www.amazon.de/s?rh=n%3A7194943031%2Cn%3A562066&s=price-asc-rank",  # Elektronica outlet
]


def scrape(browser):
    """Scrape Amazon.de deals en warehouse. Geeft lijst van deal-dicts terug."""
    deals = []

    all_urls = AMAZON_DE_URLS + AMAZON_DE_OUTLET_URLS

    for url in all_urls:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({
                "Accept-Language": "nl-NL,nl;q=0.9,de;q=0.8,en;q=0.7",
            })
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)

            # Scroll
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1500)

            is_deals_page = "/deals" in url
            is_outlet = "outlet" in url or "7194943031" in url

            if is_deals_page:
                cards = page.query_selector_all('[data-deal-id], [data-testid="product-card"]')
            else:
                cards = page.query_selector_all('[data-component-type="s-search-result"]')

            print(f"[Amazon.de] {len(cards)} items gevonden op {url[:60]}...")

            for card in cards:
                try:
                    asin = card.get_attribute("data-asin") or card.get_attribute("data-deal-id")

                    # Naam
                    if is_deals_page:
                        name_el = card.query_selector("span.a-truncate-full.a-offscreen, p[class*='ProductCard-module__title']")
                    else:
                        name_el = card.query_selector("h2 span, h2")
                    name = name_el.inner_text().strip() if name_el else None

                    if not name or len(name) < 5:
                        continue

                    # URL
                    link_el = card.query_selector("a[href*='/dp/'], a[data-testid='product-card-link']")
                    product_url = link_el.get_attribute("href") if link_el else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.amazon.de{product_url}"
                    if not product_url and asin:
                        product_url = f"https://www.amazon.de/dp/{asin}"

                    if not product_url:
                        continue

                    # Prijzen
                    current_price = None
                    original_price = None

                    if is_deals_page:
                        # Deals page: gebruik accessible text
                        for span in card.query_selector_all("span.a-offscreen"):
                            text = span.inner_text().strip()
                            p = parse_dutch_price(text)
                            if p:
                                if "Angebotspreis" in text or "Dealpreis" in text or "Aanbiedingsprijs" in text:
                                    current_price = p
                                elif "UVP" in text or "Statt" in text or "Advies" in text:
                                    original_price = p
                    else:
                        # Search/outlet: standaard Amazon prijzen
                        curr_els = card.query_selector_all(".a-price:not(.a-text-price) .a-offscreen")
                        orig_els = card.query_selector_all(".a-price.a-text-price .a-offscreen")

                        for el in curr_els:
                            p = parse_dutch_price(el.inner_text())
                            if p and (current_price is None or p < current_price):
                                current_price = p
                        for el in orig_els:
                            p = parse_dutch_price(el.inner_text())
                            if p and (original_price is None or p > (current_price or 0)):
                                original_price = p

                    # Fallback: pak alle prijzen
                    if not current_price or not original_price:
                        all_prices = []
                        for span in card.query_selector_all("span[aria-hidden='true']"):
                            text = span.inner_text().strip()
                            if "€" in text:
                                p = parse_dutch_price(text)
                                if p and p > 0:
                                    all_prices.append(p)
                        if len(all_prices) >= 2:
                            all_prices.sort()
                            if not current_price:
                                current_price = all_prices[0]
                            if not original_price:
                                original_price = all_prices[-1]

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Amazon.de",
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
            print(f"[Amazon.de] Fout bij {url[:60]}: {e}")

    return deals
