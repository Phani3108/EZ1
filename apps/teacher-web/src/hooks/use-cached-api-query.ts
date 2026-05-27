/**
 * useCachedApiQuery — Offline-aware fetch hook (Phase 11a / T-014).
 *
 * Wraps the existing `useApiQuery` flow with a read-cache on top of the
 * @eduzim/offline-core OfflineCache. Designed to close BUG-010 ("class
 * roster has no offline cache; loading spinner indefinitely offline").
 *
 * Flow:
 *   1. On mount, read the cache. If a non-expired entry exists, set it
 *      as `data` and flip `isLoading` to false IMMEDIATELY — the user
 *      sees the previously-loaded roster instead of an infinite spinner.
 *      The cache entry is also flagged via `fromCache: true` so the UI
 *      can show "showing cached data" hints.
 *   2. Fire the network fetch in parallel. If it succeeds, overwrite the
 *      cache and the in-memory data (now `fromCache: false`).
 *   3. If the fetch fails AND we have cached data, keep the cached data;
 *      the user sees something useful instead of an error screen.
 *   4. If the fetch fails AND there's no cache, surface the error like
 *      the regular `useApiQuery`.
 *
 * Cache keys are caller-provided. Convention: `${domain}:${...identifiers}`
 * (e.g. `roster:enrollments:<classId>`, `roster:students:list`).
 *
 * NB: this hook is intentionally separate from `useApiQuery` rather than
 * an option-bag extension. The non-cached path's API surface stays
 * unchanged, and pages that opt into caching also opt into the slightly
 * different return shape (`fromCache`). Two clear hooks beat one
 * conditional hook with subtle semantic shifts.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { OfflineCache } from "@eduzim/offline-core";
import { getErrorMessage, withRequestId, getErrorDetails } from "@/lib/errors";

// One shared instance — IndexedDB transactions handle concurrency.
const cache = new OfflineCache();

interface CachedQueryState<T> {
  data: T | null;
  isLoading: boolean;
  /** True when `data` came from the cache and not the network. */
  fromCache: boolean;
  error: {
    message: string;
    requestId: string | null;
    details: Record<string, unknown> | null;
  } | null;
  refetch: () => void;
}

interface UseCachedApiQueryOptions {
  /** Cache key — caller's responsibility to make it specific enough. */
  cacheKey: string;
  /** TTL in ms. Default = 24 hours (one school day). */
  ttlMs?: number;
}

const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000;

export function useCachedApiQuery<T>(
  fetcher: () => Promise<{ data: T }>,
  options: UseCachedApiQueryOptions,
  deps: unknown[] = [],
): CachedQueryState<T> {
  const { cacheKey, ttlMs = DEFAULT_TTL_MS } = options;

  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [fromCache, setFromCache] = useState(false);
  const [error, setError] = useState<CachedQueryState<T>["error"]>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    // Try the cache first. If we have a hit, paint immediately — the
    // user is never stuck on a spinner just because their network is
    // slow or absent.
    let cachedHit = false;
    try {
      const cached = await cache.get<T>(cacheKey);
      if (cached !== null && mountedRef.current) {
        setData(cached);
        setFromCache(true);
        setIsLoading(false);
        cachedHit = true;
      }
    } catch {
      // Cache read errors are non-fatal — IndexedDB may be unavailable
      // (Safari private browsing, etc.). Fall through to network.
    }

    if (!cachedHit && mountedRef.current) {
      setIsLoading(true);
      setFromCache(false);
    }
    if (mountedRef.current) setError(null);

    try {
      const result = await fetcher();
      if (!mountedRef.current) return;
      setData(result.data);
      setFromCache(false);
      // Write-through to cache so the next mount paints fast.
      // Failures here are non-fatal — same reasoning as the read path.
      try {
        await cache.set(cacheKey, result.data, ttlMs);
      } catch {
        /* ignore */
      }
    } catch (err) {
      if (!mountedRef.current) return;
      // If we already painted from cache, keep that and don't surface
      // the network error as a hard failure — the user has working data.
      if (cachedHit) {
        // Silent: cached data is still on screen, fromCache stays true.
        return;
      }
      setError({
        message: getErrorMessage(err),
        requestId: withRequestId(err),
        details: getErrorDetails(err),
      });
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, ttlMs, ...deps]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  return { data, isLoading, fromCache, error, refetch: load };
}
