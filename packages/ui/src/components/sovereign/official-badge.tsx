/**
 * OfficialBadge — sovereign theme
 * Stamp-style badge used to mark content as aligned with national programs:
 *   "Aligned with MoPSE", "Vision 2030", "ZIMSEC-aligned", etc.
 */
import React from "react";
import { cn } from "../../lib/utils";

type Variant = "mopse" | "vision2030" | "zimsec" | "neutral";

const variantStyles: Record<Variant, string> = {
  mopse:
    "border-[hsl(var(--zim-green))] bg-[hsl(var(--zim-green)_/_0.08)] text-[hsl(var(--zim-green))]",
  vision2030:
    "border-[hsl(var(--zim-gold))] bg-[hsl(var(--zim-gold)_/_0.12)] text-[hsl(var(--zim-gold)_/_0.95)]",
  zimsec:
    "border-[hsl(var(--zim-red))] bg-[hsl(var(--zim-red)_/_0.08)] text-[hsl(var(--zim-red))]",
  neutral: "border-border bg-muted text-muted-foreground",
};

export interface OfficialBadgeProps {
  label: string;
  variant?: Variant;
  className?: string;
}

export function OfficialBadge({
  label,
  variant = "mopse",
  className,
}: OfficialBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        variantStyles[variant],
        className,
      )}
      role="status"
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-current"
      />
      {label}
    </span>
  );
}
