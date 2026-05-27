# Charts bundle budget — verification runbook (PH10-3)

How to verify that ECharts has NOT leaked into the admin-web main
JS bundle.

## Why this matters

* Recharts (~50KB gzipped) is fine to ship in the main bundle — small.
* **ECharts (~600KB gzipped) is not.** Loading every admin page with
  ECharts in the critical path means every page gets a +600KB hit,
  even pages that don't render any heavy chart.
* The Phase 10 gate target: **main bundle increase < 100KB gzipped**
  on the admin-web reports page. ECharts must show up only in a
  separately-loadable chunk that's fetched when a heavy chart appears.

## How the codebase enforces this (today)

1. `@eduzim/ui` exposes ECharts wrappers via a **separate subpath**:
   `@eduzim/ui/echarts`. The main `@eduzim/ui` entry has type re-exports
   only.

2. Admin-web wraps every ECharts component in **`next/dynamic` with
   `ssr: false`**. Definitions live in
   `apps/admin-web/src/lib/lazy-charts.tsx`. Pages import from there,
   never directly from `@eduzim/ui/echarts`.

3. `package.json` lists `echarts` under **`optionalDependencies`** so
   `parent-web` and `teacher-web` don't pull it on install.

4. The internal wrapper (`packages/ui/src/components/charts/echarts/
   index.tsx`) registers ECharts components lazily via `await import(
   "echarts/core")` inside an effect — not at module top level — so a
   tree-shaker that loses the dynamic import still doesn't pull
   ECharts into a synchronous bundle.

## How to verify after a change

```bash
# Build admin-web for production
pnpm --filter admin-web build

# Look at the page-specific bundle sizes
# Next.js prints them on stdout — capture the table for /admin/reports
# and compare against the baseline. Example expected shape:
#
#   Route (app)                              Size     First Load JS
#   ┌ ƒ /admin/reports                       4.2 kB         95.1 kB
#   ├ chunks/echarts-XXXX.js                  640 kB    (separate chunk)
#
# The "First Load JS" column is what matters. It should not include
# any number close to 600 kB for reports.

# Inspect the chunk graph
pnpm --filter admin-web run analyze
# Opens the @next/bundle-analyzer treemap in a browser. ECharts should
# appear as a NAMED CHUNK (not as a node under "main" or "framework").

# Run Lighthouse against a deployed staging build
npx @lhci/cli@latest collect \
    --url=https://staging.eduzim.co.zw/admin/reports \
    --upload.target=temporary-public-storage
# Target: Performance score ≥ 90 on synthetic-throttled config.
```

## When a regression appears

Common ways ECharts ends up in the main bundle:

* **A page imports `@eduzim/ui/echarts` directly** instead of via
  `lazy-charts.tsx`. The bundler sees a sync import and includes the
  chunk in the page. Fix: route through `next/dynamic`.

* **`next/dynamic` is missing `ssr: false`**. Without it, Next.js
  attempts SSR, which forces the import to resolve at the server
  side — and the resulting chunk graph includes ECharts in the page's
  initial JS.

* **An eager `import { Heatmap } from "..."`** somewhere in the tree
  that the dynamic import path also depends on. Fix: search for any
  static reference to `Heatmap` / `ZimbabweGeomap` / `Sankey` outside
  of the `lazy-charts.tsx` file; they should not exist.

* **Tree-shaker can't prove the export is unused.** This happens when
  some other module re-exports `*` from the echarts entry. Fix: only
  re-export specific names from `@eduzim/ui/echarts`.

## Acceptance check (PH10-3 closure)

The Phase 10 gate is met when:

- [ ] `pnpm --filter admin-web build` reports a `/admin/reports`
      first-load JS of **< 350 kB** (this is the baseline + Recharts
      + the existing page deps; ECharts must not be in this number).
- [ ] The build output lists a separate chunk like
      `chunks/echarts-<hash>.js` that's > 500 kB. Its existence proves
      ECharts ships as its own file, not inlined.
- [ ] Lighthouse Performance on the reports page (synthetic-throttled
      profile) is ≥ 90.
- [ ] The chunk loads only when the page mounts a heavy-chart
      component, NOT on the page's initial navigation. Verify via
      Chrome DevTools Network tab while clicking around the page.

These checks can run only against a real Next.js build; this repo's
test suite covers the code paths, but the bundle posture is verified
post-build per the runbook above.
