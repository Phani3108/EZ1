/**
 * EduZim — Heavy chart wrappers (Phase 10 — Q-001b)
 * ===================================================
 * ECharts components for visualisations that Recharts can't do well:
 *
 *   - Heatmap            (calendar attendance heatmap, district-wise)
 *   - ZimbabweGeomap     (choropleth of Zimbabwe's 10 provinces)
 *   - Sankey             (student-flow / enrolment-flow diagrams)
 *
 * ────────────────────────────────────────────────────────────────────
 * BUNDLE POSTURE (PH10-3 — critical)
 * ────────────────────────────────────────────────────────────────────
 * ECharts is ~600KB gzipped — TEN TIMES Recharts. We must NOT pull it
 * into the main bundle. Two layers of defence:
 *
 *   1. This module imports only from `echarts/core` + the specific
 *      chart-type modules it needs. The full `echarts` umbrella import
 *      would pull every chart type (~1MB+); we register just what we
 *      use.
 *
 *   2. Consumer pages MUST lazy-import via `next/dynamic`:
 *
 *          const Heatmap = dynamic(
 *            () => import("@eduzim/ui").then(m => m.Heatmap),
 *            { ssr: false, loading: () => <ChartSkeleton /> }
 *          );
 *
 *      Without `next/dynamic`, ECharts ends up in the main JS bundle
 *      of every page that imports from `@eduzim/ui`. The PH10-3 gate
 *      depends on this discipline.
 *
 * The package.json keeps ECharts under `optionalDependencies` so apps
 * that don't render heavy charts (parent-web, teacher-web) can install
 * without it. Admin-web + (future) ministry-web install with
 * `--include=optional`.
 * ────────────────────────────────────────────────────────────────────
 */

"use client";

import * as React from "react";
import { CHART_COLORS } from "../index";


/* ──────────────────────────────────────────────────────────────────
 * ECharts instance bootstrap — registered lazily on first chart mount.
 *
 * We DON'T register at module-import time. Next.js tree-shakes the
 * whole module if it's only imported via `next/dynamic`; a top-level
 * side effect would survive the tree-shake. Instead each chart's
 * useEffect runs the registration once, idempotent via a module-level
 * flag.
 * ────────────────────────────────────────────────────────────────── */

let _registered = false;
let _echarts: any = null;

async function _ensureRegistered() {
  if (_registered && _echarts) return _echarts;
  // Dynamic imports keep them out of any synchronous bundle.
  const echarts = await import("echarts/core");
  const { HeatmapChart, MapChart, SankeyChart } = await import("echarts/charts");
  const {
    TooltipComponent, GridComponent, VisualMapComponent,
    LegendComponent, TitleComponent, CalendarComponent,
  } = await import("echarts/components");
  const { CanvasRenderer } = await import("echarts/renderers");

  echarts.use([
    HeatmapChart, MapChart, SankeyChart,
    TooltipComponent, GridComponent, VisualMapComponent,
    LegendComponent, TitleComponent, CalendarComponent,
    CanvasRenderer,
  ]);
  _echarts = echarts;
  _registered = true;
  return echarts;
}


/* ──────────────────────────────────────────────────────────────────
 * Generic EChart renderer — one container, one ResizeObserver, one
 * teardown. All three chart types below use this internally.
 * ────────────────────────────────────────────────────────────────── */

interface EChartCoreProps {
  option: any;            // ECharts option object — chart-type-specific
  height?: number;
  ariaLabel?: string;
  className?: string;
  /** Optional callback invoked once the instance is ready. */
  onReady?: (instance: any) => void;
  /** GeoJSON map registration is async; pass `mapName` to wait for it. */
  mapName?: string;
  mapGeoJson?: any;
}

function EChartCore({
  option, height = 320, ariaLabel = "Chart", className, onReady,
  mapName, mapGeoJson,
}: EChartCoreProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const instanceRef = React.useRef<any>(null);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    let resizeObserver: ResizeObserver | null = null;

    (async () => {
      const echarts = await _ensureRegistered();
      if (!mounted || !containerRef.current) return;

      // Register the map if supplied (Zimbabwe geomap path).
      if (mapName && mapGeoJson) {
        echarts.registerMap(mapName, mapGeoJson);
      }

      const instance = echarts.init(containerRef.current, undefined, {
        renderer: "canvas",
      });
      instance.setOption(option);
      instanceRef.current = instance;
      setReady(true);
      onReady?.(instance);

      // Resize handling — ECharts doesn't auto-resize.
      resizeObserver = new ResizeObserver(() => instance.resize());
      resizeObserver.observe(containerRef.current);
    })();

    return () => {
      mounted = false;
      resizeObserver?.disconnect();
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);   // mount-only; option updates handled by the next effect

  // Update option on re-renders without a full teardown.
  React.useEffect(() => {
    if (ready && instanceRef.current) {
      instanceRef.current.setOption(option, true);
    }
  }, [option, ready]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height }}
      role="img"
      aria-label={ariaLabel}
      className={className}
    />
  );
}


/* ──────────────────────────────────────────────────────────────────
 * Heatmap
 *
 * A common use: attendance rate per day across a school term. X = day
 * of month, Y = month. Cells coloured by rate.
 * ────────────────────────────────────────────────────────────────── */

export interface HeatmapDatum {
  /** ISO date "YYYY-MM-DD". */
  date: string;
  /** Numeric value (e.g., attendance rate 0–100). */
  value: number;
}

