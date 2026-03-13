/**
 * EduZim Service Worker — hybrid caching strategy.
 *
 * Strategy matrix:
 *   /_next/static/*  → Cache-first  (immutable hashed bundles)
 *   /api/*           → Network-first, stale fallback for reads
 *   Navigation       → Network-first, offline shell fallback
 *   Other static     → Cache-first  (icons, images, fonts)
 */

const CACHE_NAME = "eduzim-v1";
const STATIC_ASSETS = ["/", "/offline"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (POST/PUT/DELETE go to network)
  if (request.method !== "GET") return;

  // ── Network-first for API calls ──
  // Always try the network; fall back to cached response for offline reads.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // ── Network-first for navigation ──
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline") || caches.match("/"))
    );
    return;
  }

  // ── Cache-first for static assets ──
  // /_next/static/* are content-hashed and immutable.
  // Icons, images, and fonts are also served cache-first.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          if (response.ok && url.origin === self.location.origin) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
    )
  );
});

// ── Background Sync ──
self.addEventListener("sync", (event) => {
  if (event.tag === "attendance-sync" || event.tag === "offline-queue") {
    event.waitUntil(
      self.clients.matchAll().then((clients) => {
        for (const client of clients) {
          client.postMessage({ type: "SYNC_TRIGGER", tag: event.tag });
        }
      })
    );
  }
});

// ── Push Notifications ──
self.addEventListener("push", (event) => {
  if (!event.data) return;
  try {
    const data = event.data.json();
    event.waitUntil(
      self.registration.showNotification(data.title || "EduZim", {
        body: data.body || "",
        icon: "/icons/icon-192x192.png",
        badge: "/icons/icon-72x72.png",
        data: data,
        tag: data.tag || "eduzim-notification",
      })
    );
  } catch (e) {
    // Ignore malformed push
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(url);
    })
  );
});
