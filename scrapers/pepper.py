"""
Pepper.com NL scraper — scrapt de community-gecureerde deals.
Dit is de meest effectieve bron: duizenden gebruikers filteren al de beste deals.
Hoge "temperatuur" = goede deal volgens de community.

v2.1: Filtert verlopen deals, China-bronnen, betere prijsextractie.
"""

import re
from scrapers.base import parse_dutch_price, respectful_delay

# Shops/bronnen die we blokkeren (China, niet-EU)
BLOCKED_MERCHANTS = [
    'aliexpress', 'ali express', 'banggood', 'gearbest', 'geekbuying',
    'tomtop', 'cafago', 'lightinthebox', 'wish.com', 'temu', 'shein',
    'dhgate', 'miniinthebox', 'dealextreme', 'dx.com', 'goboo',
]

PEPPER_URLS = [
    "https://nl.pepper.com/nieuw",           # Nieuwste deals
    "https://nl.pepper.com/heetste",          # Populairste deals
    "https://nl.pepper.com/groep/prijsfout",  # Specifiek prijsfouten
]


def _is_expired(article):
    """Check of een deal als verlopen/expired gemarkeerd is."""
    try:
        classes = article.get_attribute("class") or ""
        if any(c in classes.lower() for c in ['expired', 'afgelopen', 'thread--expired', 'thread--dimmed']):
            return True

        badges = article.query_selector_all('[class*="expired"], [class*="afgelopen"], .cept-threadStatus, [class*="threadBadge"]')
        for badge in badges:
            text = badge.inner_text().strip().lower()
            if any(w in text for w in ['afgelopen', 'verlopen', 'expired', 'uitverkocht', 'voorbij']):
                return True

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
    Slimme prijsextractie — gebruikt specifieke elementen.
    Voorkomt de Monster Energy bug (multipack vs stuksprijs).
    """
    current_price = None
    original_price = None

    # 1. Doorgestreepte prijs = originele prijs
    strike_selectors = [
        'span[class*="mute--text"] span[class*="lineThrough"]',
        'span[class*="text--lineThrough"]',
        's',
    ]
    for sel in strike_selectors:
        el = article.query_selector(sel)
        if el:
            p = parse_dutch_price(el.inner_text())
            if p and p > 0:
                original_price = p
                break

    # 2. Deal-prijs
    price_selectors = [
        '[class*="thread-price"]',
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

    # 3. Voorzichtige fallback — alleen in prijs-container
    if not current_price or not original_price:
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

    # 4. Sanity checks
    if current_price and original_price:
        if current_price >= original_price:
            if original_price < current_price:
                current_price, original_price = original_price, current_price
            else:
                original_price = None

    # Verschil mag niet absurd groot zijn (voorkomt Monster Energy bug)
    if current_price and original_price:
        ratio = original_price / current_price
        if ratio > 50:
            original_price = None

    return current_price, original_price


def scrape(browser):
    """Scrape nl.pepper.com deals. Geeft lijst van deal-dicts terug."""
    deals = []
    seen_urls = set()

    for url in PEPPER_URLS:
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "nl-NL,nl;q=0.9"})
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)

            # Scroll voor meer deals
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1000)

            # Pepper deal cards
            articles = page.query_selector_all('article[class*="thread"], article[id*="thread"]')
            if not articles:
                articles = page.query_selector_all('[class*="threadGrid"], [class*="thread--"]')

            expired_count = 0
            blocked_count = 0
            print(f"[Pepper] {len(articles)} deals op {url.split('/')[-1]}")

            for article in articles:
                try:
                    # Check verlopen
                    if _is_expired(article):
                        expired_count += 1
                        continue

                    # Titel
                    title_el = article.query_selector('a[class*="thread-title"], [class*="threadTitle"] a, strong a')
                    if not title_el:
                        title_el = article.query_selector('a[href*="/aanbiedingen/"]')
                    if not title_el:
                        continue

                    name = title_el.inner_text().strip()
                    href = title_el.get_attribute("href")
                    if not name or len(name) < 5:
                        continue

                    # Deal URL
                    deal_url = href
                    if deal_url and not deal_url.startswith("http"):
                        deal_url = f"https://nl.pepper.com{deal_url}"

                    # Externe link (de echte webshop link)
                    ext_link = article.query_selector('a[rel*="nofollow"], a[href*="goto/deal"]')
                    if ext_link:
                        ext_href = ext_link.get_attribute("href")
                        if ext_href:
                            deal_url = ext_href if ext_href.startswith("http") else f"https://nl.pepper.com{ext_href}"

                    # Deduplicatie
                    if deal_url in seen_urls:
                        continue
                    seen_urls.add(deal_url)

                    # Winkel naam
                    merchant_el = article.query_selector('[class*="merchant"], [class*="cept-merchant"], span[class*="chip"]')
                    shop_name = "Pepper deal"
                    if merchant_el:
                        shop_name = merchant_el.inner_text().strip()[:30]

                    # China/AliExpress filter
                    if _is_blocked_merchant(shop_name, name):
                        blocked_count += 1
                        continue

                    # Prijzen (slimme extractie)
                    current_price, original_price = _extract_prices_smart(article)

                    # Temperatuur (community score)
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
                            "shop": f"Pepper ({shop_name})",
                            "current_price": current_price,
                            "original_price": original_price,
                            "discount_percent": round(discount, 1),
                            "url": deal_url,
                            "_temperature": temperature,
                            "_country": "NL",
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
            print(f"[Pepper] Fout bij {url}: {e}")

    return deals
