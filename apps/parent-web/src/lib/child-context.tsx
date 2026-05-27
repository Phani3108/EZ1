/**
 * ChildContext — Phase 12a / P-002.
 *
 * Multi-child UX: a parent with two or more children needs to switch
 * which child the rest of the app (attendance, fees, marks, etc.) is
 * "about." This context holds the currently-selected child id plus the
 * full children list.
 *
 * The list is fetched once from `/parents/me/children` and cached in
 * localStorage so the switcher renders instantly on the next page
 * load (the list rarely changes). Once a child is picked, the id
 * lives in localStorage too — staying on the same child between
 * sessions matches user intuition.
 *
 * Single-child households are the common case; the switcher renders
 * as a static label rather than a dropdown when there's only one
 * child, avoiding a useless click target.
 */

"use client";

import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";


export interface ChildSummary {
  /** Student.id */
  id: string;
  first_name: string;
  last_name: string;
  /** True for the primary-guardian linkage (StudentParent.is_primary). */
  is_primary: boolean;
  enrollment_id?: string | null;
  class_id?: string | null;
}

interface ChildContextValue {
  children: ChildSummary[];
  isLoading: boolean;
  /** Currently-selected child. null when no children OR pre-load. */
  selected: ChildSummary | null;
  selectChild: (id: string) => void;
  refetch: () => Promise<void>;
}


const ChildContext = createContext<ChildContextValue | undefined>(undefined);
const STORAGE_KEY = "eduzim.parent.selectedChildId";


async function fetchChildren(): Promise<ChildSummary[]> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const { getAccessToken } = await import("@eduzim/auth");
  const tok = getAccessToken();
  const res = await fetch(`${baseUrl}/api/v1/parents/me/children`, {
    headers: tok ? { Authorization: `Bearer ${tok}` } : undefined,
  });
  if (!res.ok) {
    if (res.status === 404) return [];
    throw new Error(`fetchChildren failed: ${res.status}`);
  }
  const body = (await res.json()) as { data: ChildSummary[] };
  return body.data ?? [];
}


export function ChildProvider({
  children: providerChildren,
}: {
  children: React.ReactNode;
}) {
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await fetchChildren();
      setChildren(list);
      // Pick a default: previously-saved selection if still present,
      // else the primary child, else the first.
      if (typeof window !== "undefined") {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored && list.some((c) => c.id === stored)) {
          setSelectedId(stored);
        } else {
          const primary = list.find((c) => c.is_primary);
          setSelectedId(primary?.id ?? list[0]?.id ?? null);
        }
      }
    } catch {
      // Non-fatal — the UI shows "no children" if list stays empty.
      setChildren([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selectChild = useCallback((id: string) => {
    setSelectedId(id);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, id);
    }
  }, []);

  const selected = useMemo(
    () => children.find((c) => c.id === selectedId) ?? null,
    [children, selectedId],
  );

  const value = useMemo<ChildContextValue>(
    () => ({
      children, isLoading, selected, selectChild, refetch: load,
    }),
    [children, isLoading, selected, selectChild, load],
  );

  return (
    <ChildContext.Provider value={value}>
      {providerChildren}
    </ChildContext.Provider>
  );
}


export function useChild(): ChildContextValue {
  const ctx = useContext(ChildContext);
  if (!ctx) {
    throw new Error("useChild must be used inside <ChildProvider>");
  }
  return ctx;
}
