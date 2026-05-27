/**
 * @eduzim/ui/echarts — separate entry-point for the heavy ECharts
 * wrappers (Phase 10 — Q-001b / PH10-3).
 *
 * Importing from `@eduzim/ui` does NOT pull ECharts. The runtime
 * exports below are reachable only via `@eduzim/ui/echarts` — and
 * consumer pages should still wrap them in `next/dynamic` so ECharts
 * lands in a separate chunk.
 *
 * The split-entry approach keeps the main `@eduzim/ui` bundle small
 * even if a consumer accidentally imports a chart without dynamic
 * wrapping — the worst case is the chunk loads synchronously rather
 * than not loading at all.
 */
export {
  Heatmap,
  ZimbabweGeomap,
  Sankey,
} from "./components/charts/echarts";

export type {
  HeatmapProps,
  HeatmapDatum,
  ZimbabweGeomapProps,
  GeomapDatum,
  SankeyProps,
  SankeyNode,
  SankeyLink,
} from "./components/charts/echarts";
