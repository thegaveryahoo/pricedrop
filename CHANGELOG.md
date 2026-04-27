# PriceDrop Changelog

## 2026-04-27 · v4.0.2 — Threading-bugfix (scans deden het niet)

**Probleem:** v4.0.1 introduceerde threading met context-recovery, maar drie bugs zorgden voor cascadefalen:
1. Timeout-threads bleven doorlopen met oude context → crashed als context hersteld werd
2. `context_crashed.is_set()` liet volgende scrapers stilletjes overslaan
3. Eén crashende scraper → alle 13 andere scrapers faalden → 0 deals

**Fix (scanner.py):**
- Threading volledig verwijderd → sequentiële uitvoering met `try/except`
- Elke scraper draait direct in de hoofdloop
- Bij crash: context herstellen en door naar volgende scraper
- Code 40 regels korter, geen locks, geen race conditions

**Bestanden gewijzigd:**
- `scanner.py` — threading verwijderd, sequentiële scrapers met foutafhandeling

## 2026-04-27 · v4.0.1 — Scanner-veerkracht fix

**Probleem:** Scheduled scans (08:00, 14:00, 20:00 via GitHub Actions) sloegen vaak over. De handmatige SCAN-knop werkte soms wel, soms niet. Oorzaak: als één scraper crashte (Target closed door anti-bot), werd de Playwright context corrupt → alle volgende 13 scrapers faalden stilletjes → 0 deals → "geen scan".

**Fix (scanner.py):**

1. **Per-scraper timeout (120s):** Elke scraper draait nu in een aparte thread met timeout. Vastlopende scrapers (anti-bot wall, trage CDN) worden na 120s geskipt in plaats van de hele pipeline te blokkeren.

2. **Context-recovery na crash:** Als een scraper een Playwright-fout gooit (Target/Page closed), wordt de corrupte browser context gesloten en een verse context + pagina's aangemaakt. Als context-recovery faalt, wordt de hele Chromium browser herstart.

**Bestanden gewijzigd:**
- `scanner.py` — context-recovery + timeout per scraper
- `.github/workflows/scan.yml` — timeout verhoogd van 20→45 minuten (14 scrapers × 120s max)
