"""
PriceDrop Scanner v2 — Prijsverificatie
Checkt de ECHTE marktprijs via Idealo.nl en Google Shopping.
Detecteert nep-kortingen (opgeblazen "was-prijzen").

v2.1: Volledig herschreven — oude versie gaf altijd €33 terug door
te brede selectors en min() over alle €-bedragen op de pagina.
"""

import re
import time
import random
from scrapers.base import parse_dutch_price, random_user_agent, respectful_delay


def _extract_idealo_prices(page):
    """Haal prijzen uit Idealo zoekresultaten via specifieke product-card selectors."""
    prices = []

    # Idealo product cards bevatten prijzen in specifieke structuur
    # Probeer meerdere bekende selectors voor Idealo.nl product listings
    selectors = [
        # Productkaart prijzen (zoekresultaten)
        '[data-testid="product-listing"] [data-testid="price"]',
        '.sr-productSummary__priceComparison_price',
        '.sr-detailedProductCard__priceComparison',
        '.sr-resultItemPrice__price',
        '.offerList-item__price',
        # Productpagina: "vanaf" prijs
        '.productOffers-listItemOfferPrice',
        '[class*="ProductPrice"]',
    ]

    for sel in selectors:
        elements = page.query_selector_all(sel)
        for el in elements:
            text = el.inner_text().strip()
            p = parse_dutch_price(text)
            if p and 1 < p < 50000:
                prices.append(p)
        if prices:
            break

    # Fallback: zoek "vanaf €X" patronen in de zoekresultaten
    if not prices:
        try:
            # Beperk tot de main content area, niet header/footer/nav
            main = page.query_selector('main, [role="main"], #content, .sr-resultList')
            if main:
                text = main.inner_text()
            else:
                text = page.inner_text("body")

            # Zoek specifiek "vanaf €X" of "ab €X" patronen (Idealo's standaard format)
            for match in re.findall(r'(?:vanaf|ab|from)\s*€\s*([\d.,]+)', text, re.IGNORECASE):
                p = parse_dutch_price(f"€{match}")
                if p and 1 < p < 50000:
                    prices.append(p)

            # Als dat niks oplevert, zoek prijzen maar ALLEEN in product-achtige context
            if not prices:
                # Zoek regels die een prijs bevatten EN een productnaam-achtig stuk tekst
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip navigatie/footer/cookie regels
                    if len(line) < 10 or len(line) > 500:
                        continue
                    if any(skip in line.lower() for skip in ['cookie', 'privacy', 'inloggen', 'account', 'warenkorb', 'cart', 'newsletter', 'meld je aan']):
                        continue
                    price_matches = re.findall(r'€\s*([\d.,]+)', line)
                    for m in price_matches:
                        p = parse_dutch_price(f"€{m}")
                        if p and 2 < p < 50000:
                            prices.append(p)
        except Exception:
            pass

    return prices