export interface HeatmapProps {
  data: HeatmapDatum[];
  /** Min/max for the color scale. Defaults to [0, 100]. */
  range?: [number, number];
  /** ECharts calendar range "YYYY" or ["YYYY-MM-DD","YYYY-MM-DD"]. */
  calendarRange?: string | [string, string];
  height?: number;
  ariaLabel?: string;
  className?: string;
}

export function Heatmap({
  data, range = [0, 100], calendarRange,
  height = 200, ariaLabel = "Calendar heatmap", className,
}: HeatmapProps) {
  // Derive a sensible default calendarRange from the data if not given.
  const derivedRange = React.useMemo(() => {
    if (calendarRange) return calendarRange;
    if (!data.length) return new Date().getFullYear().toString();
    const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
    return [sorted[0].date, sorted[sorted.length - 1].date] as [string, string];
  }, [data, calendarRange]);

  const option = React.useMemo(() => ({
    tooltip: {
      formatter: (params: any) => `${params.value[0]}: ${params.value[1]}`,
    },
    visualMap: {
      min: range[0],
      max: range[1],
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: {
        color: ["#FEE2E2", "#FBBF24", CHART_COLORS[2]],   // red → amber → zim green
      },
    },
    calendar: {
      top: 30,
      left: 30,
      right: 30,
      cellSize: ["auto", 14],
      range: derivedRange,
      itemStyle: { borderWidth: 0.5, borderColor: "#fff" },
      yearLabel: { show: false },
    },
    series: [{
      type: "heatmap",
      coordinateSystem: "calendar",
      data: data.map((d) => [d.date, d.value]),
    }],
  }), [data, range, derivedRange]);

  return (
    <EChartCore option={option} height={height} ariaLabel={ariaLabel}
                className={className} />
  );
}


/* ──────────────────────────────────────────────────────────────────
 * ZimbabweGeomap — choropleth of the 10 provinces
 *
 * Consumer supplies a `data: [{provinceCode, value}]` array. The GeoJSON
 * is NOT bundled here — too heavy for the default install. The caller
 * provides it as the `geoJson` prop. Recommended source:
 *   - https://raw.githubusercontent.com/codeforafrica/CountryGeoJSONCollection
 *
 * Fallback when no geoJson is supplied: render an empty-state placeholder
 * so the consumer gets a clear "you need to wire the geoJson" signal.
 * ────────────────────────────────────────────────────────────────── */

export interface GeomapDatum {
  /** Province code matching the GeoJSON's `name` property. */
  name: string;
  value: number;
}

export interface ZimbabweGeomapProps {
  data: GeomapDatum[];
  geoJson?: any;
  /** Min/max for the color scale; defaults to data-derived. */
  range?: [number, number];
  height?: number;
  ariaLabel?: string;
  className?: string;
}

export function ZimbabweGeomap({
  data, geoJson, range, height = 420,
  ariaLabel = "Zimbabwe choropleth", className,
}: ZimbabweGeomapProps) {
  if (!geoJson) {
    return (
      <div
        style={{ height }}
        role="img"
        aria-label={ariaLabel}
        className={className + " flex items-center justify-center rounded-lg border bg-muted/30 p-4 text-center text-sm text-muted-foreground"}
      >
        ZimbabweGeomap: pass a <code className="rounded bg-muted px-1 py-0.5 text-xs">geoJson</code> prop
        with Zimbabwe province GeoJSON.
        <br />
        See <code className="text-xs">apps/admin-web/public/zimbabwe-provinces.geo.json</code>.
      </div>
    );
  }

  const [vMin, vMax] = range || (() => {
    const values = data.map((d) => d.value);
    return [Math.min(...values, 0), Math.max(...values, 1)] as [number, number];
  })();

  const option = React.useMemo(() => ({
    tooltip: {
      trigger: "item",
      formatter: (params: any) => `${params.name}: ${params.value ?? "—"}`,
    },
    visualMap: {
      min: vMin,
      max: vMax,
      left: "left",
      bottom: 8,
      text: ["High", "Low"],
      calculable: true,
      inRange: {
        color: ["#F3E8FF", CHART_COLORS[1], CHART_COLORS[0]],  // light → primary
      },
    },
    series: [{
      type: "map",
      map: "zimbabwe",
      roam: false,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 11 } },
      data,
    }],
  }), [data, vMin, vMax]);

  return (
    <EChartCore
      option={option}
      height={height}
      ariaLabel={ariaLabel}
      className={className}
      mapName="zimbabwe"
      mapGeoJson={geoJson}
    />
  );
}


/* ──────────────────────────────────────────────────────────────────
 * Sankey — student-flow / enrolment-flow diagrams
 *
 * Common use: "Grade 7 → Grade 8 promotion flow" or "Enrolled →
 * Promoted / Withdrawn / Repeated" lifecycle.
 * ────────────────────────────────────────────────────────────────── */

export interface SankeyNode {
  name: string;
  value?: number;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

export interface SankeyProps {
  nodes: SankeyNode[];
  links: SankeyLink[];
  height?: number;
  ariaLabel?: string;
  className?: string;
}

export function Sankey({
  nodes, links, height = 360,
  ariaLabel = "Sankey diagram", className,
}: SankeyProps) {
  const option = React.useMemo(() => ({
    tooltip: { trigger: "item", triggerOn: "mousemove" },
    series: [{
      type: "sankey",
      data: nodes,
      links,
      lineStyle: { color: "gradient", curveness: 0.5 },
      itemStyle: {
        color: CHART_COLORS[0],
        borderColor: "#fff",
      },
      label: { fontSize: 11 },
    }],
  }), [nodes, links]);

  return (
    <EChartCore option={option} height={height} ariaLabel={ariaLabel}
                className={className} />
  );
}
