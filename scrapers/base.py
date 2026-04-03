"""
Base scraper met gedeelde logica voor alle webshop scrapers.
Gebruikt Playwright voor JavaScript-rendered pagina's.
"""

import re
import random
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import USER_AGENTS, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT


def parse_dutch_price(text):
    """Parse Nederlandse prijs-tekst naar float. Bijv. '€ 1.299,99' -> 1299.99"""
    if not text:
        return None
    # Verwijder alles behalve cijfers, punt, komma, en dash
    text = text.replace("EUR", "").replace("€", "").strip()
    text = text.replace("\xa0", "").replace(" ", "")
    # Verwijder '--' of '-' als cent-placeholder
    text = re.sub(r',-+$', '', text)
    text = re.sub(r'-+$', '', text)
    # Nederlandse notatie: 1.299,99 -> 1299.99
    text = text.replace(".", "")  # verwijder duizendtal-punten
    text = text.replace(",", ".")  # komma -> punt voor decimalen
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def random_user_agent():
    return random.choice(USER_AGENTS)


def respectful_delay():
    """Wacht even tussen requests om de server niet te overbelasten."""
    time.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, 1))
