import { defineConfig } from "@playwright/test";

/**
 * Playwright E2E config — 10A test harness
 *
 * Screenshots : captured on every explicit step
 * Trace       : recorded on first retry (open with `npx playwright show-trace`)
 * Video       : recorded on first retry (keeps failed-run video)
 * Report      : HTML saved to playwright-report/
 * Artifacts   : screenshots, traces, videos → test-results/
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 1,

  /* ── Reporter ── */
  reporter: [["html", { open: "never", outputFolder: "playwright-report" }]],

  /* ── Shared browser options ── */
  use: {
    baseURL: "http://localhost:3000",
    headless: true,

    /* Screenshot on every test step (explicit calls to page.goto, click, etc.) */
    screenshot: "on",

    /* Trace on first retry — captures DOM snapshots, network, console */
    trace: "on-first-retry",

    /* Video on first retry — keeps recording for failed runs */
    video: "on-first-retry",
  },

  /* ── Artifact output ── */
  outputDir: "test-results",

  webServer: {
    command: "pnpm run dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
