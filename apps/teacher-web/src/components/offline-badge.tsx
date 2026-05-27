/**
 * OfflineBadge — Phase 11a / T-014.
 *
 * Two-mode indicator the rest of the app uses to surface offline state:
 *
 *   - mode="status"   : a pill at the top of the page that says "Offline"
 *                       whenever `useSync().online === false`. Disappears
 *                       when connectivity returns. This is the global
 *                       cue — placed in headers / page shells.
 *   - mode="cache"    : an inline pill rendered next to data that came
 *                       from the cache (the consumer passes `fromCache`
 *                       from `useCachedApiQuery`). Different from
 *                       "status" because data CAN be cached while online
 *                       (we paint from cache and refresh in background),
 *                       and we want the user to know what they're seeing.
 *
 * The component is intentionally tiny — no padding around it, no
 * positioning concerns; placement is up to the parent.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { WifiOff, CloudOff } from "lucide-react";
import { useSync } from "@/lib/sync-provider";

interface OfflineBadgeProps {
  /**
   * "status" = live network indicator (renders only when offline).
   * "cache"  = "this data came from cache" indicator (renders when
   *            `fromCache` is true).
   */
  mode: "status" | "cache";
  /** Required when mode="cache". Provided by useCachedApiQuery. */
  fromCache?: boolean;
  className?: string;
}

export function OfflineBadge({ mode, fromCache, className }: OfflineBadgeProps) {
  const { online } = useSync();
  const t = useTranslations("offline");

  if (mode === "status") {
    if (online) return null;
    return (
      <span
        role="status"
        aria-live="polite"
        data-testid="offline-status-badge"
        className={`inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ${className ?? ""}`}
      >
        <WifiOff className="h-3 w-3" />
        {t("offline")}
      </span>
    );
  }

  // mode === "cache"
  if (!fromCache) return null;
  return (
    <span
      role="note"
      data-testid="cache-badge"
      className={`inline-flex items-center gap-1 rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-xs text-blue-700 ${className ?? ""}`}
    >
      <CloudOff className="h-3 w-3" />
      {online ? t("showingCached") : t("offlineShowingCached")}
    </span>
  );
}
