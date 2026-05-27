/**
 * EduZim — Chart wrappers (Phase 10 — Q-001a)
 * =============================================
 * Thin Recharts wrappers using EduZim theme tokens. Aim: simple, consistent
 * API across the three apps; replace HTML-table-as-chart everywhere.
 *
 * Per ADR 011: Recharts for parent + teacher + simple admin dashboards.
 * Heavy stuff (heatmap, Zimbabwe geomap, sankey) goes to ECharts and lives
 * under packages/ui/src/components/charts/echarts/ (added in Phase 14 when
 * ministry-web is built).
 *
 * Bundle posture: Recharts is ~50KB gzipped. We import only the components
 * we use; tree-shaking handles the rest. NO default global styling here —
 * the consuming page wraps the chart in <SectionCard> for layout.
 */

"use client";

import * as React from "react";
import {
  LineChart as RLineChart,
  Line,
  BarChart as RBarChart,
  Bar,
  PieChart as RPieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

/** EduZim chart palette — purple-led, Zimbabwe accent on tertiary/quaternary. */
export const CHART_COLORS = [
  "#5B2D8A", // primary purple
  "#7C3AED", // primary lighter
  "#008751", // zim green
  "#FFD200", // zim gold
  "#D62828", // zim red (used for negative trends)
  "#94A3B8", // neutral
];

const TOOLTIP_STYLE: React.CSSProperties = {
  background: "white",
  border: "1px solid hsl(var(--border, 0 0% 90%))",
  borderRadius: "8px",
  padding: "8px 12px",
  fontSize: "12px",
};

interface BaseProps {
  data: any[];
  height?: number;
  className?: string;
  ariaLabel?: string;
}

// ─── Line ───

interface LineSeries {
  key: string;
  label: string;
  color?: string;
}

export interface LineChartProps extends BaseProps {
  xKey: string;
  series: LineSeries[];
}

export function LineChart({
  data,
  xKey,
  series,
  height = 240,
  className,
  ariaLabel = "Line chart",
}: LineChartProps) {
  return (
    <div className={className} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <RLineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey={xKey} stroke="#6B7280" fontSize={12} />
          <YAxis stroke="#6B7280" fontSize={12} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color || CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          ))}
        </RLineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Bar ───

export interface BarChartProps extends BaseProps {
  xKey: string;
  series: LineSeries[];
  stacked?: boolean;
}

export function BarChart({
  data,
  xKey,
  series,
  stacked = false,
  height = 240,
  className,
  ariaLabel = "Bar chart",
}: BarChartProps) {
  return (
    <div className={className} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <RBarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey={xKey} stroke="#6B7280" fontSize={12} />
          <YAxis stroke="#6B7280" fontSize={12} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color || CHART_COLORS[i % CHART_COLORS.length]}
              stackId={stacked ? "a" : undefined}
              radius={stacked ? 0 : [4, 4, 0, 0]}
            />
          ))}
        </RBarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Pie ───

export interface PieDatum {
  name: string;
  value: number;
  color?: string;
}

export interface PieChartProps {
  data: PieDatum[];
  height?: number;
  innerRadius?: number;
  className?: string;
  ariaLabel?: string;
}

export function PieChart({
  data,
  height = 240,
  innerRadius = 0,
  className,
  ariaLabel = "Pie chart",
}: PieChartProps) {
  return (
    <div className={className} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <RPieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius="80%"
            innerRadius={innerRadius}
            label={(entry: any) => `${entry.name}`}
          >
            {data.map((entry, i) => (
              <Cell
                key={entry.name}
                fill={entry.color || CHART_COLORS[i % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
        </RPieChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── SparkLine ───
// Compact, no-axis line for stat-card use.

export interface SparkLineProps {
  data: Array<{ value: number }>;
  height?: number;
  color?: string;
  ariaLabel?: string;
  className?: string;
}

export function SparkLine({
  data,
  height = 32,
  color = CHART_COLORS[0],
  ariaLabel = "Trend",
  className,
}: SparkLineProps) {
  return (
    <div className={className} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height}>
        <RLineChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </RLineChart>
      </ResponsiveContainer>
    </div>
  );
}
