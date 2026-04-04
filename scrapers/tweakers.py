"""
Tweakers Pricewatch scraper — scrapt prijsdalingen en aanbiedingen.
Tweakers is de meest betrouwbare NL prijsvergelijker met historische data.

Twee functies:
1. scrape() — haal deals/prijsdalingen op van Tweakers Pricewatch
2. search_tweakers_price() — zoek marktprijs voor een specifiek product (voor verificatie)
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay


# Tweakers Pricewatch pagina's met prijsdalingen
TWEAKERS_URLS = [
    "https://tweakers.net/pricewatch/deals/",       # Prijsdalingen
    "https://tweakers.net/pricewatch/deals/?page=2", # Pagina 2
]


def _extract_deals_from_page(page):
    """Haal deals uit een Tweakers Pricewatch deals pagina."""
    deals = []
    seen_urls = set()

    # Tweakers deals pagina: table.listing met tr rijen
    rows = page.query_selector_all('table.listing tr')

    for row in rows:
        try:
            # Productnaam via td.itemname a.editionName
            name_el = row.query_selector('td.itemname a.editionName')
            if not name_el:
                continue
            name = name_el.inner_text().strip()
            if not name or len(name) < 5:
                continue

            # URL
            url = name_el.get_attribute("href")
            if not url:
                continue
            if not url.startswith("http"):
                url = f"https://tweakers.net{url}"

            # Deduplicatie
            base_url = url.split("?")[0].split("#")[0]
            if base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            # Huidige prijs via td.price-score p.price
            current_price = None
            price_el = row.query_selector('td.price-score p.price')
            if price_el:
                current_price = parse_dutch_price(price_el.inner_text())

            # Originele prijs via td.price-score p.beforePrice
            original_price = None
            before_el = row.query_selector('td.price-score p.beforePrice')
            if before_el:
                original_price = parse_dutch_price(before_el.inner_text())

            # Korting% via td.discountRow a.discount
            page_discount = None
            discount_el = row.query_selector('td.discountRow a.discount')
            if discount_el:
                discount_text = discount_el.inner_text().strip().replace('%', '')
                try:
                    page_discount = abs(float(discount_text))
                except ValueError:
                    pass

            if not current_price:
                continue

            # Bereken korting
            if original_price and original_price > current_price:
                discount = ((original_price - current_price) / original_price) * 100
            elif page_discount:
                discount = page_discount
                # Bereken originele prijs uit discount
                if discount > 0:
                    original_price = round(current_price / (1 - discount / 100), 2)
            else:
                continue

            # Sanity check
            if original_price and current_price >= original_price:
                continue
            if original_price and original_price / current_price > 50:
                continue

            deals.append({
                "product_name": name[:200],
                "shop": "Tweakers Pricewatch",
                "current_price": round(current_price, 2),
                "original_price": round(original_price, 2) if original_price else round(current_price * 1.5, 2),
                "discount_percent": round(discount, 1),
                "url": url,
                "_country": "NL",
            })

        except Exception:
            continue

    return deals


def scrape(browser):
    """Scrape Tweakers Pricewatch deals. Geeft lijst van deal-dicts terug."""
    deals = []
    seen_urls = set()

    for url in TWEAKERS_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            # Accepteer cookies
            try:
                cookie_btn = page.query_selector(
                    'button[id*="accept"], button:has-text("Akkoord"), '
                    'button:has-text("Accepteren"), [data-testid*="accept"]'
                )
                if cookie_btn:
                    cookie_btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            found = _extract_deals_from_page(page)

            for d in found:
                base = d["url"].split("?")[0].split("#")[0]
                if base not in seen_urls:
                    seen_urls.add(base)
                    deals.append(d)

            label = url.split('/')[-1] or url.split('/')[-2]
            if '?' in label:
                label = label.split('?')[0] or 'deals'
            print(f"[Tweakers] {len(found)} deals op {label}")
            page.close()
            respectful_delay()

        except Exception as e:
            print(f"[Tweakers] Fout bij {url}: {e}")

    return deals


def search_tweakers_price(product_name, browser_context, deal_price=None, original_price=None):
    """
    Zoek een product op Tweakers Pricewatch en haal de laagste marktprijs op.
    Wordt gebruikt voor prijsverificatie in price_checker.py.

    Returns: float (laagste prijs) of None
    """
    page = None
    try:
        # Maak zoekterm schoon
        clean_name = re.sub(r'[^\w\s\-\.]', ' ', product_name)
        noise = ['aanbieding', 'deal', 'korting', 'sale', 'gratis', 'free', 'nieuw', 'new', 'hot']
        words = [w for w in clean_name.split() if w.lower() not in noise]
        clean_name = ' '.join(words[:6])  # Max 6 woorden

        page = browser_context.new_page()
        page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})

        # Tweakers zoekpagina
        search_url = f"https://tweakers.net/zoeken/?keyword={clean_name.replace(' ', '+')}&cat=pricewatch"
        page.goto(search_url, timeout=15000)
        page.wait_for_timeout(2500)

        # Accepteer cookies indien nodig
        try:
            cookie_btn = page.query_selector(
                'button[id*="accept"], button:has-text("Akkoord"), '
                'button:has-text("Accepteren"), [data-testid*="accept"]'
            )
            if cookie_btn:
                cookie_btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        prices = []

        # Methode 1: Pricewatch product kaarten bovenaan zoekresultaten
        # .tweakbaseGrid li → div.price a (laatste a = prijs)
        price_cards = page.query_selector_all('.tweakbaseGrid li')
        for card in price_cards:
            price_links = card.query_selector_all('div.price a')
            if price_links:
                # Laatste link in div.price bevat de prijs ("vanaf €X")
                price_text = price_links[-1].inner_text()
                p = parse_dutch_price(price_text)
                if p and 1 < p < 50000:
                    prices.append(p)

        # Methode 2: Klik op eerste Pricewatch resultaat voor shop-prijzen
        if not prices:
            first_card = page.query_selector('.tweakbaseGrid a.thumb[href*="vergelijken"]')
            if not first_card:
                first_card = page.query_selector('.tweakbaseGrid p.title a')
            if first_card:
                href = first_card.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = f"https://tweakers.net{href}"
                    page.goto(href, timeout=15000)
                    page.wait_for_timeout(2000)

                    # Op productpagina: zoek prijzen
                    for sel in ['.shop-offer__price', 'p.price', '[class*="price"]']:
                        elements = page.query_selector_all(sel)
                        for el in elements:
                            p = parse_dutch_price(el.inner_text())
                            if p and 1 < p < 50000:
                                prices.append(p)
                        if prices:
                            break

                    # Fallback: regex € bedragen
                    if not prices:
                        try:
                            text = page.inner_text("body")
                            for m in re.findall(r'€\s*([\d.,]+)', text):
                                p = parse_dutch_price(f"€{m}")
                                if p and 2 < p < 50000:
                                    prices.append(p)
                        except Exception:
                            pass

        page.close()
        page = None

        if not prices:
            return None

        # Filter uitschieters
        prices = sorted(set(prices))
        if deal_price and original_price:
            ref_price = (deal_price + original_price) / 2
            filtered = [p for p in prices if ref_price * 0.1 < p < ref_price * 5]
            if filtered:
                prices = filtered

        # Return mediaan (meest betrouwbaar)
        if len(prices) == 1:
            return prices[0]
        return prices[len(prices) // 2]

    except Exception:
        if page:
            try:
                page.close()
            except Exception:
                pass
        return None
