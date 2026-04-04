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
    "https://tweakers.net/aanbiedingen/",                    # Huidige aanbiedingen
    "https://tweakers.net/pricewatch/besteselectie/",        # Beste selectie deals
]


def _extract_deals_from_page(page):
    """Haal deals uit een Tweakers aanbiedingen/pricewatch pagina."""
    deals = []
    seen_urls = set()

    # Tweakers deal listings — probeer meerdere selectors
    selectors = [
        # Aanbiedingen pagina
        'tr.largethumb, tr.listing',
        # Pricewatch listing items
        '[class*="listing--"] a[href*="/pricewatch/"]',
        '.listingContainer tr',
        # Generieke product links
        'article, .product-card, [class*="productCard"]',
    ]

    articles = []
    for sel in selectors:
        articles = page.query_selector_all(sel)
        if articles:
            break

    # Fallback: zoek alle links met pricewatch
    if not articles:
        articles = page.query_selector_all('a[href*="/pricewatch/"]')

    for article in articles:
        try:
            # Productnaam
            name = None
            name_el = article.query_selector('a[href*="/pricewatch/"], h3, .title, p.title')
            if name_el:
                name = name_el.inner_text().strip()
            if not name:
                # Probeer de hele tekst als het een link is
                tag = article.evaluate("el => el.tagName")
                if tag == 'A':
                    name = article.inner_text().strip()
            if not name or len(name) < 5:
                continue

            # URL
            url = None
            link_el = article.query_selector('a[href*="/pricewatch/"], a[href*="tweakers.net"]')
            if link_el:
                url = link_el.get_attribute("href")
            elif article.evaluate("el => el.tagName") == 'A':
                url = article.get_attribute("href")
            if not url:
                continue
            if not url.startswith("http"):
                url = f"https://tweakers.net{url}"

            # Deduplicatie
            base_url = url.split("?")[0].split("#")[0]
            if base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            # Prijzen extraheren
            current_price = None
            original_price = None

            # Zoek doorgestreepte (oude) prijs
            strike_el = article.query_selector('s, del, [class*="oldPrice"], [class*="was-price"], [style*="line-through"]')
            if strike_el:
                original_price = parse_dutch_price(strike_el.inner_text())

            # Zoek huidige prijs
            price_selectors = [
                '[class*="price"]:not(s):not(del)',
                '.price, .currentPrice',
                'td:last-child',
            ]
            for psel in price_selectors:
                pel = article.query_selector(psel)
                if pel:
                    p = parse_dutch_price(pel.inner_text())
                    if p and p > 0:
                        current_price = p
                        break

            # Fallback: regex alle prijzen in het element
            if not current_price:
                text = article.inner_text()
                prices = []
                for m in re.findall(r'€\s*([\d.,]+)', text):
                    p = parse_dutch_price(f"€{m}")
                    if p and p > 0:
                        prices.append(p)
                if prices:
                    current_price = min(prices)
                    if len(prices) >= 2:
                        original_price = max(prices)

            if not current_price:
                continue

            # Bereken korting
            if original_price and original_price > current_price:
                discount = ((original_price - current_price) / original_price) * 100
            else:
                continue  # Zonder originele prijs kunnen we geen korting berekenen

            # Sanity check
            if current_price >= original_price:
                continue
            ratio = original_price / current_price
            if ratio > 50:
                continue

            deals.append({
                "product_name": name[:200],
                "shop": "Tweakers Pricewatch",
                "current_price": round(current_price, 2),
                "original_price": round(original_price, 2),
                "discount_percent": round(discount, 1),
                "url": url,
                "_country": "NL",
            })

        except Exception:
            continue

    return deals


