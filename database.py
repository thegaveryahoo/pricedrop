"""
PriceDrop Scanner v2 — SQLite database voor prijshistorie en gevonden deals
Met prijsverificatie: marktprijs, echte korting, nep-korting detectie.
"""

import sqlite3
import os
from datetime import datetime
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Deals tabel — gevonden prijsfouten
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            shop TEXT NOT NULL,
            current_price REAL NOT NULL,
            original_price REAL NOT NULL,
            discount_percent REAL NOT NULL,
            url TEXT NOT NULL,
            found_at TEXT NOT NULL,
            notified INTEGER DEFAULT 0,
            market_price REAL DEFAULT NULL,
            real_discount_percent REAL DEFAULT NULL,
            is_verified INTEGER DEFAULT 0,
            is_fake_discount INTEGER DEFAULT 0,
            category TEXT DEFAULT '',
            UNIQUE(url, current_price)
        )
    """)

    # Prijshistorie — voor trend-analyse
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            shop TEXT NOT NULL,
            price REAL NOT NULL,
            url TEXT NOT NULL,
            scraped_at TEXT NOT NULL
        )
    """)

    # Scan log — wanneer is er voor het laatst gescand
    c.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            shops_scanned INTEGER DEFAULT 0,
            deals_found INTEGER DEFAULT 0,
            new_deals INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
    """)

    # Migratie: voeg kolommen toe als ze nog niet bestaan
    try:
        c.execute("ALTER TABLE deals ADD COLUMN market_price REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN real_discount_percent REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN is_verified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN is_fake_discount INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN category TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN mp_avg_price REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN mp_median_price REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN mp_listings INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN mp_profit REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN country TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN country_flag TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN tweakers_price REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE deals ADD COLUMN verification_source TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def save_deal(product_name, shop, current_price, original_price, discount_percent, url,
              market_price=None, real_discount_percent=None, is_verified=False, is_fake_discount=False,
              category="", country="", country_flag=""):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO deals
            (product_name, shop, current_price, original_price, discount_percent, url, found_at,
             market_price, real_discount_percent, is_verified, is_fake_discount, category,
             country, country_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_name, shop, current_price, original_price, discount_percent, url,
              datetime.now().isoformat(), market_price, real_discount_percent,
              1 if is_verified else 0, 1 if is_fake_discount else 0, category,
              country, country_flag))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def update_deal_verification(deal_id, market_price, real_discount_percent, is_fake_discount,
                              tweakers_price=None, verification_source=""):
    """Update een deal met prijsverificatie-data."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE deals SET market_price = ?, real_discount_percent = ?,
        is_verified = 1, is_fake_discount = ?,
        tweakers_price = ?, verification_source = ?
        WHERE id = ?
    """, (market_price, real_discount_percent, 1 if is_fake_discount else 0,
          tweakers_price, verification_source, deal_id))
    conn.commit()
    conn.close()


def update_deal_marktplaats(deal_id, mp_avg, mp_median, mp_listings, mp_profit):
    """Update een deal met Marktplaats verkoopdata."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE deals SET mp_avg_price = ?, mp_median_price = ?,
        mp_listings = ?, mp_profit = ?
        WHERE id = ?
    """, (mp_avg, mp_median, mp_listings, mp_profit, deal_id))
    conn.commit()
    conn.close()


def save_price(product_name, shop, price, url):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO price_history (product_name, shop, price, url, scraped_at)
        VALUES (?, ?, ?, ?, ?)
    """, (product_name, shop, price, url, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_avg_price(url, days=30):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT AVG(price) as avg_price, COUNT(*) as data_points
        FROM price_history
        WHERE url = ? AND scraped_at >= datetime('now', ?)
    """, (url, f"-{days} days"))
    row = c.fetchone()
    conn.close()
    if row and row["data_points"] > 0:
        return row["avg_price"], row["data_points"]
    return None, 0


def get_unnotified_deals():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE notified = 0 ORDER BY discount_percent DESC")
    deals = c.fetchall()
    conn.close()
    return deals


def mark_notified(deal_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE deals SET notified = 1 WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()


def get_recent_deals(hours=24):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM deals
        WHERE found_at >= datetime('now', ?)
        ORDER BY discount_percent DESC
    """, (f"-{hours} hours",))
    deals = c.fetchall()
    conn.close()
    return deals


# Scan log functies
def start_scan_log():
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO scan_log (started_at, status) VALUES (?, 'running')",
              (datetime.now().isoformat(),))
    conn.commit()
    scan_id = c.lastrowid
    conn.close()
    return scan_id


def finish_scan_log(scan_id, shops_scanned, deals_found, new_deals):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE scan_log SET finished_at = ?, shops_scanned = ?,
        deals_found = ?, new_deals = ?, status = 'done'
        WHERE id = ?
    """, (datetime.now().isoformat(), shops_scanned, deals_found, new_deals, scan_id))
    conn.commit()
    conn.close()


def get_last_scan():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scan_log ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# Initialiseer database bij import
init_db()
