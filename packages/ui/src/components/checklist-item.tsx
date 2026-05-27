/**
 * Phase 15b — ChecklistItem
 *
 * Single row in a setup-readiness checklist. Renders a green/amber/red
 * status dot, a label, an optional evidence chip, and an optional
 * action button.
 *
 * Designed to be controlled — the parent passes the status; this
 * component doesn't fetch anything.
 */
"use client";

import * as React from "react";
import { cn } from "../lib/utils";
import { Button } from "./button";

export type ChecklistStatus = "green" | "amber" | "red" | "unknown";

export interface ChecklistItemProps {
  status: ChecklistStatus;
  label: string;
  evidence?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  href?: string;
  className?: string;
}

const STATUS_STYLES: Record<ChecklistStatus, { dot: string; ring: string; pill: string; pillText: string }> = {
  green: {
    dot: "bg-green-500",
    ring: "ring-green-500/30",
    pill: "bg-green-100 dark:bg-green-900/40",
    pillText: "text-green-800 dark:text-green-200",
  },
  amber: {
    dot: "bg-amber-500",
    ring: "ring-amber-500/30",
    pill: "bg-amber-100 dark:bg-amber-900/40",
    pillText: "text-amber-800 dark:text-amber-200",
  },
  red: {
    dot: "bg-red-500",
    ring: "ring-red-500/30",
    pill: "bg-red-100 dark:bg-red-900/40",
    pillText: "text-red-800 dark:text-red-200",
  },
  unknown: {
    dot: "bg-muted-foreground/30",
    ring: "ring-muted-foreground/10",
    pill: "bg-muted",
    pillText: "text-muted-foreground",
  },
};

const STATUS_LABEL: Record<ChecklistStatus, string> = {
  green: "Done",
  amber: "In progress",
  red: "Not started",
  unknown: "—",
};

export function ChecklistItem({
  status,
  label,
  evidence,
  actionLabel,
  onAction,
  href,
  className,
}: ChecklistItemProps) {
  const s = STATUS_STYLES[status];
  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-md border bg-card p-3",
        className,
      )}
      role="group"
      aria-label={`${label} — ${STATUS_LABEL[status]}`}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-3 w-3 shrink-0 rounded-full ring-4",
          s.dot, s.ring,
        )}
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium">{label}</div>
        {evidence !== undefined && evidence !== null && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            {evidence}
          </div>
        )}
      </div>
      <span
        className={cn(
          "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
          s.pill, s.pillText,
        )}
      >
        {STATUS_LABEL[status]}
      </span>
      {(actionLabel || href) && (
        href ? (
          <a
            href={href}
            className="text-sm font-medium text-primary hover:underline shrink-0"
          >
            {actionLabel ?? "Open"}
          </a>
        ) : (
          <Button variant="ghost" size="sm" onClick={onAction}>
            {actionLabel ?? "Open"}
          </Button>
        )
      )}
    </div>
  );
}
