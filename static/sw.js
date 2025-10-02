// static/sw.js - Service Worker for push notifications and offline support
const CACHE_NAME = 'community-platform-v1';
const urlsToCache = [
    '/',
    '/static/css/accounts.css',
    '/static/js/accounts.js',
    '/static/js/utils.js',
    '/static/js/websocket.js',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// Install event - cache resources
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version or fetch from network
                return response || fetch(event.request);
            })
    );
});

// Push event - handle push notifications
self.addEventListener('push', event => {
    const options = {
        body: event.data ? event.data.text() : 'New notification',
        icon: '/static/img/icon-192x192.png',
        badge: '/static/img/badge-72x72.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: '1'
        },
        actions: [
            {
                action: 'explore',
                title: 'View',
                icon: '/static/img/checkmark.png'
            },
            {
                action: 'close',
                title: 'Dismiss',
                icon: '/static/img/xmark.png'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification('Community Platform', options)
    );
});

// Notification click event
self.addEventListener('notificationclick', event => {
    event.notification.close();

    if (event.action === 'explore') {
        // Open the app
        event.waitUntil(
            clients.openWindow('/accounts/dashboard/')
        );
    }
});