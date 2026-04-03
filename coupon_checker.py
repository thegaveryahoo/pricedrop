"""
PriceDrop Scanner — Kortingscode checker.
Scrapt actieve kortingscodes van Pepper.com en acties.nl,
en matcht ze met gevonden deals voor extra korting.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay


# Bekende shops waarvoor we codes zoeken
TARGET_SHOPS = [
    "bol.com", "mediamarkt", "amazon", "wehkamp", "bcc",
    "alternate", "megekko", "coolblue", "ibood", "saturn",
]


def scrape_pepper_coupons(browser_context):
    """Scrape actieve kortingscodes van nl.pepper.com."""
    coupons = []
    try:
        page = browser_context.new_page()
        page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
        page.goto("https://nl.pepper.com/kortingscode", timeout=20000)
        page.wait_for_timeout(3000)

        # Scroll voor meer
        for _ in range(3):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(1000)

        # Pepper toont kortingscode-deals per shop
        articles = page.query_selector_all('article[class*="thread"], [class*="voucher"]')

        for article in articles:
            try:
                # Shop naam
                merchant_el = article.query_selector('[class*="merchant"], [class*="cept-merchant"]')
                shop = merchant_el.inner_text().strip().lower() if merchant_el else ""

                # Code
                code_el = article.query_selector('[class*="code"], [class*="voucher-code"], input[type="text"]')
                code = code_el.get_attribute("value") or code_el.inner_text().strip() if code_el else ""

                # Beschrijving
                title_el = article.query_selector('[class*="thread-title"], strong a, [class*="title"]')
                desc = title_el.inner_text().strip() if title_el else ""

                # Korting bedrag/percentage
                discount_text = ""
                all_text = article.inner_text()
                pct_match = re.search(r'(\d+)\s*%\s*(korting|off|rabatt)', all_text, re.I)
                eur_match = re.search(r'€\s*([\d.,]+)\s*(korting|off|rabatt)', all_text, re.I)

                if pct_match:
                    discount_text = f"{pct_match.group(1)}% korting"
                elif eur_match:
                    discount_text = f"€{eur_match.group(1)} korting"

                if code and len(code) >= 3 and shop:
                    coupons.append({
                        "shop": shop,
                        "code": code,
                        "description": desc[:150],
                        "discount": discount_text,
                        "source": "Pepper",
                    })

            except Exception:
                continue

        page.close()
        respectful_delay()

    except Exception as e:
        print(f"[Coupons] Pepper fout: {e}")

    return coupons


def scrape_acties_coupons(browser_context):
    """Scrape actieve kortingscodes van acties.nl."""
    coupons = []

    for shop in TARGET_SHOPS:
        try:
            page = browser_context.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            url = f"https://www.acties.nl/kortingscode/{shop}"
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)

            # Zoek code-elementen
            code_els = page.query_selector_all('[class*="code"], [class*="coupon"], [class*="voucher"]')

            for el in code_els:
                try:
                    text = el.inner_text().strip()
                    # Zoek iets dat eruitziet als een code (alphanumeriek, 4+ tekens)
                    code_match = re.search(r'[A-Z0-9]{4,20}', text)
                    if code_match:
                        code = code_match.group(0)

                        # Zoek omschrijving in parent
                        parent = el.evaluate_handle("el => el.closest('li, div, article, tr')")
                        parent_text = parent.evaluate("el => el.innerText") if parent else text

                        # Korting
                        discount = ""
                        pct = re.search(r'(\d+)\s*%', parent_text)
                        eur = re.search(r'€\s*([\d.,]+)', parent_text)
                        if pct:
                            discount = f"{pct.group(1)}% korting"
                        elif eur:
                            discount = f"€{eur.group(1)} korting"

                        if len(code) >= 4:
                            coupons.append({
                                "shop": shop,
                                "code": code,
                                "description": parent_text[:100].split('\n')[0],
                                "discount": discount,
                                "source": "Acties.nl",
                            })
                except Exception:
                    continue

            page.close()
            respectful_delay()

        except Exception:
            continue

    return coupons


def find_coupons_for_deals(deals, browser_context):
    """
    Zoek kortingscodes die van toepassing kunnen zijn op gevonden deals.
    Matched op shopnaam.
    """
    print(f"[Coupons] Kortingscodes zoeken...")

    all_coupons = []
    all_coupons.extend(scrape_pepper_coupons(browser_context))
    all_coupons.extend(scrape_acties_coupons(browser_context))

    print(f"[Coupons] {len(all_coupons)} codes gevonden")

    # Match codes met deals
    matched = 0
    for deal in deals:
        shop_lower = deal["shop"].lower()
        matching_codes = []

        for coupon in all_coupons:
            if coupon["shop"] in shop_lower or shop_lower.startswith(coupon["shop"]):
                matching_codes.append(coupon)

        if matching_codes:
            # Neem de beste code (hoogste korting)
            best = matching_codes[0]
            deal["coupon_code"] = best["code"]
            deal["coupon_discount"] = best["discount"]
            deal["coupon_source"] = best["source"]
            deal["coupon_desc"] = best["description"]
            matched += 1

    print(f"[Coupons] {matched} deals gematcht met kortingscodes")
    return deals
