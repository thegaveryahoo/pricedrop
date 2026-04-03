// PriceDrop Service Worker — v1
// Cachet NOOIT de HTML — pull-to-refresh haalt altijd de nieuwste versie op.
// Cachet alleen statische assets (manifest, icoon).

const CACHE_NAME = 'pricedrop-v1';
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

  // NOOIT HTML cachen — altijd netwerk (zorgt dat pull-to-refresh werkt)
  if (url.pathname.endsWith('.html')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Statische assets: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
