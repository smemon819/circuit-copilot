const CACHE_NAME = 'circuit-copilot-v3-cache';
const ASSETS_TO_CACHE = [
    '/',
    '/app',
    '/static/index.html',
    '/static/manifest.json',
    '/static/icon.svg'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS_TO_CACHE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            );
        })
    );
});

self.addEventListener('fetch', event => {
    // Only intercept GET requests, skip API calls
    if (event.request.method !== 'GET' || event.request.url.includes('/api/')) return;

    event.respondWith(
        caches.match(event.request)
            .then(cached => cached || fetch(event.request))
            .catch(() => caches.match('/app'))
    );
});
