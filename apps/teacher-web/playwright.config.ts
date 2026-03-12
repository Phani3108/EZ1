import { defineConfig } from "@playwright/test";

/**
 * Playwright E2E config — Teacher-web 10B test harness
 *
 * Screenshots : captured on every explicit step
 * Trace       : recorded on first retry
 * Video       : recorded on first retry
 * Report      : HTML saved to playwright-report/
 * Artifacts   : screenshots, traces, videos → test-results/
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 1,

  reporter: [["html", { open: "never", outputFolder: "playwright-report" }]],

  use: {
    baseURL: "http://localhost:3002",
    headless: true,
    screenshot: "on",
    trace: "on-first-retry",
    video: "on-first-retry",
  },

  outputDir: "test-results",

  webServer: {
    command: "pnpm run dev",
    port: 3002,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
