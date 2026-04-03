"""
mydealz.de scraper — Duitse deals die naar NL verzonden kunnen worden.
Focust op de Preisfehler (prijsfouten) groep + heetste deals.

v2.1: Filtert verlopen/expired deals + betere prijsextractie.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay

# Shops/bronnen die we blokkeren (China, niet-EU)
BLOCKED_MERCHANTS = [
    'aliexpress', 'ali express', 'banggood', 'gearbest', 'geekbuying',
    'tomtop', 'cafago', 'lightinthebox', 'wish.com', 'temu', 'shein',
    'dhgate', 'miniinthebox', 'dealextreme', 'dx.com', 'goboo',
]

MYDEALZ_URLS = [
    "https://www.mydealz.de/gruppe/preisfehler",  # Prijsfouten!
    "https://www.mydealz.de/neue-deals",           # Nieuwste deals
    "https://www.mydealz.de/hot",                  # Heetste deals
]


def _is_expired(article):
    """Check of een deal als verlopen/expired gemarkeerd is."""
    try:
        # Mydealz markeert verlopen deals met specifieke classes
        classes = article.get_attribute("class") or ""
        if any(c in classes.lower() for c in ['expired', 'abgelaufen', 'thread--expired', 'thread--dimmed']):
            return True

        # Check op "abgelaufen" of "expired" badge/label
        badges = article.query_selector_all('[class*="expired"], [class*="abgelaufen"], .cept-threadStatus, [class*="threadBadge"]')
        for badge in badges:
            text = badge.inner_text().strip().lower()
            if any(w in text for w in ['abgelaufen', 'expired', 'beendet', 'vorbei', 'ausverkauft']):
                return True

        # Check op doorgestreepte/vervaagde deal indicator
        overlay = article.query_selector('[class*="threadCardLayout--faded"]')
        if overlay:
            return True
    except Exception:
        pass
    return False


def _is_blocked_merchant(shop_name, title):
    """Check of de merchant uit China/niet-EU komt."""
    text = f"{shop_name} {title}".lower()
    return any(blocked in text for blocked in BLOCKED_MERCHANTS)


def _extract_prices_smart(article):
    """
    Slimme prijsextractie — gebruikt specifieke elementen in plaats van
    alle €-bedragen uit de tekst te halen.
    """
    current_price = None
    original_price = None

    # 1. Doorgestreepte prijs = originele prijs
    strike_selectors = [
        'span[class*="mute--text"] span[class*="lineThrough"]',
        'span[class*="text--lineThrough"]',
        'span[class*="threadItemCard-crossedPrice"]',
        's',  # <s> tag = strikethrough
    ]
    for sel in strike_selectors:
        el = article.query_selector(sel)
        if el:
            p = parse_dutch_price(el.inner_text())
            if p and p > 0:
                original_price = p
                break

    # 2. Deal-prijs = current price (de vetgedrukte/opvallende prijs)
    price_selectors = [
        '[class*="thread-price"]',
        '[class*="threadItemCard-price"]',
        'span[class*="threadPrice"]',
        'span[class*="text--b"][class*="size--all-xl"]',
        'span[class*="text--b"][class*="cept-tp"]',
    ]
    for sel in price_selectors:
        el = article.query_selector(sel)
        if el:
            p = parse_dutch_price(el.inner_text())
            if p and p > 0:
                current_price = p
                break

    # 3. Alleen als specifieke selectors niks gaven, doe voorzichtige text scan
    if not current_price or not original_price:
        # Zoek prijzen maar alleen in de prijs-container, niet overal
        price_container = article.query_selector('[class*="threadItem-price"], [class*="threadItemCard-price"]')
        if price_container:
            text = price_container.inner_text()
            found = []
            for match in re.findall(r'€\s*[\d.,]+', text):
                p = parse_dutch_price(match)
                if p and p > 0:
                    found.append(p)
            if found:
                if not current_price:
                    current_price = min(found)
                if not original_price and len(found) >= 2:
                    original_price = max(found)

    # 4. Sanity check: current moet lager zijn dan original
    if current_price and original_price:
        if current_price >= original_price:
            # Swap als ze per ongeluk omgedraaid zijn
            if original_price < current_price:
                current_price, original_price = original_price, current_price
            else:
                original_price = None

    # 5. Sanity check: verschil mag niet absurd zijn
    # (bijv. €0.77 current en €77 original = waarschijnlijk multipack vs single)
    if current_price and original_price:
        ratio = original_price / current_price
        if ratio > 50:
            # Te groot verschil — waarschijnlijk verkeerde prijzen opgepikt
            original_price = None

    return current_price, original_price


def scrape(browser):
    """Scrape mydealz.de deals. Geeft lijst van deal-dicts terug."""
    deals = []
    seen_urls = set()

    for url in MYDEALZ_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "de-DE,de;q=0.9,nl;q=0.8"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            # mydealz deal cards (zelfde platform als Pepper)
            articles = page.query_selector_all('article[class*="thread"], article[id*="thread"]')
            if not articles:
                articles = page.query_selector_all('[class*="threadGrid"], [class*="thread--"]')

            expired_count = 0
            blocked_count = 0
            print(f"[mydealz] {len(articles)} deals op {url.split('/')[-1]}")

            for article in articles:
                try:
                    # Check of deal verlopen is
                    if _is_expired(article):
                        expired_count += 1
                        continue

                    # Titel
                    title_el = article.query_selector('a[class*="thread-title"], [class*="threadTitle"] a, strong a')
                    if not title_el:
                        title_el = article.query_selector('a[href*="/deals/"]')
                    if not title_el:
                        continue

                    name = title_el.inner_text().strip()
                    href = title_el.get_attribute("href")
                    if not name or len(name) < 5:
                        continue

                    deal_url = href
                    if deal_url and not deal_url.startswith("http"):
                        deal_url = f"https://www.mydealz.de{deal_url}"

                    # Externe link
                    ext_link = article.query_selector('a[rel*="nofollow"], a[href*="goto/deal"]')
                    if ext_link:
                        ext_href = ext_link.get_attribute("href")
                        if ext_href:
                            deal_url = ext_href if ext_href.startswith("http") else f"https://www.mydealz.de{ext_href}"

                    # Deduplicatie
                    if deal_url in seen_urls:
                        continue
                    seen_urls.add(deal_url)

                    # Winkel
                    merchant_el = article.query_selector('[class*="merchant"], [class*="cept-merchant"]')
                    shop_name = "mydealz"
                    if merchant_el:
                        shop_name = merchant_el.inner_text().strip()[:30]

                    # China/AliExpress filter
                    if _is_blocked_merchant(shop_name, name):
                        blocked_count += 1
                        continue

                    # Prijzen (slimme extractie)
                    current_price, original_price = _extract_prices_smart(article)

                    # Temperatuur
                    temp_el = article.query_selector('[class*="vote-temp"], [class*="voteTemp"]')
                    temperature = 0
                    if temp_el:
                        temp_text = temp_el.inner_text().strip().replace("°", "").replace(",", ".")
                        try:
                            temperature = float(temp_text)
                        except (ValueError, TypeError):
                            pass

                    if current_price and original_price and original_price > current_price:
                        discount = ((original_price - current_price) / original_price) * 100
                        deals.append({
                            "product_name": name[:200],
                            "shop": f"mydealz ({shop_name})",
                            "current_price": current_price,
                            "original_price": original_price,
                            "discount_percent": round(discount, 1),
                            "url": deal_url,
                            "_temperature": temperature,
                            "_country": "DE",
                        })

                except Exception:
                    continue

            if expired_count:
                print(f"    ({expired_count} verlopen deals overgeslagen)")
            if blocked_count:
                print(f"    ({blocked_count} China/niet-EU deals geblokkeerd)")

            page.close()
            respectful_delay()

        except Exception as e:
            print(f"[mydealz] Fout bij {url}: {e}")

    return deals
