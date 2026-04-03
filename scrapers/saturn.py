"""
Saturn.de scraper — Duitse elektronica (zelfde moederbedrijf als MediaMarkt).
Zelfde HTML-structuur als MediaMarkt.de.
"""

from scrapers.base import parse_dutch_price, respectful_delay

URLS = [
    "https://www.saturn.de/de/list/top-deals",
    "https://www.saturn.de/de/list/tv-angebote",
    "https://www.saturn.de/de/list/laptop-angebote",
    "https://www.saturn.de/de/list/smartphone-angebote",
    "https://www.saturn.de/de/list/audio-angebote",
]


def scrape(browser):
    deals = []
    for url in URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "de-DE,de;q=0.9,nl;q=0.8"})
            page.goto(url, timeout=30000)

            try:
                page.wait_for_selector('[data-test="mms-product-card"]', timeout=10000)
            except Exception:
                print(f"[Saturn] Geen producten op {url.split('/')[-1]}")
                page.close()
                continue

            page.wait_for_timeout(2000)

            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            cards = page.query_selector_all('[data-test="mms-product-card"]')
            print(f"[Saturn] {len(cards)} producten op {url.split('/')[-1]}")

            for card in cards:
                try:
                    name_el = card.query_selector('[data-test="product-title"]')
                    name = name_el.inner_text().strip() if name_el else None
                    if not name:
                        continue

                    link_el = card.query_selector('a[href*="/product/"]')
                    product_url = link_el.get_attribute("href") if link_el else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.saturn.de{product_url}"
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
                        for span in price_div.query_selector_all('span[aria-hidden="true"]'):
                            text = span.inner_text().strip()
                            if text.startswith("€"):
                                p = parse_dutch_price(text)
                                if p and p > 0:
                                    if original_price and p < original_price:
                                        current_price = p
                                    elif not original_price and (current_price is None or p < current_price):
                                        current_price = p

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Saturn.de",
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
            print(f"[Saturn] Fout bij {url}: {e}")

    return deals
