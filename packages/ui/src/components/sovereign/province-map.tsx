/**
 * ProvinceMap — sovereign theme
 * Clickable SVG map of Zimbabwe's 10 provinces. Province polygons are
 * stylised rectangles for v1 (an accurate geographic SVG will replace this
 * once we ship the ministry-service rollup data).
 *
 * Each tile receives a heat colour based on `data[provinceId]?.value`
 * (0..1) blending Zimbabwe green → yellow → red. Tiles are full keyboard
 * accessible and emit `onSelect(provinceId)` on click/enter/space.
 */
import React from "react";
import { cn } from "../../lib/utils";

export const ZIMBABWE_PROVINCES = [
  { id: "harare", name: "Harare" },
  { id: "bulawayo", name: "Bulawayo" },
  { id: "manicaland", name: "Manicaland" },
  { id: "mashonaland-central", name: "Mashonaland Central" },
  { id: "mashonaland-east", name: "Mashonaland East" },
  { id: "mashonaland-west", name: "Mashonaland West" },
  { id: "masvingo", name: "Masvingo" },
  { id: "matabeleland-north", name: "Matabeleland North" },
  { id: "matabeleland-south", name: "Matabeleland South" },
  { id: "midlands", name: "Midlands" },
] as const;

export type ProvinceId = (typeof ZIMBABWE_PROVINCES)[number]["id"];

export interface ProvinceDatum {
  /** 0..1 — used to pick a heat colour. */
  value: number;
  /** Optional secondary label, e.g. "82% attendance". */
  label?: string;
}

export interface ProvinceMapProps {
  data?: Partial<Record<ProvinceId, ProvinceDatum>>;
  onSelect?: (id: ProvinceId) => void;
  selected?: ProvinceId | null;
  /** ARIA label for the whole map region. */
  ariaLabel?: string;
  className?: string;
}

/** Blend Zimbabwe green (low risk) → gold → red (high risk). */
function heatColor(value: number): string {
  const v = Math.max(0, Math.min(1, value));
  if (v < 0.5) {
    // green → gold
    const t = v / 0.5;
    return `color-mix(in oklab, hsl(var(--zim-green)) ${(1 - t) * 100}%, hsl(var(--zim-gold)) ${t * 100}%)`;
  }
  const t = (v - 0.5) / 0.5;
  return `color-mix(in oklab, hsl(var(--zim-gold)) ${(1 - t) * 100}%, hsl(var(--zim-red)) ${t * 100}%)`;
}

export function ProvinceMap({
  data,
  onSelect,
  selected,
  ariaLabel = "Zimbabwe provinces",
  className,
}: ProvinceMapProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "grid grid-cols-2 gap-2 rounded-lg border bg-card p-3 sm:grid-cols-3 lg:grid-cols-5",
        className,
      )}
    >
      {ZIMBABWE_PROVINCES.map((p) => {
        const datum = data?.[p.id];
        const v = datum?.value;
        const isSelected = selected === p.id;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onSelect?.(p.id)}
            className={cn(
              "group relative flex h-20 flex-col items-start justify-between rounded-md border p-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isSelected ? "ring-2 ring-ring" : "hover:shadow-card",
            )}
            style={{
              background:
                v !== undefined
                  ? `linear-gradient(135deg, ${heatColor(v)} 0%, ${heatColor(v)} 60%, hsl(var(--card)) 100%)`
                  : "hsl(var(--muted))",
            }}
            aria-pressed={isSelected}
            aria-label={
              datum?.label
                ? `${p.name}, ${datum.label}`
                : `${p.name}, no data`
            }
          >
            <span className="text-[11px] font-semibold uppercase tracking-wide text-foreground/80">
              {p.name}
            </span>
            {datum?.label ? (
              <span className="text-sm font-bold text-foreground">
                {datum.label}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">No data</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
