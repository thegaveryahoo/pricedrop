"""
PriceDrop Scanner — Verzendkosten per shop.
Bekende drempels voor gratis verzending + standaard tarieven.
Bron: webshop FAQ-pagina's, april 2026.
"""

# Per shop: (gratis_vanaf_eur, standaard_verzendkosten_eur, notities)
SHIPPING_INFO = {
    # Nederlandse shops
    "Bol.com":      {"free_above": 25,   "cost": 3.99,  "note": "Select: altijd gratis"},
    "Coolblue":     {"free_above": 0,    "cost": 0,     "note": "Altijd gratis bezorging"},
    "MediaMarkt":   {"free_above": 50,   "cost": 4.99,  "note": "Ophalen in winkel: gratis"},
    "Amazon.nl":    {"free_above": 25,   "cost": 3.49,  "note": "Prime: altijd gratis"},
    "Alternate":    {"free_above": 50,   "cost": 5.99,  "note": ""},
    "Megekko":      {"free_above": 50,   "cost": 5.95,  "note": ""},
    "BCC":          {"free_above": 30,   "cost": 4.99,  "note": "Ophalen in winkel: gratis"},
    "Wehkamp":      {"free_above": 25,   "cost": 2.95,  "note": ""},
    "iBood":        {"free_above": 0,    "cost": 5.95,  "note": "Verzendkosten bijna altijd €5.95"},
    # Duitse shops
    "Amazon.de":    {"free_above": 39,   "cost": 3.99,  "note": "Prime DE: altijd gratis"},
    "Saturn.de":    {"free_above": 0,    "cost": 0,     "note": "Gratis verzending DE; NL via forwarding ~€5-10"},
    "MediaMarkt.de":{"free_above": 0,    "cost": 0,     "note": "Alleen DE; ophalen grenswinkel"},
    # Deal-aggregators (verzendkosten hangen af van de achterliggende shop)
    "Pepper":       {"free_above": None, "cost": None,  "note": "Verschilt per webshop"},
    "mydealz":      {"free_above": None, "cost": None,  "note": "Verschilt per webshop"},
}


def get_shipping_cost(shop_name, price):
    """
    Bereken verzendkosten voor een shop en prijs.
    Returns: (kosten_eur, is_gratis, notitie)
    """
    # Normaliseer shopnaam (verwijder Pepper/mydealz subshop info)
    clean_shop = shop_name.split("(")[0].strip()

    info = SHIPPING_INFO.get(clean_shop)
    if not info:
        # Probeer partial match
        for key, val in SHIPPING_INFO.items():
            if key.lower() in clean_shop.lower():
                info = val
                break

    if not info or info["cost"] is None:
        # Onbekende shop of aggregator — schat conservatief
        return (4.99, False, "Verzendkosten onbekend (~€5)")

    if info["free_above"] is not None and price >= info["free_above"]:
        return (0, True, f"Gratis boven €{info['free_above']}")
    elif info["free_above"] == 0:
        return (0, True, info["note"] or "Gratis verzending")
    else:
        note = info["note"] or f"Onder €{info['free_above']}: €{info['cost']}"
        return (info["cost"], False, note)


def add_shipping_to_deals(deals):
    """Voeg verzendkosten toe aan een lijst deals en pas winst aan."""
    for deal in deals:
        cost, is_free, note = get_shipping_cost(deal["shop"], deal["current_price"])
        deal["shipping_cost"] = cost
        deal["shipping_free"] = is_free
        deal["shipping_note"] = note
        # Pas winstberekening aan
        if deal.get("mp_profit") is not None:
            deal["mp_profit_after_shipping"] = deal["mp_profit"] - (cost or 0)
    return deals
