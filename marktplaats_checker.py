"""
PriceDrop Scanner v2 — Marktplaats prijscheck
Zoekt voor elk product de gemiddelde verkoopprijs op Marktplaats,
zodat je weet of je het echt met winst kunt doorverkopen.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay


def search_marktplaats(product_name, browser_context):
    """
    Zoek een product op Marktplaats en haal prijzen op van vergelijkbare listings.
    Returned dict met: avg_price, min_price, max_price, num_listings.
    """
    try:
        # Schoon de zoekterm op — kort en relevant houden
        clean = re.sub(r'[^\w\s\-]', ' ', product_name)
        words = clean.split()[:5]  # Max 5 woorden
        query = '+'.join(words)

        page = browser_context.new_page()
        page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
        url = f"https://www.marktplaats.nl/q/{query}/"
        page.goto(url, timeout=15000)
        page.wait_for_timeout(3000)

        prices = []

        # Marktplaats listing prijzen
        # Zoek alle prijselementen op de pagina
        price_elements = page.query_selector_all('[class*="price"], [data-testid*="price"]')
        for el in price_elements:
            text = el.inner_text().strip()
            p = parse_dutch_price(text)
            if p and p > 1:
                prices.append(p)

        # Fallback: zoek €-bedragen in de tekst
        if len(prices) < 3:
            body_text = page.inner_text("body")
            for match in re.findall(r'€\s*([\d.,]+)', body_text):
                p = parse_dutch_price(f"€{match}")
                if p and 1 < p < 50000:
                    prices.append(p)

        page.close()

        if not prices:
            return None

        # Filter uitschieters (< 10% of > 300% van mediaan)
        prices.sort()
        if len(prices) >= 5:
            median = prices[len(prices) // 2]
            prices = [p for p in prices if median * 0.1 < p < median * 3]

        if not prices:
            return None

        return {
            "avg_price": round(sum(prices) / len(prices), 2),
            "min_price": round(min(prices), 2),
            "max_price": round(max(prices), 2),
            "median_price": round(prices[len(prices) // 2], 2),
            "num_listings": len(prices),
        }

    except Exception as e:
        try:
            page.close()
        except Exception:
            pass
        return None


def check_marktplaats_batch(deals, browser_context, max_checks=10):
    """Check Marktplaats prijzen voor een batch deals."""
    results = []
    checked = 0

    for deal in deals:
        if checked >= max_checks:
            break

        print(f"  Marktplaats {checked+1}/{min(len(deals), max_checks)}: {deal['product_name'][:45]}...")
        result = search_marktplaats(deal["product_name"], browser_context)
        respectful_delay()

        if result:
            mp_price = result["median_price"]
            profit = mp_price - deal["current_price"]
            print(f"    MP mediaan: €{mp_price:.0f} | Inkoop: €{deal['current_price']:.0f} | Winst: €{profit:.0f} ({result['num_listings']} listings)")
        else:
            print(f"    Geen Marktplaats data gevonden")

        results.append(result)
        checked += 1

    return results