def _extract_google_shopping_prices(page):
    """Haal prijzen uit Google Shopping resultaten via specifieke selectors."""
    prices = []

    # Google Shopping product cards
    selectors = [
        # Prijs in shopping resultaten
        '[data-sh-or] span.a8Pemb',  # Shopping prijs element
        '.sh-dgr__content .a8Pemb',
        '.sh-dlr__list-result .a8Pemb',
        '.rgHvZc .a8Pemb',           # Grid resultaat prijs
        '.sh-pr__content .kHxwFf',
        # Alternatieve selectors
        '.result-container [aria-label*="€"]',
        '.sh-dgr__grid-result .sh-dgr__content',
    ]

    for sel in selectors:
        elements = page.query_selector_all(sel)
        for el in elements:
            text = el.inner_text().strip()
            p = parse_dutch_price(text)
            if p and 1 < p < 50000:
                prices.append(p)
        if prices:
            break

    # Fallback: zoek prijzen in het shopping grid area alleen
    if not prices:
        try:
            # Google Shopping resultaten zitten in specifieke containers
            containers = page.query_selector_all('[data-sh-or], .sh-dgr__content, .sh-dlr__list-result, .rgHvZc')
            for container in containers[:20]:  # Max 20 resultaten
                text = container.inner_text().strip()
                for match in re.findall(r'€\s*([\d.,]+)', text):
                    p = parse_dutch_price(f"€{match}")
                    if p and 2 < p < 50000:
                        prices.append(p)

            # Laatste fallback: zoek in de body maar filter agressief
            if not prices:
                text = page.inner_text("body")
                # Zoek ALLE €-bedragen
                all_prices = []
                for match in re.findall(r'€\s*([\d.,]+)', text):
                    p = parse_dutch_price(f"€{match}")
                    if p and 2 < p < 50000:
                        all_prices.append(p)

                if len(all_prices) >= 3:
                    # Neem de mediaan als referentie, niet min()
                    all_prices.sort()
                    median = all_prices[len(all_prices) // 2]
                    # Filter prijzen die te ver van de mediaan afwijken
                    prices = [p for p in all_prices if median * 0.3 < p < median * 3]
        except Exception:
            pass

    return prices


def _pick_best_market_price(prices, deal_current_price, deal_original_price):
    """
    Kies de beste marktprijs uit gevonden prijzen.
    Niet simpelweg min() — dat geeft vaak rommel.

    Strategie:
    - Filter extreme uitschieters
    - De marktprijs moet redelijkerwijs bij het product passen
    - Neem de mediaan van de gefilterde prijzen als meest betrouwbare waarde
    """
    if not prices:
        return None

    # Verwijder duplicaten en sorteer
    prices = sorted(set(prices))

    # Referentieprijs = gemiddelde van deal-prijs en "was"-prijs
    ref_price = (deal_current_price + deal_original_price) / 2

    # Filter: prijs moet binnen 10% - 500% van referentieprijs liggen
    # (een marktprijs van €5 voor een product van €200 is onzin)
    filtered = [p for p in prices if ref_price * 0.1 < p < ref_price * 5]

    if not filtered:
        # Te streng gefilterd — probeer breder
        filtered = [p for p in prices if ref_price * 0.05 < p < ref_price * 10]

    if not filtered:
        return None

    if len(filtered) == 1:
        return filtered[0]

    # Neem de mediaan — meest representatief voor "echte" marktprijs
    median_idx = len(filtered) // 2
    return filtered[median_idx]


def search_idealo(product_name, browser_context, deal_price=None, original_price=None):
    """Zoek een product op Idealo.nl en haal de marktprijs op."""
    page = None
    try:
        # Maak zoekterm schoon — behoud alleen relevante woorden
        clean_name = re.sub(r'[^\w\s\-\.]', ' ', product_name)
        # Verwijder veelvoorkomende ruis-woorden
        noise = ['aanbieding', 'deal', 'korting', 'sale', 'gratis', 'free', 'nieuw', 'new', 'hot']
        words = [w for w in clean_name.split() if w.lower() not in noise]
        clean_name = ' '.join(words[:7])  # Max 7 woorden

        page = browser_context.new_page()
        page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
        search_url = f"https://www.idealo.nl/mscat.html?q={clean_name.replace(' ', '+')}"
        page.goto(search_url, timeout=15000)
        page.wait_for_timeout(2500)

        # Accepteer cookies als die popup verschijnt
        try:
            cookie_btn = page.query_selector('[data-testid="accept-all"], #onetrust-accept-btn-handler, [class*="consent"] button')
            if cookie_btn:
                cookie_btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        prices = _extract_idealo_prices(page)
        page.close()
        page = None

        if prices and deal_price and original_price:
            return _pick_best_market_price(prices, deal_price, original_price)
        elif prices:
            prices.sort()
            return prices[len(prices) // 2]  # mediaan
        return None

    except Exception as e:
        if page:
            try:
                page.close()
            except Exception:
                pass
        return None


def search_google_shopping(product_name, browser_context, deal_price=None, original_price=None):
    """Zoek een product via Google Shopping NL voor marktprijs."""
    page = None
    try:
        clean_name = re.sub(r'[^\w\s\-\.]', ' ', product_name)
        noise = ['aanbieding', 'deal', 'korting', 'sale', 'gratis', 'free']
        words = [w for w in clean_name.split() if w.lower() not in noise]
        clean_name = ' '.join(words[:6])

        page = browser_context.new_page()
        page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
        url = f"https://www.google.nl/search?q={clean_name.replace(' ', '+')}&tbm=shop&gl=nl&hl=nl"
        page.goto(url, timeout=15000)
        page.wait_for_timeout(2500)

        # Accepteer Google cookies
        try:
            consent = page.query_selector('button[id="L2AGLb"], [aria-label*="Alles accepteren"], [aria-label*="Accept all"]')
            if consent:
                consent.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        prices = _extract_google_shopping_prices(page)
        page.close()
        page = None

        if prices and deal_price and original_price:
            return _pick_best_market_price(prices, deal_price, original_price)
        elif prices:
            prices.sort()
            return prices[len(prices) // 2]
        return None

    except Exception as e:
        if page:
            try:
                page.close()
            except Exception:
                pass
        return None


def verify_deal(deal, browser_context):
    """
    Verifieer een deal door de marktprijs op te zoeken.
    Returned dict met verificatie-data.
    """
    product_name = deal["product_name"]
    current_price = deal["current_price"]
    original_price = deal["original_price"]
    shop_discount = deal["discount_percent"]

    # Probeer Idealo eerst (meest betrouwbaar voor NL)
    market_price = search_idealo(product_name, browser_context, current_price, original_price)
    respectful_delay()

    # Fallback naar Google Shopping
    if market_price is None:
        market_price = search_google_shopping(product_name, browser_context, current_price, original_price)
        respectful_delay()

    if market_price is None:
        return {
            "market_price": None,
            "real_discount_percent": None,
            "is_verified": False,
            "is_fake_discount": False,
        }

    # Sanity check: als de marktprijs onrealistisch is, verwerp
    ref = (current_price + original_price) / 2
    if market_price < ref * 0.05 or market_price > ref * 20:
        print(f"    [!] Marktprijs €{market_price:.2f} onrealistisch (ref: €{ref:.2f}), overgeslagen")
        return {
            "market_price": None,
            "real_discount_percent": None,
            "is_verified": False,
            "is_fake_discount": False,
        }

    # Bereken de ECHTE korting (vs marktprijs, niet vs "was-prijs")
    if market_price > 0:
        real_discount = ((market_price - current_price) / market_price) * 100
    else:
        real_discount = 0

    # Detecteer nep-korting: als de shop-korting >2x hoger is dan de echte korting
    is_fake = False
    if real_discount < (shop_discount * 0.5):
        # Shop claimt bijv 60% korting, maar echt is het maar 20% → nep
        is_fake = True
    # Ook nep als marktprijs dicht bij current_price ligt (geen echte deal)
    if market_price > 0 and abs(market_price - current_price) / market_price < 0.05:
        is_fake = True

    return {
        "market_price": round(market_price, 2),
        "real_discount_percent": round(real_discount, 1),
        "is_verified": True,
        "is_fake_discount": is_fake,
    }


def verify_deals_batch(deals, browser_context, max_checks=20):
    """Verifieer een batch deals. Limiet om niet te veel te queryen."""
    results = []
    checked = 0

    for deal in deals:
        if checked >= max_checks:
            break

        print(f"  Verificatie {checked+1}/{min(len(deals), max_checks)}: {deal['product_name'][:50]}...")
        result = verify_deal(deal, browser_context)

        if result["is_verified"]:
            marker = "NEP" if result["is_fake_discount"] else "ECHT"
            print(f"    Marktprijs: €{result['market_price']:.2f} | Echte korting: {result['real_discount_percent']:.0f}% [{marker}]")
        else:
            print(f"    Geen marktprijs gevonden")

        results.append(result)
        checked += 1

    return results
