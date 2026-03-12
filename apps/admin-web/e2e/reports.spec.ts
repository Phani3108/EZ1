/**
 * E2E — Reports module.
 *
 * Tests:
 *  1. Reports dashboard loads with KPI cards
 *  2. Attendance trend section visible
 *  3. Financial summary section visible
 */

import { test, expect } from "@playwright/test";

test.describe("Reports Module", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/login");
        await page.fill('input[type="email"]', "admin@eduzim.zw");
        await page.fill('input[type="password"]', "admin123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard", { timeout: 10000 });
    });

    test("reports page loads with dashboard content", async ({ page }) => {
        await page.goto("/reports");
        await page.waitForLoadState("networkidle");

        // Should have KPI cards or loading state
        const content = page.locator("[class*='card'], [class*='animate-pulse']").first();
        await expect(content).toBeVisible({ timeout: 10000 });
    });

    test("attendance trend section is visible", async ({ page }) => {
        await page.goto("/reports");
        await page.waitForLoadState("networkidle");

        // Trend toggle buttons should be visible
        const trend = page.locator("text=Last 7 Days").first();
        await expect(trend).toBeVisible({ timeout: 10000 });
    });

    test("financial summary section is visible", async ({ page }) => {
        await page.goto("/reports");
        await page.waitForLoadState("networkidle");

        // Financial section should be visible
        const fin = page.locator("text=Financial Summary").first();
        await expect(fin).toBeVisible({ timeout: 10000 });
    });
});
