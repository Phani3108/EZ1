/**
 * Phase 15b — InvitationStatusPill
 *
 * Tiny chip showing where an invitation is in its lifecycle:
 *   queued / sent / manual_pending / failed / activated.
 */
"use client";

import * as React from "react";
import { cn } from "../lib/utils";

export type InvitationStatus =
  | "queued"
  | "sent"
  | "delivered"
  | "manual_pending"
  | "failed"
  | "activated";

export interface InvitationStatusPillProps {
  status: InvitationStatus;
  className?: string;
}

const PILL: Record<InvitationStatus, { label: string; classes: string }> = {
  queued: {
    label: "Queued",
    classes: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200",
  },
  sent: {
    label: "Sent",
    classes: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200",
  },
  delivered: {
    label: "Delivered",
    classes: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  },
  manual_pending: {
    label: "Manual code",
    classes: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  },
  failed: {
    label: "Failed",
    classes: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
  },
  activated: {
    label: "Activated ✓",
    classes: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  },
};

export function InvitationStatusPill({ status, className }: InvitationStatusPillProps) {
  const s = PILL[status] ?? PILL.queued;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        s.classes,
        className,
      )}
    >
      {s.label}
    </span>
  );
}
