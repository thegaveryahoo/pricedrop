/**
 * iBood Deep Scanner — Bookmarklet (v2 met paginatie)
 *
 * Gebruik: open https://www.ibood.com/nl/s-nl/all-offers in Chrome,
 * klik dan op de bookmarklet. Het script loopt automatisch door ALLE pagina's,
 * extraheert prijzen, filtert op korting, pusht naar GitHub en triggert rebuild.
 *
 * Eén knop: alles automatisch.
 */
(function() {
  'use strict';

  // === CONFIG ===
  const MIN_DISCOUNT = 40;
  const MIN_PRICE = 30;
  const MIN_EUROS_OFF = 20;
  const GITHUB_REPO = 'thegaveryahoo/pricedrop';
  const SCROLL_DELAY = 600;
  const PAGE_LOAD_DELAY = 2000;
  const CONSECUTIVE_LOW_PAGES = 3; // Stop na X pagina's zonder deals

  // === KLEDING / MAAT FILTER ===
  const BLOCKED_KEYWORDS = [
    'shirt', 't-shirt', 'trui', 'broek', 'jas', 'schoen', 'sneaker',
    'sandaal', 'sok', 'boxer', 'slip', 'jurk', 'rok', 'vest', 'blazer',
    'polo', 'hoodie', 'sweater', 'jeans', 'legging', 'panty', 'bikini',
    'badpak', 'pyjama', 'onderbroek', 'bh', 'lingerie', 'colbert',
    'blouse', 'tuniek', 'cardigan', 'parka', 'regenjas', 'winterjas',
    'sneakers', 'laarzen', 'pumps', 'slippers', 'espadrilles',
  ];
  const SIZE_REGEX = /\b(XXS|XS|S\/M|M\/L|L\/XL|X{0,3}[SML]|3XL|4XL|5XL|\d{2}\/\d{2}|maat\s*\d{2,3})\b/i;

  // === STATE ===
  let allDeals = [];
  let seenUrls = new Set();
  let currentPage = 1;
  let totalPages = 1;

  // === UI ===
  let overlay, statusEl, countEl, listEl, pageEl;

  function createUI() {
    overlay = document.createElement('div');
    overlay.id = 'ibood-scanner';
    overlay.innerHTML = `
      <style>
        #ibood-scanner { position:fixed; top:0; right:0; bottom:0; width:min(420px,100vw);
          background:#f0faf2; z-index:999999; box-shadow:-4px 0 20px rgba(0,0,0,.3);
          font-family:-apple-system,'Segoe UI',system-ui,sans-serif; display:flex; flex-direction:column;
          color:#1a2e1f; }
        #ibs-header { padding:14px 16px; background:linear-gradient(135deg,#22c55e,#ff8c2e); color:#fff; }
        #ibs-header h2 { font-size:18px; margin:0 0 4px; }
        #ibs-status { font-size:12px; opacity:.9; }
        #ibs-page { font-size:11px; opacity:.8; margin-top:2px; }
        #ibs-count { font-size:24px; font-weight:800; }
        #ibs-actions { display:flex; gap:8px; padding:10px 16px; border-bottom:2px solid #c8e0cc; }
        #ibs-actions button { flex:1; padding:10px; border-radius:10px; border:none; font-weight:700;
          font-size:13px; cursor:pointer; }
        .ibs-btn-push { background:#22c55e; color:#fff; }
        .ibs-btn-copy { background:#fff; color:#22c55e; border:2px solid #22c55e!important; }
        .ibs-btn-close { background:#e53e3e; color:#fff; }
        #ibs-list { flex:1; overflow-y:auto; padding:8px 12px; }
        .ibs-deal { background:#fff; border-radius:10px; padding:10px 12px; margin-bottom:8px;
          border:1.5px solid #d4e8d6; }
        .ibs-deal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
        .ibs-deal-name { font-size:13px; font-weight:600; flex:1; line-height:1.3; }
        .ibs-deal-badge { background:#fff0ef; color:#e53e3e; padding:2px 8px; border-radius:6px;
          font-size:14px; font-weight:800; flex-shrink:0; }
        .ibs-deal-prices { font-size:12px; color:#6b8f72; margin-top:4px; }
        .ibs-deal-prices b { color:#1a2e1f; font-size:15px; }
        .ibs-deal-prices s { color:#a0a0a0; }
        .ibs-progress { height:4px; background:#c8e0cc; margin:0; }
        .ibs-progress-bar { height:100%; background:linear-gradient(90deg,#22c55e,#ff8c2e); transition:width .3s; }
      </style>
      <div id="ibs-header">
        <h2>iBood Scanner</h2>
        <div id="ibs-status">Start scannen...</div>
        <div id="ibs-page"></div>
        <div id="ibs-count">0 deals</div>
      </div>
      <div class="ibs-progress"><div class="ibs-progress-bar" id="ibs-progress" style="width:0%"></div></div>
      <div id="ibs-actions">
        <button class="ibs-btn-push" id="ibs-btn-push" disabled>Naar PriceDrop</button>
        <button class="ibs-btn-copy" id="ibs-btn-copy" disabled>Kopieer JSON</button>
        <button class="ibs-btn-close" onclick="document.getElementById('ibood-scanner').remove()">X</button>
      </div>
      <div id="ibs-list"></div>
    `;
    document.body.appendChild(overlay);
    statusEl = document.getElementById('ibs-status');
    countEl = document.getElementById('ibs-count');
    listEl = document.getElementById('ibs-list');
    pageEl = document.getElementById('ibs-page');

    document.getElementById('ibs-btn-push').addEventListener('click', pushToGitHub);
    document.getElementById('ibs-btn-copy').addEventListener('click', copyJSON);
  }

  function setStatus(msg) { statusEl.textContent = msg; }
  function setPage(msg) { pageEl.textContent = msg; }
  function setProgress(pct) { document.getElementById('ibs-progress').style.width = pct + '%'; }

  // === PAGINATION ===
  function detectTotalPages() {
    // Zoek de paginatie-component
    const paginationLinks = document.querySelectorAll(
      'nav[aria-label*="paginat"] a, ' +
      '[class*="pagination"] a, ' +
      '[class*="Pagination"] a, ' +
      'ul[class*="pagination"] li a, ' +
      'a[href*="page="], a[href*="/page/"]'
    );

    let maxPage = 1;
    for (const link of paginationLinks) {
      const text = link.textContent.trim();
      const num = parseInt(text);
      if (!isNaN(num) && num > maxPage) {
        maxPage = num;
      }
      // Check ook href voor page nummer
      const href = link.getAttribute('href') || '';
      const pageMatch = href.match(/page[=\/](\d+)/);
      if (pageMatch) {
        const p = parseInt(pageMatch[1]);
        if (p > maxPage) maxPage = p;
      }
    }

    // Fallback: kijk naar "van X" of "of X" tekst
    const pageText = document.body.innerText;
    const totalMatch = pageText.match(/(?:van|of|\/)\s*(\d+)\s*(?:pagina|pages?)/i);
    if (totalMatch) {
      const t = parseInt(totalMatch[1]);
      if (t > maxPage) maxPage = t;
    }

    return maxPage;
  }

  function buildPageUrl(pageNum) {
    const url = new URL(window.location.href);
    url.searchParams.set('page', pageNum);
    // Sorteer op korting (hoogste eerst) zodat we vroeg kunnen stoppen
    url.searchParams.set('sort', 'discount');
    url.searchParams.set('order', 'desc');
    return url.toString();
  }

  async function goToPage(pageNum) {
    // Methode 1: URL parameter
    const url = buildPageUrl(pageNum);

    // Gebruik fetch om de pagina-content op te halen zonder te navigeren
    // Dit is sneller en behoudt onze UI overlay
    try {
      const resp = await fetch(url, {
        credentials: 'include',
        headers: { 'Accept': 'text/html' }
      });
      if (resp.ok) {
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        return doc;
      }
    } catch (e) {
      console.log('[iBood Scanner] Fetch failed, navigating...', e);
    }

    // Methode 2: Klik op de paginatie-link
    const nextBtn = findPageLink(pageNum);
    if (nextBtn) {
      nextBtn.click();
      await new Promise(r => setTimeout(r, PAGE_LOAD_DELAY));
      return document;
    }

    // Methode 3: Direct navigeren (verliest overlay, maar werkt altijd)
    return null;
  }

  function findPageLink(pageNum) {
    const links = document.querySelectorAll(
      'nav[aria-label*="paginat"] a, ' +
      '[class*="pagination"] a, [class*="Pagination"] a, ' +
      'a[href*="page="], a[href*="/page/"]'
    );
    for (const link of links) {
      if (link.textContent.trim() === String(pageNum)) return link;
      const href = link.getAttribute('href') || '';
      if (href.includes(`page=${pageNum}`) || href.includes(`/page/${pageNum}`)) return link;
    }
    // "Volgende" / "Next" knop
    const nextBtns = document.querySelectorAll(
      '[class*="next"], [aria-label*="next"], [aria-label*="volgende"], ' +
      'a[rel="next"], button[class*="next"]'
    );
    for (const btn of nextBtns) {
      if (!btn.disabled && !btn.classList.contains('disabled')) return btn;
    }
    return null;
  }

  // === SCROLL binnen pagina ===
  async function scrollPage(doc) {
    if (doc !== document) return; // Skip scroll voor geparsede docs
    let lastHeight = 0;
    let sameCount = 0;
    for (let i = 0; i < 15; i++) {
      window.scrollTo(0, document.body.scrollHeight);
      await new Promise(r => setTimeout(r, SCROLL_DELAY));
      const newHeight = document.body.scrollHeight;
      if (newHeight === lastHeight) {
        sameCount++;
        if (sameCount >= 2) break;
      } else {
        sameCount = 0;
      }
      lastHeight = newHeight;
    }
    window.scrollTo(0, 0);
  }

  // === EXTRACT DEALS ===
  function extractDealsFromDoc(doc) {
    const deals = [];

    // Strategie 1: product cards
    const cards = doc.querySelectorAll(
      '[class*="product-card"], [class*="ProductCard"], [class*="offer-card"], ' +
      '[class*="OfferCard"], [data-test*="product"], [class*="product-item"], ' +
      '[class*="productCard"], [class*="deal-card"], [class*="DealCard"]'
    );

    for (const card of cards) {
      const deal = parseCard(card);
      if (deal && !seenUrls.has(deal.url)) {
        seenUrls.add(deal.url);
        deals.push(deal);
      }
    }

    // Strategie 2: links met prijzen
    const links = doc.querySelectorAll('a[href*="/nl/s-nl/"], a[href*="/nl/product/"], a[href*="/offer/"]');
    for (const link of links) {
      const deal = parseLink(link);
      if (deal && !seenUrls.has(deal.url)) {
        seenUrls.add(deal.url);
        deals.push(deal);
      }
    }

    // Strategie 3: generieke elementen
    const allEls = doc.querySelectorAll('article, [class*="item"], [class*="tile"], [class*="grid"] > div');
    for (const el of allEls) {
      const deal = parseGeneric(el);
      if (deal && !seenUrls.has(deal.url)) {
        seenUrls.add(deal.url);
        deals.push(deal);
      }
    }

    return deals;
  }

  function parsePrice(text) {
    if (!text) return null;
    text = text.replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.');
    const n = parseFloat(text);
    return (n && n > 0 && n < 50000) ? n : null;
  }

  function findPricesInText(text) {
    const matches = text.match(/€\s*[\d.,]+/g) || [];
    return matches.map(m => parsePrice(m)).filter(p => p && p > 0.5);
  }

  function parseCard(card) {
    try {
      const nameEl = card.querySelector('[class*="title"], [class*="name"], [class*="Title"], [class*="Name"], h2, h3, h4, strong');
      const name = nameEl ? nameEl.textContent.trim() : null;
      if (!name || name.length < 5) return null;

      const linkEl = card.tagName === 'A' ? card : card.querySelector('a');
      let url = linkEl ? linkEl.href || linkEl.getAttribute('href') : null;
      if (!url) return null;
      if (url.startsWith('/')) url = 'https://www.ibood.com' + url;

      const strikeEl = card.querySelector('s, del, [class*="old"], [class*="retail"], [class*="was"], [class*="advice"], [class*="from"], [class*="Original"], [class*="crossed"]');
      let origPrice = strikeEl ? parsePrice(strikeEl.textContent) : null;

      const priceEls = card.querySelectorAll('[class*="price"], [class*="Price"], [class*="amount"]');
      let curPrice = null;
      for (const el of priceEls) {
        const p = parsePrice(el.textContent);
        if (p && (!origPrice || p < origPrice)) {
          curPrice = p;
          break;
        }
      }

      if (!curPrice || !origPrice) {
        const prices = findPricesInText(card.textContent);
        if (prices.length >= 2) {
          prices.sort((a, b) => a - b);
          if (!curPrice) curPrice = prices[0];
          if (!origPrice) origPrice = prices[prices.length - 1];
        }
      }

      return buildDeal(name, url, curPrice, origPrice);
    } catch(e) { return null; }
  }

  function parseLink(link) {
    try {
      const container = link.closest('[class*="card"], [class*="Card"], article, [class*="item"]') || link;
      const text = container.textContent.trim();
      if (text.length < 10) return null;

      const nameEl = container.querySelector('[class*="title"], [class*="name"], h2, h3, h4, strong');
      const name = (nameEl ? nameEl.textContent.trim() : text.split('\n')[0].trim()).substring(0, 200);
      if (name.length < 5) return null;

      let url = link.href || link.getAttribute('href');
      if (!url) return null;
      if (url.startsWith('/')) url = 'https://www.ibood.com' + url;

      const prices = findPricesInText(container.textContent);
      if (prices.length < 2) return null;
      prices.sort((a, b) => a - b);

      return buildDeal(name, url, prices[0], prices[prices.length - 1]);
    } catch(e) { return null; }
  }

  function parseGeneric(el) {
    try {
      const link = el.querySelector('a[href*="/nl/"], a[href*="/offer/"], a[href*="/product/"]');
      if (!link) return null;
      const name = (el.querySelector('h2,h3,h4,strong,[class*="title"],[class*="Title"]') || link).textContent.trim().substring(0, 200);
      if (name.length < 5) return null;

      let url = link.href || link.getAttribute('href');
      if (!url) return null;
      if (url.startsWith('/')) url = 'https://www.ibood.com' + url;

      const prices = findPricesInText(el.textContent);
      if (prices.length < 2) return null;
      prices.sort((a, b) => a - b);

      return buildDeal(name, url, prices[0], prices[prices.length - 1]);
    } catch(e) { return null; }
  }

  function isClothingOrSized(name) {
    const lower = name.toLowerCase();
    for (const kw of BLOCKED_KEYWORDS) {
      if (lower.includes(kw)) return true;
    }
    if (SIZE_REGEX.test(name)) return true;
    return false;
  }

  function buildDeal(name, url, curPrice, origPrice) {
    if (!curPrice || !origPrice || origPrice <= curPrice || curPrice <= 0) return null;
    if (origPrice / curPrice > 50) return null;

    const discount = ((origPrice - curPrice) / origPrice) * 100;
    const eurosOff = origPrice - curPrice;

    if (discount < MIN_DISCOUNT) return null;
    if (origPrice < MIN_PRICE) return null;
    if (eurosOff < MIN_EUROS_OFF) return null;

    name = name.replace(/€\s*[\d.,]+/g, '').replace(/\s+/g, ' ').trim();

    // Filter kleding en maat-specifieke items
    if (isClothingOrSized(name)) return null;

    return {
      product_name: name.substring(0, 200),
      shop: 'iBood',
      current_price: Math.round(curPrice * 100) / 100,
      original_price: Math.round(origPrice * 100) / 100,
      discount_percent: Math.round(discount * 10) / 10,
      url: url,
      country: 'NL',
      country_flag: '\u{1F1F3}\u{1F1F1}',
      found_at: new Date().toISOString(),
      _source: 'ibood_bookmarklet',
    };
  }

  // === DISPLAY ===
  function displayDeals() {
    countEl.textContent = `${allDeals.length} deals gevonden!`;
    listEl.innerHTML = allDeals
      .sort((a, b) => b.discount_percent - a.discount_percent)
      .slice(0, 100) // Toon max 100 in UI (alle worden wel gepusht)
      .map(d => `
        <a href="${d.url}" target="_blank" class="ibs-deal" style="display:block;text-decoration:none;color:inherit">
          <div class="ibs-deal-head">
            <span class="ibs-deal-name">${d.product_name}</span>
            <span class="ibs-deal-badge">-${d.discount_percent.toFixed(0)}%</span>
          </div>
          <div class="ibs-deal-prices">
            <b>\u20AC${d.current_price.toFixed(2)}</b>
            <s>\u20AC${d.original_price.toFixed(0)}</s>
            &middot; \u20AC${(d.original_price - d.current_price).toFixed(0)} korting
          </div>
        </a>
      `).join('');

    if (allDeals.length > 100) {
      listEl.innerHTML += `<div style="text-align:center;padding:12px;color:#6b8f72;font-size:12px">
        En nog ${allDeals.length - 100} meer... (alle worden gepusht)
      </div>`;
    }
  }

  // === GITHUB PUSH ===
  async function getFileSha(token, path) {
    try {
      const resp = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/${path}`, {
        headers: { 'Authorization': `token ${token}` }
      });
      if (resp.ok) return (await resp.json()).sha;
    } catch(e) {}
    return undefined;
  }

  async function pushToGitHub() {
    const btn = document.getElementById('ibs-btn-push');
    btn.textContent = 'Pushen...';
    btn.disabled = true;

    if (!allDeals.length) {
      alert('Geen deals om te pushen');
      btn.disabled = false;
      btn.textContent = 'Naar PriceDrop';
      return;
    }

    const token = localStorage.getItem('pricedrop_github_token');
    if (!token) {
      setStatus('Geen GitHub token! Voer in console uit: localStorage.setItem("pricedrop_github_token", "ghp_...")');
      copyJSON();
      btn.textContent = 'Gekopieerd (geen token)';
      return;
    }

    try {
      // Stap 1: Push ibood_deals.json
      const content = btoa(unescape(encodeURIComponent(JSON.stringify(allDeals, null, 2))));
      const sha = await getFileSha(token, 'ibood_deals.json');

      const putResp = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/contents/ibood_deals.json`, {
        method: 'PUT',
        headers: {
          'Authorization': `token ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `iBood scan: ${allDeals.length} deals [${new Date().toLocaleString('nl-NL')}]`,
          content: content,
          sha: sha,
        })
      });

      if (!putResp.ok) {
        throw new Error(`GitHub PUT failed: ${putResp.status}`);
      }

      // Stap 2: Trigger GitHub Actions workflow om webapp te rebuilden
      setStatus('Deals gepusht! Webapp rebuild triggeren...');
      const dispatchResp = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/scan.yml/dispatches`, {
        method: 'POST',
        headers: {
          'Authorization': `token ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'master' })
      });

      if (dispatchResp.ok || dispatchResp.status === 204) {
        btn.textContent = 'Gepusht + Rebuild!';
        btn.style.background = '#22c55e';
        setStatus(`${allDeals.length} iBood deals gepusht! Webapp wordt opnieuw gebouwd (~5 min).`);
      } else {
        btn.textContent = 'Gepusht!';
        btn.style.background = '#22c55e';
        setStatus(`${allDeals.length} deals gepusht. Workflow trigger mislukt (${dispatchResp.status}), maar data staat op GitHub.`);
      }
    } catch(e) {
      btn.textContent = 'Fout!';
      setStatus('Fout: ' + e.message);
      console.error('[iBood Scanner]', e);
    }
  }

  function copyJSON() {
    if (!allDeals.length) { alert('Geen deals'); return; }
    const json = JSON.stringify(allDeals, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      const btn = document.getElementById('ibs-btn-copy');
      btn.textContent = 'Gekopieerd!';
      setTimeout(() => btn.textContent = 'Kopieer JSON', 2000);
    });
  }

  // === MAIN SCAN LOOP ===
  async function run() {
    createUI();

    // Stap 1: Detecteer aantal pagina's
    setStatus('Paginatie detecteren...');
    await new Promise(r => setTimeout(r, 1500));

    totalPages = detectTotalPages();
    setPage(`Pagina 1 van ${totalPages}`);
    setStatus(`${totalPages} pagina's gevonden. Scannen...`);

    // Stap 2: Scan huidige pagina (pagina 1)
    await scrollPage(document);
    let pageDeals = extractDealsFromDoc(document);
    allDeals.push(...pageDeals);
    displayDeals();
    setProgress(Math.round((1 / totalPages) * 100));

    // Stap 3: Loop door alle volgende pagina's (stop vroeg als korting te laag wordt)
    let consecutiveEmptyPages = 0;

    for (let page = 2; page <= totalPages; page++) {
      currentPage = page;
      setPage(`Pagina ${page} van ${totalPages}`);
      setStatus(`Pagina ${page}/${totalPages} laden... (${allDeals.length} deals tot nu toe)`);

      const doc = await goToPage(page);
      if (!doc) {
        setStatus(`Pagina ${page}: directe navigatie nodig...`);
        const nextBtn = findPageLink(page);
        if (nextBtn) {
          sessionStorage.setItem('ibood_scanner_deals', JSON.stringify(allDeals));
          sessionStorage.setItem('ibood_scanner_seen', JSON.stringify([...seenUrls]));
          sessionStorage.setItem('ibood_scanner_page', String(page));
          sessionStorage.setItem('ibood_scanner_total', String(totalPages));
          nextBtn.click();
          return;
        }
        setStatus(`Pagina ${page} overgeslagen (niet bereikbaar)`);
        continue;
      }

      if (doc === document) {
        await scrollPage(doc);
      }

      pageDeals = extractDealsFromDoc(doc);
      allDeals.push(...pageDeals);
      displayDeals();

      setProgress(Math.round((page / totalPages) * 100));
      setStatus(`Pagina ${page}/${totalPages}: ${pageDeals.length} deals gevonden (totaal: ${allDeals.length})`);

      // Early-stop: als X pagina's achter elkaar 0 deals opleveren, stoppen
      if (pageDeals.length === 0) {
        consecutiveEmptyPages++;
        if (consecutiveEmptyPages >= CONSECUTIVE_LOW_PAGES) {
          setStatus(`Gestopt na ${page} pagina's — ${CONSECUTIVE_LOW_PAGES} pagina's zonder deals. Totaal: ${allDeals.length} deals.`);
          break;
        }
      } else {
        consecutiveEmptyPages = 0;
      }

      await new Promise(r => setTimeout(r, 500));
    }

    // Stap 4: Klaar!
    setProgress(100);
    setStatus(`Klaar! ${totalPages} pagina's gescand, ${allDeals.length} deals gevonden.`);

    // Knoppen activeren
    document.getElementById('ibs-btn-push').disabled = false;
    document.getElementById('ibs-btn-copy').disabled = false;

    // Auto-push als token beschikbaar is
    const token = localStorage.getItem('pricedrop_github_token');
    if (token && allDeals.length > 0) {
      setStatus(`${allDeals.length} deals gevonden! Automatisch pushen naar PriceDrop...`);
      await pushToGitHub();
    }
  }

  // === HERSTEL na pagina-navigatie ===
  function restoreState() {
    const savedDeals = sessionStorage.getItem('ibood_scanner_deals');
    if (savedDeals) {
      try {
        allDeals = JSON.parse(savedDeals);
        const savedSeen = JSON.parse(sessionStorage.getItem('ibood_scanner_seen') || '[]');
        seenUrls = new Set(savedSeen);
        currentPage = parseInt(sessionStorage.getItem('ibood_scanner_page') || '1');
        totalPages = parseInt(sessionStorage.getItem('ibood_scanner_total') || '1');

        // Verwijder opgeslagen state
        sessionStorage.removeItem('ibood_scanner_deals');
        sessionStorage.removeItem('ibood_scanner_seen');
        sessionStorage.removeItem('ibood_scanner_page');
        sessionStorage.removeItem('ibood_scanner_total');

        return true;
      } catch(e) {}
    }
    return false;
  }

  // === START ===
  if (!window.location.hostname.includes('ibood')) {
    if (confirm('Dit script werkt op ibood.com. Wil je daarheen navigeren?')) {
      window.location.href = 'https://www.ibood.com/nl/s-nl/all-offers?sort=discount&order=desc';
    }
    return;
  }

  // Check of we herstellen na een pagina-navigatie
  if (restoreState()) {
    createUI();
    displayDeals();
    setPage(`Pagina ${currentPage} van ${totalPages} (hervat)`);
    setStatus(`Hervat scan vanaf pagina ${currentPage}...`);

    // Ga verder waar we gebleven waren
    (async () => {
      await scrollPage(document);
      let pageDeals = extractDealsFromDoc(document);
      allDeals.push(...pageDeals);
      displayDeals();

      for (let page = currentPage + 1; page <= totalPages; page++) {
        setPage(`Pagina ${page} van ${totalPages}`);
        setStatus(`Pagina ${page}/${totalPages} laden... (${allDeals.length} deals)`);

        const doc = await goToPage(page);
        if (!doc) {
          const nextBtn = findPageLink(page);
          if (nextBtn) {
            sessionStorage.setItem('ibood_scanner_deals', JSON.stringify(allDeals));
            sessionStorage.setItem('ibood_scanner_seen', JSON.stringify([...seenUrls]));
            sessionStorage.setItem('ibood_scanner_page', String(page));
            sessionStorage.setItem('ibood_scanner_total', String(totalPages));
            nextBtn.click();
            return;
          }
          continue;
        }

        if (doc === document) await scrollPage(doc);
        pageDeals = extractDealsFromDoc(doc);
        allDeals.push(...pageDeals);
        displayDeals();
        setProgress(Math.round((page / totalPages) * 100));
        await new Promise(r => setTimeout(r, 500));
      }

      setProgress(100);
      setStatus(`Klaar! ${totalPages} pagina's gescand, ${allDeals.length} deals.`);
      document.getElementById('ibs-btn-push').disabled = false;
      document.getElementById('ibs-btn-copy').disabled = false;

      const token = localStorage.getItem('pricedrop_github_token');
      if (token && allDeals.length > 0) {
        await pushToGitHub();
      }
    })();
  } else {
    run();
  }
})();
