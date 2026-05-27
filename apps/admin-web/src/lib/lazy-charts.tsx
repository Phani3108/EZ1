/**
 * Lazy ECharts wrappers (Phase 10 — Q-001b / PH10-3).
 *
 * The page-level entry point for ECharts-backed visualisations.
 * Each component below is loaded via `next/dynamic` with `ssr: false`,
 * so:
 *
 *   * ECharts (~600KB gzipped) does NOT ship in the main page bundle.
 *   * The chart shows a skeleton until the JS chunk + the chart's first
 *     render are done.
 *   * SSR is skipped entirely — charts only render in the browser.
 *
 * Why this lives in admin-web rather than @eduzim/ui:
 *   `next/dynamic` is Next.js-specific. Each app sets up its own
 *   dynamic wrappers; the @eduzim/ui package stays framework-neutral.
 *   When ministry-web is built, copy this file across.
 *
 * PH10-3 budget: the admin-web main bundle target is < 100KB gzipped
 * over baseline. Adding these dynamic wrappers adds zero to that
 * budget — the ECharts chunks load on-demand when a chart is in view.
 */

"use client";

import dynamic from "next/dynamic";
import * as React from "react";


function ChartSkeleton({ height = 320, label = "Loading chart…" }: {
  height?: number;
  label?: string;
}) {
  return (
    <div
      role="status"
      aria-label={label}
      className="flex items-center justify-center rounded-lg border bg-muted/30"
      style={{ height }}
    >
      <span className="text-sm text-muted-foreground animate-pulse">
        {label}
      </span>
    </div>
  );
}


export const Heatmap = dynamic(
  () => import("@eduzim/ui/echarts").then((m) => m.Heatmap),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={200} label="Loading heatmap…" />,
  },
);


export const ZimbabweGeomap = dynamic(
  () => import("@eduzim/ui/echarts").then((m) => m.ZimbabweGeomap),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={420} label="Loading map…" />,
  },
);


export const Sankey = dynamic(
  () => import("@eduzim/ui/echarts").then((m) => m.Sankey),
  {
    ssr: false,
    loading: () => <ChartSkeleton height={360} label="Loading diagram…" />,
  },
);


// Re-export the prop types so consumers don't double-import from
// @eduzim/ui/echarts.
export type {
  HeatmapProps,
  HeatmapDatum,
  ZimbabweGeomapProps,
  GeomapDatum,
  SankeyProps,
  SankeyNode,
  SankeyLink,
} from "@eduzim/ui/echarts";