def _scrape_pricewatch_drops(page):
    """
    Scrape Tweakers Pricewatch prijsdalingen — alternatieve methode.
    Kijkt naar de body tekst en zoekt producten met prijsdalingen.
    """
    deals = []
    seen_urls = set()

    try:
        # Zoek alle product-rijen met prijsinformatie
        rows = page.query_selector_all('tr, .listing, [class*="product"]')

        for row in rows:
            try:
                text = row.inner_text().strip()
                if not text or len(text) < 20:
                    continue

                # Zoek prijzen in de rij
                price_matches = re.findall(r'€\s*([\d.,]+)', text)
                prices = []
                for m in price_matches:
                    p = parse_dutch_price(f"€{m}")
                    if p and 1 < p < 50000:
                        prices.append(p)

                if len(prices) < 2:
                    continue

                # Laagste = huidige prijs, hoogste = oude prijs
                current_price = min(prices)
                original_price = max(prices)

                if current_price >= original_price:
                    continue

                discount = ((original_price - current_price) / original_price) * 100
                if discount < 15:
                    continue

                # URL zoeken
                link = row.query_selector('a[href*="/pricewatch/"], a[href*="tweakers.net"]')
                if not link:
                    continue
                url = link.get_attribute("href") or ""
                if not url.startswith("http"):
                    url = f"https://tweakers.net{url}"

                base_url = url.split("?")[0].split("#")[0]
                if base_url in seen_urls:
                    continue
                seen_urls.add(base_url)

                # Naam
                name = link.inner_text().strip()
                if not name or len(name) < 5:
                    continue

                deals.append({
                    "product_name": name[:200],
                    "shop": "Tweakers Pricewatch",
                    "current_price": round(current_price, 2),
                    "original_price": round(original_price, 2),
                    "discount_percent": round(discount, 1),
                    "url": url,
                    "_country": "NL",
                })

            except Exception:
                continue

    except Exception:
        pass

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
                    'button[id*="accept"], [class*="cookie"] button, '
                    '[data-testid*="accept"], button:has-text("Akkoord"), '
                    'button:has-text("Accepteren")'
                )
                if cookie_btn:
                    cookie_btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Scroll voor meer content
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)

            # Methode 1: standaard deal extractie
            found = _extract_deals_from_page(page)

            # Methode 2: prijsdalingen rijen
            if len(found) < 3:
                found2 = _scrape_pricewatch_drops(page)
                # Voeg toe wat we nog niet hebben
                for d in found2:
                    base = d["url"].split("?")[0].split("#")[0]
                    if base not in seen_urls:
                        found.append(d)

            for d in found:
                base = d["url"].split("?")[0].split("#")[0]
                if base not in seen_urls:
                    seen_urls.add(base)
                    deals.append(d)

            print(f"[Tweakers] {len(found)} deals op {url.split('/')[-2] or url.split('/')[-1]}")
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

        # Methode 1: Zoekresultaten met prijzen
        price_elements = page.query_selector_all(
            '.price, [class*="price"], [class*="Price"]'
        )
        for el in price_elements:
            p = parse_dutch_price(el.inner_text())
            if p and 1 < p < 50000:
                prices.append(p)

        # Methode 2: Klik op eerste Pricewatch resultaat en haal prijzen op
        if not prices:
            first_result = page.query_selector(
                'a[href*="/pricewatch/"], .searchResult a[href*="tweakers.net"]'
            )
            if first_result:
                href = first_result.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = f"https://tweakers.net{href}"
                    page.goto(href, timeout=15000)
                    page.wait_for_timeout(2000)

                    # Op productpagina: haal shop-prijzen op
                    shop_prices = page.query_selector_all(
                        '.shop-offer__price, [class*="offerPrice"], '
                        'table.pricing td.price, [class*="shop-price"], '
                        '[class*="priceAmount"]'
                    )
                    for el in shop_prices:
                        p = parse_dutch_price(el.inner_text())
                        if p and 1 < p < 50000:
                            prices.append(p)

                    # Fallback: "vanaf" prijs
                    if not prices:
                        try:
                            main = page.query_selector('main, [role="main"], #content')
                            text = main.inner_text() if main else page.inner_text("body")
                            for m in re.findall(r'(?:vanaf|laagste|prijs)\s*€\s*([\d.,]+)', text, re.IGNORECASE):
                                p = parse_dutch_price(f"€{m}")
                                if p and 1 < p < 50000:
                                    prices.append(p)
                        except Exception:
                            pass

                    # Fallback: alle € bedragen op de pagina
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
