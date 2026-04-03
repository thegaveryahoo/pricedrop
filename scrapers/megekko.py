"""
Megekko.nl scraper — populaire NL PC/gaming shop.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay

URLS = [
    "https://www.megekko.nl/aanbiedingen",
    "https://www.megekko.nl/Computer/Componenten?sort=discount",
    "https://www.megekko.nl/Computer/Laptops?sort=discount",
]


def scrape(browser):
    deals = []
    for url in URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            for _ in range(2):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            cards = page.query_selector_all('[class*="product"], [class*="item"]')
            print(f"[Megekko] {len(cards)} items op {url.split('/')[-1]}")

            for card in cards:
                try:
                    name_el = card.query_selector('a[class*="name"], [class*="title"], h2, h3')
                    name = name_el.inner_text().strip() if name_el else None
                    if not name or len(name) < 5:
                        continue

                    link = card.query_selector('a[href*="/product/"], a[href*="megekko.nl"]')
                    if not link:
                        link = card.query_selector("a")
                    product_url = link.get_attribute("href") if link else None
                    if product_url and not product_url.startswith("http"):
                        product_url = f"https://www.megekko.nl{product_url}"
                    if not product_url:
                        continue

                    all_text = card.inner_text()
                    prices = []
                    for match in re.findall(r'€\s*[\d.,]+', all_text):
                        p = parse_dutch_price(match)
                        if p and p > 0:
                            prices.append(p)

                    strike_el = card.query_selector('s, [class*="old"], [class*="strike"], [class*="was"]')
                    original_price = parse_dutch_price(strike_el.inner_text()) if strike_el else None

                    current_price = None
                    if not original_price and len(prices) >= 2:
                        prices.sort()
                        original_price = prices[-1]
                        current_price = prices[0]
                    elif prices:
                        current_price = min(prices)

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Megekko",
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
            print(f"[Megekko] Fout bij {url}: {e}")

    return deals
