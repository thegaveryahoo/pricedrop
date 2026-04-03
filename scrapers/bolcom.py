"""
Bol.com deals scraper — scant aanbiedingen-pagina's op extreme kortingen.
"""

from playwright.sync_api import sync_playwright
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


# Bol.com categorieen met deals
BOLCOM_URLS = [
    "https://www.bol.com/nl/nl/l/elektronica-deals/N/17575/",
    "https://www.bol.com/nl/nl/l/computer-deals/N/17577/",
    "https://www.bol.com/nl/nl/l/telefoon-deals/N/40027/",
    "https://www.bol.com/nl/nl/l/tv-deals/N/40028/",
    "https://www.bol.com/nl/nl/l/gaming-deals/N/40026/",
]


def scrape(browser):
    """Scrape Bol.com deals pagina's. Geeft lijst van deal-dicts terug."""
    deals = []

    for url in BOLCOM_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            # Zoek product-links met prijzen
            products = page.query_selector_all('a[href*="/p/"]')
            seen_urls = set()

            for product_el in products:
                try:
                    href = product_el.get_attribute("href")
                    if not href or "/p/" not in href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    product_url = href if href.startswith("http") else f"https://www.bol.com{href}"

                    # Zoek naam
                    name_el = product_el.query_selector("h2, h3, span")
                    name = name_el.inner_text().strip() if name_el else None
                    if not name or len(name) < 5:
                        continue

                    # Navigeer omhoog naar de product card container
                    card = product_el.evaluate_handle("""
                        el => {
                            let parent = el.closest('[class*="product"]') || el.parentElement?.parentElement?.parentElement;
                            return parent;
                        }
                    """)

                    if not card:
                        continue

                    # Zoek prijzen in de card
                    card_html = card.evaluate("el => el.innerText")

                    # Zoek doorstreepte prijs (origineel)
                    strike_el = card.query_selector("s")
                    original_text = strike_el.inner_text() if strike_el else None
                    original_price = parse_dutch_price(original_text)

                    # Zoek huidige prijs - kijk naar tekst met "prijs" of euro-teken
                    price_spans = card.query_selector_all("span")
                    current_price = None
                    for span in price_spans:
                        text = span.inner_text().strip()
                        if "€" in text or text.replace(",", "").replace(".", "").replace("-", "").isdigit():
                            p = parse_dutch_price(text)
                            if p and p > 0 and (current_price is None or p < current_price):
                                if original_price is None or p < original_price:
                                    current_price = p

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": "Bol.com",
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
            print(f"[Bol.com] Fout bij {url}: {e}")
            continue

    return deals
