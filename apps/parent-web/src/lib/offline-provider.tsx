/**
 * Parent-web — Offline Provider
 * ================================
 * Read-cache oriented offline support using @eduzim/offline-core OfflineCache.
 * Provides:
 *   - online/offline status
 *   - cachedFetch() — network-first with IndexedDB fallback
 *   - offline banner state
 */

"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import {
  OfflineCache,
  isOnline as checkOnline,
  onOnline,
  onOffline,
} from "@eduzim/offline-core";

// ───── TTL Constants (milliseconds) ─────
export const CacheTTL = {
  SHORT: 1 * 60 * 60 * 1000, // 1 hour
  MEDIUM: 12 * 60 * 60 * 1000, // 12 hours
  LONG: 24 * 60 * 60 * 1000, // 24 hours
} as const;

interface OfflineContextValue {
  /** Whether the browser is online */
  online: boolean;
  /**
   * Fetch data with offline caching.
   * Network-first: if online, fetch from API and update cache.
   * If offline (or fetch fails), return cached data if available.
   */
  cachedFetch: <T>(
    key: string,
    fetcher: () => Promise<{ data: T }>,
    ttl?: number,
  ) => Promise<{ data: T; fromCache: boolean }>;
}

const OfflineContext = createContext<OfflineContextValue>({
  online: true,
  cachedFetch: () => Promise.reject(new Error("OfflineProvider not mounted")),
});

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState(true);
  const cacheRef = useRef<OfflineCache>(new OfflineCache());

  useEffect(() => {
    setOnline(checkOnline());

    const unsubOn = onOnline(() => setOnline(true));
    const unsubOff = onOffline(() => setOnline(false));

    // Purge expired cache on mount
    cacheRef.current.purgeExpired();

    return () => {
      unsubOn();
      unsubOff();
    };
  }, []);

  const cachedFetch = useCallback(
    async <T,>(
      key: string,
      fetcher: () => Promise<{ data: T }>,
      ttl: number = CacheTTL.LONG,
    ): Promise<{ data: T; fromCache: boolean }> => {
      const cache = cacheRef.current;

      // Try network first
      if (checkOnline()) {
        try {
          const result = await fetcher();
          await cache.set<T>(key, result.data, ttl);
          return { data: result.data, fromCache: false };
        } catch {
          // Network failed even though we appear online — fall through to cache
        }
      }

      // Offline or network failed — try cache
      const cached = await cache.get<T>(key);
      if (cached !== null) {
        return { data: cached, fromCache: true };
      }

      throw new Error("No cached data available");
    },
    [],
  );

  return (
    <OfflineContext.Provider value={{ online, cachedFetch }}>
      {children}
    </OfflineContext.Provider>
  );
}

/** Hook to access offline state and caching */
export function useOffline() {
  return useContext(OfflineContext);
}
