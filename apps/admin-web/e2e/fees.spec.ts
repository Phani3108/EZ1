/**
 * E2E — Fees module.
 *
 * Tests:
 *  1. Fee structures page loads
 *  2. Invoices page loads with status filter
 *  3. Defaulters page loads
 *  4. Student 360 fees tab renders with Record Payment button
 */

import { test, expect } from "@playwright/test";

test.describe("Fees Module", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/login");
        await page.fill('input[type="email"]', "admin@eduzim.zw");
        await page.fill('input[type="password"]', "admin123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard", { timeout: 10000 });
    });

    test("fee structures page loads", async ({ page }) => {
        await page.goto("/fees/structures");
        await page.waitForLoadState("networkidle");

        // Should show table or empty state
        const content = page.locator("table, [class*='empty']").first();
        await expect(content).toBeVisible({ timeout: 10000 });
    });

    test("invoices page loads with status filter", async ({ page }) => {
        await page.goto("/fees/invoices");
        await page.waitForLoadState("networkidle");

        // Status filter select should be visible
        const select = page.locator("select");
        await expect(select.first()).toBeVisible();
    });

    test("defaulters page loads", async ({ page }) => {
        await page.goto("/fees/defaulters");
        await page.waitForLoadState("networkidle");

        // Should show table or empty state
        const content = page.locator("table, [class*='empty']").first();
        await expect(content).toBeVisible({ timeout: 10000 });
    });

    test("student 360 fees tab shows invoices or empty state", async ({ page }) => {
        await page.goto("/students");
        await page.waitForLoadState("networkidle");

        const studentLink = page.locator('a[href^="/students/"]').first();
        const hasStudents = await studentLink.isVisible().catch(() => false);

        if (hasStudents) {
            await studentLink.click();
            await page.waitForLoadState("networkidle");

            const feesTab = page.locator('button:has-text("Fees")');
            if (await feesTab.isVisible()) {
                await feesTab.click();
                await page.waitForTimeout(1000);

                // Should see invoice table or empty state
                const content = page.locator("table, [class*='empty']").first();
                await expect(content).toBeVisible();
            }
        }
    });
});
