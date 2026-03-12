/**
 * @eduzim/offline-core — Network Utilities
 * ===========================================
 * Thin wrappers around the browser's online / offline events.
 * No logic — just plumbing.
 */

/** Whether the browser reports being online. */
export function isOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}

/** Register a callback that fires when the browser goes online. Returns unsubscribe fn. */
export function onOnline(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("online", cb);
  return () => window.removeEventListener("online", cb);
}

/** Register a callback that fires when the browser goes offline. Returns unsubscribe fn. */
export function onOffline(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("offline", cb);
  return () => window.removeEventListener("offline", cb);
}
