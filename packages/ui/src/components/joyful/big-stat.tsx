/**
 * BigStat — joyful theme
 * Friendly child-progress card. Used on parent home grid.
 * Always pairs the value with a label and an optional emoji status so it
 * remains accessible without colour.
 */
import React from "react";
import { cn } from "../../lib/utils";

export interface BigStatProps {
  label: string;
  value: string | number;
  emoji?: string;
  hint?: string;
  className?: string;
}

export function BigStat({ label, value, emoji, hint, className }: BigStatProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border/60 bg-card p-5 shadow-card",
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-2">
        {emoji ? (
          <span aria-hidden="true" className="text-2xl">
            {emoji}
          </span>
        ) : null}
        <p className="text-3xl font-extrabold tracking-tight text-foreground">
          {value}
        </p>
      </div>
      {hint ? (
        <p className="mt-1 text-sm text-foreground/70">{hint}</p>
      ) : null}
    </div>
  );
}
