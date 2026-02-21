// Minimal safe service worker to replace older workers and clear old caches.
const CACHE_NAME = 'plaidbridge-static-v1'; // bump on future updates
const ASSETS = [
  '/static/js/app.js',
  '/static/css/app.css',
  '/static/android-chrome-192x192.png',
  '/static/android-chrome-512x512.png',
  '/static/site.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.map((n) => (n !== CACHE_NAME ? caches.delete(n) : null)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).catch(() => {
        // Optional: return an offline placeholder page/image instead
        return new Response('', { status: 404 });
      });
    })
  );
});