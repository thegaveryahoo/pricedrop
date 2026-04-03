"""
PriceDrop Scanner — Webapp
Draait een lokale webserver met een dashboard om deals te bekijken,
de drempel in te stellen, en scans te starten.

Start: python webapp.py
Open: http://localhost:8050
"""

import sys
import os
import json
import sqlite3
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH
from database import get_recent_deals, init_db

PORT = 8050
scan_status = {"running": False, "last_scan": None, "message": ""}


def get_all_deals_from_db(min_discount=0, hours=168):
    """Haal alle deals uit de database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM deals
        WHERE discount_percent >= ? AND found_at >= datetime('now', ?)
        ORDER BY discount_percent DESC
    """, (min_discount, f"-{hours} hours"))
    deals = [dict(row) for row in c.fetchall()]
    conn.close()
    return deals


def run_scan_background(min_discount):
    """Start een scan op de achtergrond."""
    global scan_status
    scan_status["running"] = True
    scan_status["message"] = "Bezig met scannen..."

    try:
        from scanner import run_scan
        import config
        config.MIN_DISCOUNT_PERCENT = min_discount
        all_deals, new_deals = run_scan()
        scan_status["message"] = f"Klaar! {len(all_deals)} deals gevonden ({len(new_deals)} nieuw)"
        scan_status["last_scan"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    except Exception as e:
        scan_status["message"] = f"Fout: {e}"
    finally:
        scan_status["running"] = False


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PriceDrop Scanner</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }

        .header {
            background: linear-gradient(135deg, #1a1a3e 0%, #0f0f2a 100%);
            padding: 24px 32px;
            border-bottom: 1px solid #2a2a4a;
            display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
        }
        .header h1 { color: #00d4ff; font-size: 24px; font-weight: 700; }
        .header .subtitle { color: #888; font-size: 13px; }

        .controls {
            display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
        }
        .control-group { display: flex; align-items: center; gap: 8px; }
        .control-group label { color: #aaa; font-size: 13px; white-space: nowrap; }

        .slider-container {
            display: flex; align-items: center; gap: 10px;
        }
        input[type="range"] {
            -webkit-appearance: none; width: 180px; height: 6px; border-radius: 3px;
            background: #333; outline: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%;
            background: #00d4ff; cursor: pointer;
        }
        .threshold-value {
            color: #00d4ff; font-weight: 700; font-size: 18px; min-width: 50px;
        }

        .btn {
            padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer;
            font-size: 14px; font-weight: 600; transition: all 0.2s;
        }
        .btn-primary { background: #00d4ff; color: #000; }
        .btn-primary:hover { background: #33dfff; transform: translateY(-1px); }
        .btn-primary:disabled { background: #555; color: #888; cursor: not-allowed; transform: none; }

        .status-bar {
            background: #16163a; padding: 10px 32px; font-size: 13px; color: #888;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid #222;
        }
        .status-bar .scanning { color: #ffaa00; }
        .status-bar .success { color: #00ff88; }

        .content { padding: 24px 32px; }

        .stats {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px;
        }
        .stat-card {
            background: #16163a; border: 1px solid #2a2a4a; border-radius: 10px;
            padding: 20px; text-align: center;
        }
        .stat-card .value { font-size: 32px; font-weight: 700; color: #00d4ff; }
        .stat-card .label { color: #888; font-size: 13px; margin-top: 4px; }
        .stat-card.hot .value { color: #ff4444; }
        .stat-card.profit .value { color: #00ff88; }

        table { width: 100%; border-collapse: collapse; }
        thead th {
            background: #16163a; color: #00d4ff; padding: 12px 10px; text-align: left;
            font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
            position: sticky; top: 0; cursor: pointer; user-select: none;
            border-bottom: 2px solid #2a2a4a;
        }
        thead th:hover { color: #fff; }
        thead th.sorted::after { content: ' ▼'; }
        thead th.sorted-asc::after { content: ' ▲'; }

        tbody tr { transition: background 0.15s; }
        tbody tr:hover { background: #1a1a3e; }
        tbody td { padding: 12px 10px; border-bottom: 1px solid #1e1e3a; font-size: 14px; }

        .discount-badge {
            display: inline-block; padding: 3px 10px; border-radius: 12px;
            font-weight: 700; font-size: 14px;
        }
        .discount-hot { background: rgba(255,68,68,0.15); color: #ff4444; }
        .discount-warm { background: rgba(255,170,0,0.15); color: #ffaa00; }
        .discount-cool { background: rgba(0,212,255,0.15); color: #00d4ff; }

        .profit-positive { color: #00ff88; font-weight: 600; }
        .profit-negative { color: #ff4444; font-weight: 600; }

        .shop-badge {
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 12px; font-weight: 600;
            background: #1e1e3e; border: 1px solid #333;
        }

        .link-btn {
            display: inline-block; padding: 4px 12px; border-radius: 4px;
            background: #00d4ff20; color: #00d4ff; text-decoration: none;
            font-size: 13px; font-weight: 600; transition: all 0.2s;
        }
        .link-btn:hover { background: #00d4ff40; }

        .empty { text-align: center; padding: 60px; color: #555; }
        .empty .icon { font-size: 48px; margin-bottom: 16px; }

        .filter-chips {
            display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;
        }
        .chip {
            padding: 6px 14px; border-radius: 20px; font-size: 13px;
            cursor: pointer; border: 1px solid #333; background: transparent; color: #aaa;
            transition: all 0.2s;
        }
        .chip:hover { border-color: #00d4ff; color: #00d4ff; }
        .chip.active { background: #00d4ff20; border-color: #00d4ff; color: #00d4ff; }

        @media (max-width: 768px) {
            .header { padding: 16px; }
            .content { padding: 16px; }
            .stats { grid-template-columns: repeat(2, 1fr); }
            table { font-size: 12px; }
            input[type="range"] { width: 120px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>PriceDrop Scanner</h1>
            <div class="subtitle">Automatische prijsfout-detectie voor NL & DE webshops</div>
        </div>
        <div class="controls">
            <div class="control-group">
                <label>Min. korting:</label>
                <div class="slider-container">
                    <input type="range" id="threshold" min="10" max="90" step="5" value="40">
                    <span class="threshold-value" id="thresholdValue">40%</span>
                </div>
            </div>
            <div class="control-group">
                <label>Periode:</label>
                <select id="period" style="background:#1e1e3e;color:#e0e0e0;border:1px solid #333;padding:6px 10px;border-radius:6px;">
                    <option value="24">24 uur</option>
                    <option value="48">48 uur</option>
                    <option value="168" selected>7 dagen</option>
                    <option value="720">30 dagen</option>
                </select>
            </div>
            <button class="btn btn-primary" id="scanBtn" onclick="startScan()">Scan Nu</button>
        </div>
    </div>

    <div class="status-bar" id="statusBar">
        <span id="statusText">Gereed</span>
        <span id="lastScan">-</span>
    </div>

    <div class="content">
        <div class="stats" id="statsContainer"></div>

        <div class="filter-chips" id="shopFilters"></div>

        <div id="dealsTable"></div>
    </div>

    <script>
        let allDeals = [];
        let activeShops = new Set();
        let sortCol = 'discount_percent';
        let sortAsc = false;

        const threshold = document.getElementById('threshold');
        const thresholdValue = document.getElementById('thresholdValue');
        const period = document.getElementById('period');

        threshold.addEventListener('input', () => {
            thresholdValue.textContent = threshold.value + '%';
            localStorage.setItem('pd_threshold', threshold.value);
            loadDeals();
        });
        period.addEventListener('change', () => {
            localStorage.setItem('pd_period', period.value);
            loadDeals();
        });

        // Herstel opgeslagen instellingen
        const savedThreshold = localStorage.getItem('pd_threshold');
        const savedPeriod = localStorage.getItem('pd_period');
        if (savedThreshold) { threshold.value = savedThreshold; thresholdValue.textContent = savedThreshold + '%'; }
        if (savedPeriod) { period.value = savedPeriod; }

        async function loadDeals() {
            const res = await fetch(`/api/deals?min_discount=${threshold.value}&hours=${period.value}`);
            allDeals = await res.json();
            updateShopFilters();
            renderTable();
            renderStats();
        }

        function updateShopFilters() {
            const shops = [...new Set(allDeals.map(d => d.shop))].sort();
            if (activeShops.size === 0) shops.forEach(s => activeShops.add(s));
            const container = document.getElementById('shopFilters');
            container.innerHTML = shops.map(s =>
                `<span class="chip ${activeShops.has(s) ? 'active' : ''}" onclick="toggleShop('${s}')">${s}</span>`
            ).join('');
        }

        function toggleShop(shop) {
            if (activeShops.has(shop)) activeShops.delete(shop);
            else activeShops.add(shop);
            updateShopFilters();
            renderTable();
            renderStats();
        }

        function renderStats() {
            const deals = getFilteredDeals();
            const totalDeals = deals.length;
            const bestDiscount = deals.length > 0 ? Math.max(...deals.map(d => d.discount_percent)) : 0;
            const totalProfit = deals.reduce((sum, d) => sum + Math.max(0, d.original_price * 0.75 - d.current_price), 0);
            const shops = new Set(deals.map(d => d.shop)).size;

            document.getElementById('statsContainer').innerHTML = `
                <div class="stat-card"><div class="value">${totalDeals}</div><div class="label">Deals gevonden</div></div>
                <div class="stat-card hot"><div class="value">-${bestDiscount.toFixed(0)}%</div><div class="label">Hoogste korting</div></div>
                <div class="stat-card profit"><div class="value">&euro;${totalProfit.toFixed(0)}</div><div class="label">Totale potentiele winst</div></div>
                <div class="stat-card"><div class="value">${shops}</div><div class="label">Webshops</div></div>
            `;
        }

        function getFilteredDeals() {
            return allDeals.filter(d => activeShops.has(d.shop));
        }

        function sortDeals(col) {
            if (sortCol === col) sortAsc = !sortAsc;
            else { sortCol = col; sortAsc = false; }
            renderTable();
        }

        function renderTable() {
            let deals = getFilteredDeals();

            // Sorteer
            deals.sort((a, b) => {
                let va = a[sortCol], vb = b[sortCol];
                if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
                return sortAsc ? va - vb : vb - va;
            });

            if (deals.length === 0) {
                document.getElementById('dealsTable').innerHTML = `
                    <div class="empty">
                        <div class="icon">&#128269;</div>
                        <p>Geen deals gevonden met deze filters.</p>
                        <p style="margin-top:8px;font-size:13px">Verlaag de kortingsdrempel of vergroot de periode.</p>
                    </div>`;
                return;
            }

            const thClass = (col) => sortCol === col ? (sortAsc ? 'sorted-asc' : 'sorted') : '';

            let html = `<table>
                <thead><tr>
                    <th class="${thClass('product_name')}" onclick="sortDeals('product_name')">Product</th>
                    <th class="${thClass('shop')}" onclick="sortDeals('shop')">Shop</th>
                    <th class="${thClass('current_price')}" onclick="sortDeals('current_price')">Prijs</th>
                    <th class="${thClass('original_price')}" onclick="sortDeals('original_price')">Was</th>
                    <th class="${thClass('discount_percent')}" onclick="sortDeals('discount_percent')">Korting</th>
                    <th>~Winst</th>
                    <th>Gevonden</th>
                    <th></th>
                </tr></thead><tbody>`;

            for (const d of deals) {
                const profit = d.original_price * 0.75 - d.current_price;
                const discClass = d.discount_percent >= 60 ? 'discount-hot' : d.discount_percent >= 40 ? 'discount-warm' : 'discount-cool';
                const profitClass = profit > 0 ? 'profit-positive' : 'profit-negative';
                const time = d.found_at ? new Date(d.found_at).toLocaleString('nl-NL', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '-';

                html += `<tr>
                    <td title="${d.product_name}">${d.product_name.substring(0,55)}${d.product_name.length > 55 ? '...' : ''}</td>
                    <td><span class="shop-badge">${d.shop}</span></td>
                    <td style="font-weight:700">&euro;${d.current_price.toFixed(2)}</td>
                    <td style="text-decoration:line-through;color:#888">&euro;${d.original_price.toFixed(2)}</td>
                    <td><span class="discount-badge ${discClass}">-${d.discount_percent.toFixed(0)}%</span></td>
                    <td class="${profitClass}">&euro;${profit.toFixed(0)}</td>
                    <td style="color:#888;font-size:12px">${time}</td>
                    <td><a href="${d.url}" target="_blank" class="link-btn">Bekijk</a></td>
                </tr>`;
            }

            html += '</tbody></table>';
            document.getElementById('dealsTable').innerHTML = html;
        }

        async function startScan() {
            const btn = document.getElementById('scanBtn');
            btn.disabled = true;
            btn.textContent = 'Scanning...';
            document.getElementById('statusText').innerHTML = '<span class="scanning">Bezig met scannen van alle webshops...</span>';

            await fetch(`/api/scan?min_discount=${threshold.value}`, {method: 'POST'});

            // Poll status
            const poll = setInterval(async () => {
                const res = await fetch('/api/status');
                const status = await res.json();
                document.getElementById('statusText').innerHTML = status.running
                    ? `<span class="scanning">${status.message}</span>`
                    : `<span class="success">${status.message}</span>`;
                if (status.last_scan) document.getElementById('lastScan').textContent = 'Laatste scan: ' + status.last_scan;

                if (!status.running) {
                    clearInterval(poll);
                    btn.disabled = false;
                    btn.textContent = 'Scan Nu';
                    loadDeals();
                }
            }, 3000);
        }

        async function checkStatus() {
            const res = await fetch('/api/status');
            const status = await res.json();
            if (status.last_scan) document.getElementById('lastScan').textContent = 'Laatste scan: ' + status.last_scan;
        }

        // Start
        loadDeals();
        checkStatus();
        // Auto-refresh elke 5 minuten
        setInterval(loadDeals, 5 * 60 * 1000);
    </script>
</body>
</html>"""


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Stille server

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

        elif parsed.path == "/api/deals":
            params = parse_qs(parsed.query)
            min_discount = float(params.get("min_discount", [0])[0])
            hours = int(params.get("hours", [168])[0])
            deals = get_all_deals_from_db(min_discount, hours)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(deals).encode("utf-8"))

        elif parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(scan_status).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/scan":
            if scan_status["running"]:
                self.send_response(409)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Scan al bezig"}).encode("utf-8"))
                return

            params = parse_qs(parsed.query)
            min_discount = float(params.get("min_discount", [60])[0])
            thread = threading.Thread(target=run_scan_background, args=(min_discount,), daemon=True)
            thread.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def main():
    init_db()
    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)
    print(f"\n  PriceDrop Scanner webapp gestart!")
    print(f"  Open: http://localhost:{PORT}")
    print(f"  Druk Ctrl+C om te stoppen.\n")

    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer gestopt.")
        server.server_close()


if __name__ == "__main__":
    main()
