/**
 * MinistryStatCard — sovereign theme
 * Bold KPI card with a Zimbabwe flag-stripe accent and optional
 * audit-trail footer (e.g. "Last updated 10:42 by MoPSE / Manicaland").
 *
 * Drop-in replacement for StatCard on admin/ministry surfaces.
 */
import React from "react";
import { cn } from "../../lib/utils";
import { type LucideIcon } from "lucide-react";

export interface MinistryStatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  /** Optional trend, e.g. "+3.1% vs last term". */
  trend?: { value: string; positive?: boolean };
  /** Footer for audit/source attribution. Renders muted, small. */
  source?: string;
  /** Optional accent — defaults to Zimbabwe green. */
  accent?: "green" | "gold" | "red" | "black";
  className?: string;
}

const accentVar: Record<NonNullable<MinistryStatCardProps["accent"]>, string> =
  {
    green: "hsl(var(--zim-green))",
    gold: "hsl(var(--zim-gold))",
    red: "hsl(var(--zim-red))",
    black: "hsl(var(--zim-black, 220 20% 10%))",
  };

export function MinistryStatCard({
  label,
  value,
  icon: Icon,
  trend,
  source,
  accent = "green",
  className,
}: MinistryStatCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border bg-card p-5 shadow-card zim-watermark",
        className,
      )}
    >
      {/* Left accent bar in flag colour */}
      <span
        aria-hidden="true"
        className="absolute left-0 top-0 h-full w-1"
        style={{ background: accentVar[accent] }}
      />
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {Icon ? (
          <Icon
            aria-hidden="true"
            className="h-4 w-4 text-muted-foreground"
          />
        ) : null}
      </div>
      <p className="mt-2 text-3xl font-extrabold tracking-tight text-foreground">
        {value}
      </p>
      {trend ? (
        <p
          className={cn(
            "mt-1 text-xs font-medium",
            trend.positive
              ? "text-[hsl(var(--zim-green))]"
              : "text-[hsl(var(--zim-red))]",
          )}
        >
          {trend.value}
        </p>
      ) : null}
      {source ? (
        <p className="mt-3 border-t border-border pt-2 text-[11px] text-muted-foreground">
          {source}
        </p>
      ) : null}
    </div>
  );
}
