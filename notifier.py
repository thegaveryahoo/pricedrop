"""
PriceDrop Scanner — Notificaties (Windows toast + optioneel Telegram)
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_windows_notification(title, message):
    """Stuur een Windows 10/11 toast notificatie."""
    try:
        from plyer import notification
        notification.notify(
            title=title[:64],
            message=message[:256],
            app_name="PriceDrop Scanner",
            timeout=30,
        )
    except Exception as e:
        print(f"[Notificatie] Windows toast mislukt: {e}")


def send_telegram(message):
    """Stuur een bericht via Telegram bot (optioneel)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
    except Exception as e:
        print(f"[Notificatie] Telegram mislukt: {e}")


def notify_deal(deal):
    """Stuur notificatie voor een gevonden deal."""
    name = deal["product_name"][:80]
    shop = deal["shop"]
    current = deal["current_price"]
    original = deal["original_price"]
    discount = deal["discount_percent"]
    url = deal["url"]
    estimated_resale = original * 0.75  # Geschatte Marktplaats doorverkoopwaarde

    # Windows toast
    title = f"DEAL: -{discount:.0f}% bij {shop}"
    body = f"{name}\n€{current:.2f} (was €{original:.2f})\nGeschatte winst: €{estimated_resale - current:.0f}"
    send_windows_notification(title, body)

    # Telegram
    telegram_msg = (
        f"🔥 <b>PRIJSFOUT GEVONDEN: -{discount:.0f}%</b>\n\n"
        f"📦 {name}\n"
        f"🏪 {shop}\n"
        f"💰 <b>€{current:.2f}</b> (was €{original:.2f})\n"
        f"📈 Geschatte doorverkoopwaarde: ~€{estimated_resale:.0f}\n"
        f"💵 Geschatte winst: ~€{estimated_resale - current:.0f}\n\n"
        f"🔗 <a href='{url}'>Direct bekijken</a>"
    )
    send_telegram(telegram_msg)


def generate_html_report(deals, filepath=None):
    """Genereer een HTML overzicht van alle gevonden deals."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deals_report.html")

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PriceDrop Scanner — Deals</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #e0e0e0; }}
        h1 {{ color: #00d4ff; }}
        .timestamp {{ color: #888; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #16213e; color: #00d4ff; padding: 12px 8px; text-align: left; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #16213e; }}
        .discount {{ color: #ff4444; font-weight: bold; font-size: 1.1em; }}
        .profit {{ color: #00ff88; font-weight: bold; }}
        .price {{ font-weight: bold; }}
        a {{ color: #00d4ff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .no-deals {{ color: #888; padding: 40px; text-align: center; }}
    </style>
</head>
<body>
    <h1>PriceDrop Scanner</h1>
    <div class="timestamp">Laatste scan: {datetime.now().strftime('%d-%m-%Y %H:%M')}</div>
"""

    if not deals:
        html += '<div class="no-deals">Geen deals gevonden die aan de criteria voldoen.</div>'
    else:
        html += """
    <table>
        <tr>
            <th>Product</th>
            <th>Shop</th>
            <th>Prijs</th>
            <th>Was</th>
            <th>Korting</th>
            <th>~Winst</th>
            <th>Link</th>
        </tr>
"""
        for d in sorted(deals, key=lambda x: x["discount_percent"], reverse=True):
            resale = d["original_price"] * 0.75
            profit = resale - d["current_price"]
            html += f"""        <tr>
            <td>{d['product_name'][:60]}</td>
            <td>{d['shop']}</td>
            <td class="price">€{d['current_price']:.2f}</td>
            <td>€{d['original_price']:.2f}</td>
            <td class="discount">-{d['discount_percent']:.0f}%</td>
            <td class="profit">€{profit:.0f}</td>
            <td><a href="{d['url']}" target="_blank">Bekijk</a></td>
        </tr>
"""
        html += "    </table>"

    html += """
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath
