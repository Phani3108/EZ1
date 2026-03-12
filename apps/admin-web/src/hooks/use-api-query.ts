/**
 * useApiQuery — Lightweight data-fetching hook for CRUD pages.
 * Re-fetches on deps change. Call refetch() after mutations.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ApiError } from "@eduzim/api-client";
import { getErrorMessage, withRequestId, getErrorDetails } from "@/lib/errors";

interface QueryState<T> {
  data: T | null;
  isLoading: boolean;
  error: { message: string; requestId: string | null; details: Record<string, unknown> | null } | null;
  refetch: () => void;
}

export function useApiQuery<T>(
  fetcher: () => Promise<{ data: T }>,
  deps: unknown[] = []
): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<QueryState<T>["error"]>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result.data);
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
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  return { data, isLoading, error, refetch: load };
}
