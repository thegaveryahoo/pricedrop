"""
Alternate.nl scraper — grote NL elektronica webshop.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay

URLS = [
    "https://www.alternate.nl/Outlet",
    "https://www.alternate.nl/aanbiedingen",
]


def scrape(browser):
    deals = []
    for url in URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            # Alternate product cards
            cards = page.query_selector_all('[class*="productBox"], [class*="product-card"], .listing-product')
            if not cards:
                cards = page.query_selector_all('a[href*="/product/"], a[href*="/html/"]')

            print(f"[Alternate] {len(cards)} items op {url.split('/')[-1]}")

            for card in cards:
                try:
                    # Naam
                    name_el = card.query_selector('[class*="name"], [class*="title"], h2, h3, span[class*="product"]')
                    name = name_el.inner_text().strip() if name_el else None
                    if not name or len(name) < 5:
                        name_text = card.inner_text().strip()[:100]
                        if len(name_text) > 5:
                            name = name_text
                        else:
                            continue

                    # URL
                    link = card if card.evaluate("el => el.tagName") == "A" else card.query_selector("a")
                    product_url = link.get_attribute("href") if link else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.alternate.nl{product_url}"
                    if not product_url:
                        continue

                    # Prijzen
                    all_text = card.inner_text()
                    prices = []
                    for match in re.findall(r'€\s*[\d.,]+', all_text):
                        p = parse_dutch_price(match)
                        if p and p > 0:
                            prices.append(p)

                    strike_el = card.query_selector('s, [class*="strike"], [class*="old"], [class*="was"]')
                    original_price = parse_dutch_price(strike_el.inner_text()) if strike_el else None

                    if not original_price and len(prices) >= 2:
                        prices.sort()
                        original_price = prices[-1]
                        current_price = prices[0]
                    elif prices:
                        current_price = min(prices)
                    else:
                        continue

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Alternate",
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
            print(f"[Alternate] Fout bij {url}: {e}")

    return deals
