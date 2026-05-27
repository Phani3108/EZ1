# ADR 011 — Charts: Recharts for Daily Users, ECharts for Admin/Ministry

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: frontend, ux, ministry

## Context

The audit flagged that what the build calls "trends" are HTML tables with colored badges (see `apps/admin-web/src/app/(admin)/reports/page.tsx:174`). No charts library is present anywhere in the repo. For Ministry credibility, parental engagement, and teacher decision-making, real charts are needed.

Three options:

- A — Recharts (React-native, ~50KB gzipped, declarative, easy)
- B — Apache ECharts (heavier ~600KB, imperative, very capable: heatmaps, geomaps, sankey)
- C — visx (D3 with React ergonomics, lowest-level, max control)

## Decision

Use **both** Recharts and ECharts, split by use:

| Surface | Library | Reason |
|---|---|---|
| Parent-web (any chart) | Recharts | Light bundle for the most-loaded app; simple line/bar/pie is enough. |
| Teacher-web (gradebook, attendance trend) | Recharts | Same — speed and simplicity matter. |
| Admin-web — simple dashboards (per-class summaries) | Recharts | Consistent with teacher-web look. |
| Admin-web — complex roll-ups (school-wide heatmap, fee defaulter sankey) | ECharts, **lazy-loaded** | Power-user charts only. |
| Ministry-web (Phase 14) | ECharts | Heatmaps, Zimbabwe geomap, sankey — all standard ECharts strengths. |

A thin wrapper in `packages/ui/src/components/charts/` exposes a consistent prop API across both libraries, so a chart can be migrated between them without rewriting the call site.

## Consequences

### Positive
- Parent and teacher PWAs stay light. Recharts adds ~50KB to those bundles.
- Admin and Ministry get the visualisation language Ministry decision-makers expect (heatmaps, geomaps).
- ECharts is lazy-loaded via `next/dynamic` — only loaded on pages that use it.
- Single chart wrapper API → migration between libs is a one-file change.

### Negative
- Two libraries to track for updates.
- A developer must know which wrapper component renders via which library, in case fine-tuning is needed.

### Neutral
- If ECharts proves too heavy even lazy-loaded, visx or D3-native is a future option for the admin/Ministry surfaces.

## Implementation Notes

- Wrapper components (Phase 10 Q-001):
  - `<LineChart />`, `<BarChart />`, `<PieChart />`, `<SparkLine />` — Recharts backing.
  - `<Heatmap />`, `<Geomap region="zimbabwe" />`, `<Sankey />` — ECharts backing, lazy-loaded.
- All wrappers consume theme tokens (Phase 10 PH10-3 ensures consistency with `@eduzim/ui` palette).
- Bundle budget: main parent-web bundle must not grow by more than 80KB gzipped after Recharts adoption. ECharts must not appear in main bundles.
- Tests: assert chart elements exist (`getByRole('img')` or `getByLabel(...)`) — do not snapshot pixel output.

## Alternatives Considered

### Single library (Recharts only)
**Rejected.** Recharts can't do good geomaps, heatmaps, or sankey without considerable effort. Ministry visuals would suffer.

### Single library (ECharts only)
**Rejected.** Bundle cost everywhere is unjustified for the simple line/bar/pie cases.

### visx
**Rejected for v1.** Too low-level for our pace. May revisit if we need a chart no library does well.

## References

- Plan: §3 Debate 9 (resolved)
- Backlog: `task.md` §1 DEC-011, Phase 10
- Related ADRs: 004 (provider pattern doesn't apply — these are libraries we depend on, not vendor integrations)
