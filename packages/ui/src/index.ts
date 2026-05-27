export { Button } from "./components/button";
export type { ButtonProps } from "./components/button";
export { Input } from "./components/input";
export { Label } from "./components/label";
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "./components/card";
export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./components/table";
export { Badge } from "./components/badge";
export { Select } from "./components/select";
export { Dialog, DialogHeader, DialogTitle, DialogFooter } from "./components/dialog";
export { Alert, AlertTitle, AlertDescription } from "./components/alert";
export { Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter } from "./components/sheet";
export { Switch } from "./components/switch";
export { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/tabs";
export { cn } from "./lib/utils";

/* ─── Design System v1.0 — Layout Components ─── */
export { PageContainer } from "./components/page-container";
export { SectionCard } from "./components/section-card";
export { StatCard } from "./components/stat-card";
export { DataTable } from "./components/data-table";
export type { DataTableColumn } from "./components/data-table";

/* ─── Design Tokens ─── */
export {
  colors,
  spacing,
  typography,
  radii,
  shadows,
  transitions,
  kidScale,
  prideAccents,
  PERSONA_THEMES,
} from "./tokens";
export type { PersonaThemeName } from "./tokens";

/* ─── Upload ─── */
export { BulkUpload } from "./components/bulk-upload";
export type { BulkUploadResult } from "./components/bulk-upload";

/* ─── Onboarding (Phase 15) ─── */
export { ChecklistItem } from "./components/checklist-item";
export type { ChecklistItemProps, ChecklistStatus } from "./components/checklist-item";
export { Stepper } from "./components/stepper";
export type { StepperProps, StepperStep } from "./components/stepper";
export { ReadinessBar } from "./components/readiness-bar";
export type { ReadinessBarProps } from "./components/readiness-bar";
export { InvitationStatusPill } from "./components/invitation-status-pill";
export type { InvitationStatusPillProps, InvitationStatus } from "./components/invitation-status-pill";

/* ─── Friendly errors (universal) ─── */
export { FriendlyError } from "./components/friendly-error";
export type { FriendlyErrorProps } from "./components/friendly-error";
export {
  ERROR_CATALOG,
  classifyError,
} from "./lib/error-catalog";
export type {
  FriendlyErrorCode,
  FriendlyErrorEntry,
} from "./lib/error-catalog";

/* ─── Sovereign (admin-web + ministry-web only) ─── */
export { FlagHeader } from "./components/sovereign/flag-header";
export type { FlagHeaderProps } from "./components/sovereign/flag-header";
export { OfficialBadge } from "./components/sovereign/official-badge";
export type { OfficialBadgeProps } from "./components/sovereign/official-badge";
export { MinistryStatCard } from "./components/sovereign/ministry-stat-card";
export type { MinistryStatCardProps } from "./components/sovereign/ministry-stat-card";
export {
  ProvinceMap,
  ZIMBABWE_PROVINCES,
} from "./components/sovereign/province-map";
export type {
  ProvinceMapProps,
  ProvinceId,
  ProvinceDatum,
} from "./components/sovereign/province-map";

/* ─── Joyful (parent-web + student surfaces only) ─── */
export { KidButton } from "./components/joyful/kid-button";
export type { KidButtonProps } from "./components/joyful/kid-button";
export { JoyfulCard } from "./components/joyful/joyful-card";
export type { JoyfulCardProps } from "./components/joyful/joyful-card";
export { EmojiStatusPill } from "./components/joyful/emoji-status-pill";
export type { EmojiStatusPillProps, Status as EmojiStatus } from "./components/joyful/emoji-status-pill";
export { BigStat } from "./components/joyful/big-stat";
export type { BigStatProps } from "./components/joyful/big-stat";
export { IllustratedEmptyState } from "./components/joyful/illustrated-empty-state";
export type { IllustratedEmptyStateProps } from "./components/joyful/illustrated-empty-state";
export { AudioPlayButton } from "./components/joyful/audio-play-button";
export type { AudioPlayButtonProps } from "./components/joyful/audio-play-button";

/* ─── Audio manifest (joyful read-aloud) ─── */
export { AUDIO_MANIFEST, getClip } from "./assets/audio-manifest";
export type { AudioClip, SupportedLocale } from "./assets/audio-manifest";

/* ─── Exports (Excel / PDF — client-side, guest-mode safe) ─── */
export { ExportMenu } from "./components/export-menu";
export type { ExportMenuProps } from "./components/export-menu";
export {
    exportToXlsx,
    exportToPdf,
    exportReportCardPdf,
} from "./lib/export";
export type {
    ExportColumn,
    ExportOptions,
    ReportCardOptions,
    ReportCardSubject,
} from "./lib/export";



/* ─── Charts — Recharts wrappers (Phase 10 Q-001a; ADR 011) ─── */
/* Lightweight Recharts (~50KB gzipped) — safe to import directly.   */
export {
    LineChart,
    BarChart,
    PieChart,
    SparkLine,
    CHART_COLORS,
} from "./components/charts";
export type {
    LineChartProps,
    BarChartProps,
    PieChartProps,
    SparkLineProps,
    PieDatum,
} from "./components/charts";

/* ─── Heavy charts — ECharts wrappers (Phase 10 Q-001b; ADR 011) ─── */
/*                                                                    */
/* IMPORTANT (PH10-3): the components below pull ECharts (~600KB      */
/* gzipped). DO NOT import them via `@eduzim/ui` directly in any page */
/* that ships to a Lighthouse-budgeted bundle. Use `next/dynamic`:    */
/*                                                                    */
/*    import dynamic from "next/dynamic";                             */
/*    const Heatmap = dynamic(                                        */
/*      () => import("@eduzim/ui/echarts").then(m => m.Heatmap),      */
/*      { ssr: false, loading: () => <ChartSkeleton /> }              */
/*    );                                                              */
/*                                                                    */
/* The TYPE re-exports below are safe (types are erased at build      */
/* time). The runtime exports are intentionally NOT here — the heavy  */
/* path must go through `@eduzim/ui/echarts` so the bundler sees it   */
/* as a separately-loadable chunk.                                    */
/*                                                                    */
/* See `apps/admin-web/src/lib/lazy-charts.tsx` for the recommended   */
/* dynamic-import wrappers (built per-app to keep ESLint happy).      */
export type {
    HeatmapProps,
    HeatmapDatum,
    ZimbabweGeomapProps,
    GeomapDatum,
    SankeyProps,
    SankeyNode,
    SankeyLink,
} from "./components/charts/echarts";
