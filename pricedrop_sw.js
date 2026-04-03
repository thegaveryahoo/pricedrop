// PriceDrop Service Worker — v2
// Cachet NOOIT de HTML — pull-to-refresh haalt altijd de nieuwste versie op.
// Cachet alleen statische assets (manifest, icoon).

const CACHE_NAME = 'pricedrop-v2';
const STATIC_ASSETS = [
  '/local/pricedrop_manifest.json',
  '/local/pricedrop_icon.svg',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // NOOIT HTML cachen — altijd netwerk met cache-bust
  if (url.pathname.endsWith('.html') || url.pathname.endsWith('/') || url.pathname === '/pricedrop' || url.pathname === '/pricedrop/') {
    event.respondWith(
      fetch(event.request.url + (event.request.url.includes('?') ? '&' : '?') + '_cb=' + Date.now(), {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache' }
      }).catch(() => fetch(event.request))
    );
    return;
  }

  // Statische assets: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
