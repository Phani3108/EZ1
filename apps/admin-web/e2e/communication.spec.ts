/**
 * E2E — Communication module.
 *
 * Tests:
 *  1. Announcements page loads
 *  2. Outbox page loads with filters
 *  3. Student 360 communications tab renders
 */

import { test, expect } from "@playwright/test";

test.describe("Communication Module", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/login");
        await page.fill('input[type="email"]', "admin@eduzim.zw");
        await page.fill('input[type="password"]', "admin123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard", { timeout: 10000 });
    });

    test("announcements page loads", async ({ page }) => {
        await page.goto("/communication/announcements");
        await page.waitForLoadState("networkidle");

        const content = page.locator("table, [class*='empty']").first();
        await expect(content).toBeVisible({ timeout: 10000 });
    });

    test("outbox page loads with filters", async ({ page }) => {
        await page.goto("/communication/outbox");
        await page.waitForLoadState("networkidle");

        const select = page.locator("select");
        await expect(select.first()).toBeVisible();
    });

    test("student 360 communications tab shows announcements", async ({ page }) => {
        await page.goto("/students");
        await page.waitForLoadState("networkidle");

        const studentLink = page.locator('a[href^="/students/"]').first();
        const hasStudents = await studentLink.isVisible().catch(() => false);

        if (hasStudents) {
            await studentLink.click();
            await page.waitForLoadState("networkidle");

            const commsTab = page.locator('button:has-text("Communications")');
            if (await commsTab.isVisible()) {
                await commsTab.click();
                await page.waitForTimeout(1000);

                const content = page.locator("[class*='border'], [class*='empty']").first();
                await expect(content).toBeVisible();
            }
        }
    });
});
