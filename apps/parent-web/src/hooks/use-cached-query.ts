/**
 * useCachedQuery — Offline-aware data-fetching hook for parent-web.
 * Uses cachedFetch from OfflineProvider: network-first with IndexedDB fallback.
 * Same interface as useApiQuery, plus a `fromCache` indicator.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useOffline } from "@/lib/offline-provider";
import { getErrorMessage, withRequestId, getErrorDetails } from "@/lib/errors";

interface CachedQueryState<T> {
  data: T | null;
  isLoading: boolean;
  error: { message: string; requestId: string | null; details: Record<string, unknown> | null } | null;
  fromCache: boolean;
  refetch: () => void;
}

export function useCachedQuery<T>(
  key: string,
  fetcher: () => Promise<{ data: T }>,
  ttl: number,
  deps: unknown[] = [],
): CachedQueryState<T> {
  const { cachedFetch } = useOffline();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [fromCache, setFromCache] = useState(false);
  const [error, setError] = useState<CachedQueryState<T>["error"]>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await cachedFetch<T>(key, fetcher, ttl);
      if (mountedRef.current) {
        setData(result.data);
        setFromCache(result.fromCache);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError({
          message: getErrorMessage(err),
          requestId: withRequestId(err),
          details: getErrorDetails(err),
        });
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ...deps]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  return { data, isLoading, error, fromCache, refetch: load };
}
