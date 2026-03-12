/**
 * @eduzim/offline-core — OfflineCache
 * ======================================
 * Read-cache engine wrapping the storage layer.
 * Class-based API: get, set, invalidate.
 * TTL is enforced — expired entries are deleted on read (never return stale).
 */

import { getCache, setCache, deleteCache, clearExpiredCache } from "./storage";
import type { CacheEntry } from "./types";

export class OfflineCache {
  /**
   * Retrieve cached data by key.
   * Returns `null` if missing or expired (expired entries are auto-deleted).
   */
  async get<T = any>(key: string): Promise<T | null> {
    const entry = await getCache<T>(key);
    if (!entry) return null;

    // TTL enforcement
    if (entry.expiresAt < Date.now()) {
      await deleteCache(key);
      return null;
    }

    return entry.data;
  }

  /**
   * Store data with a TTL (milliseconds).
   * Overwrites any existing entry for the same key.
   */
  async set<T = any>(key: string, data: T, ttlMs: number): Promise<void> {
    const now = Date.now();
    const entry: CacheEntry<T> = {
      key,
      data,
      expiresAt: now + ttlMs,
      lastUpdated: now,
    };
    await setCache(entry);
  }

  /** Remove a cache entry by key. */
  async invalidate(key: string): Promise<void> {
    await deleteCache(key);
  }

  /** Remove all expired entries. Returns count deleted. */
  async purgeExpired(): Promise<number> {
    return clearExpiredCache();
  }
}
