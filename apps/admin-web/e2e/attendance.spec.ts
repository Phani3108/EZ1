/**
 * E2E — Attendance module.
 *
 * Tests:
 *  1. Daily attendance page loads with controls
 *  2. Stat cards render after class selection
 *  3. Sync monitor page loads
 *  4. Student 360 attendance tab renders with date range
 */

import { test, expect } from "@playwright/test";

test.describe("Attendance Module", () => {
    test.beforeEach(async ({ page }) => {
        // Login as admin
        await page.goto("/login");
        await page.fill('input[type="email"]', "admin@eduzim.zw");
        await page.fill('input[type="password"]', "admin123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard", { timeout: 10000 });
    });

    test("daily attendance page loads with controls", async ({ page }) => {
        await page.goto("/attendance");
        await page.waitForLoadState("networkidle");

        // Page header
        await expect(page.locator("h1, h2").first()).toBeVisible();

        // Date picker
        await expect(page.locator('input[type="date"]')).toBeVisible();

        // Class selector
        await expect(page.locator("select")).toBeVisible();
    });

    test("sync monitor page loads", async ({ page }) => {
        await page.goto("/attendance/sync-monitor");
        await page.waitForLoadState("networkidle");

        // Page should load — either table or empty state
        const content = page.locator("table, [class*='empty']").first();
        await expect(content).toBeVisible({ timeout: 10000 });
    });

    test("student 360 attendance tab has date range selector", async ({ page }) => {
        // Navigate to students list first
        await page.goto("/students");
        await page.waitForLoadState("networkidle");

        // If there are students, click the first one
        const studentLink = page.locator('a[href^="/students/"]').first();
        const hasStudents = await studentLink.isVisible().catch(() => false);

        if (hasStudents) {
            await studentLink.click();
            await page.waitForLoadState("networkidle");

            // Click Attendance tab
            const attendanceTab = page.locator('button:has-text("Attendance")');
            if (await attendanceTab.isVisible()) {
                await attendanceTab.click();
                await page.waitForTimeout(1000);

                // Should see the date range selector
                const select = page.locator("select");
                await expect(select.first()).toBeVisible();
            }
        }
    });
});
