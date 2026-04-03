"""
PriceDrop Scanner v2 — Configuratie
"""

# Minimale korting om als "prijsfout" te flaggen (percentage)
MIN_DISCOUNT_PERCENT = 40  # Lager gezet: meer deals vinden, webapp filtert verder

# Minimale absolute korting in euro's
MIN_DISCOUNT_EUROS = 20

# Minimale originele prijs
MIN_ORIGINAL_PRICE = 30

# Scan interval in minuten
SCAN_INTERVAL_MINUTES = 15

# Prijsverificatie: max aantal deals om te checken per scan
MAX_PRICE_CHECKS = 15

# Request instellingen
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT = 15

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Database pad
import os
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_history.db")

# Telegram (optioneel) — uit .env bestand
def _load_env_val(key, default=""):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    return default

TELEGRAM_BOT_TOKEN = _load_env_val("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _load_env_val("TELEGRAM_CHAT_ID")

# Welke scrapers actief zijn — v2: VEEL meer shops
ACTIVE_SCRAPERS = [
    # Deal-aggregators (meest effectief — community-gecureerd)
    "pepper",
    "mydealz",
    # NL shops
    "bolcom",
    "coolblue",
    "mediamarkt",
    "amazon_nl",
    "alternate",
    "megekko",
    "bcc",
    "wehkamp",
    "ibood",  # Kan geblokkeerd worden door Akamai, maar proberen
    # DE shops
    "amazon_de",
    "saturn",
]
