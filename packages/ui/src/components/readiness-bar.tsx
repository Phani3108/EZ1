/**
 * Phase 15b — ReadinessBar
 *
 * Top-of-page progress bar. Shows percent-of-steps green +
 * a count summary ("4 of 7 green · 2 amber · 1 red").
 */
"use client";

import * as React from "react";
import { cn } from "../lib/utils";
import type { ChecklistStatus } from "./checklist-item";

export interface ReadinessBarProps {
  statuses: ChecklistStatus[];
  /** Optional label, defaults to "Setup readiness". */
  label?: string;
  className?: string;
}

export function ReadinessBar({
  statuses,
  label = "Setup readiness",
  className,
}: ReadinessBarProps) {
  const total = statuses.length || 1;
  const counts = {
    green: statuses.filter((s) => s === "green").length,
    amber: statuses.filter((s) => s === "amber").length,
    red: statuses.filter((s) => s === "red").length,
    unknown: statuses.filter((s) => s === "unknown").length,
  };
  const pct = Math.round((counts.green / total) * 100);

  return (
    <div className={cn("rounded-md border bg-card p-4", className)}>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-2xl font-bold tabular-nums">{pct}%</div>
      </div>
      <div
        className="h-2 w-full rounded-full bg-muted overflow-hidden flex"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        {counts.green > 0 && (
          <div
            className="h-full bg-green-500"
            style={{ width: `${(counts.green / total) * 100}%` }}
          />
        )}
        {counts.amber > 0 && (
          <div
            className="h-full bg-amber-500"
            style={{ width: `${(counts.amber / total) * 100}%` }}
          />
        )}
        {counts.red > 0 && (
          <div
            className="h-full bg-red-500"
            style={{ width: `${(counts.red / total) * 100}%` }}
          />
        )}
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        {counts.green} of {total} done
        {counts.amber > 0 && ` · ${counts.amber} in progress`}
        {counts.red > 0 && ` · ${counts.red} not started`}
      </div>
    </div>
  );
}
