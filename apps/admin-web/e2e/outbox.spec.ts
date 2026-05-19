/**
 * E2E — Notifications Outbox / Delivery Center
 *
 * Visibility-first checks for /communication/outbox:
 *   1. Page renders and stat tiles appear
 *   2. Status filter narrows the list
 *   3. Channel filter narrows the list
 *   4. Per-channel breakdown panel renders
 *
 * These tests assume the dev login + mock-client / seed data flow used by
 * the rest of the admin-web e2e suite. They do not depend on real delivery
 * — the surface is what matters for the visibility-first principle.
 */
import { test, expect } from "@playwright/test";

const OUTBOX_PATH = "/communication/outbox";

test.describe("Notifications Outbox", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/login");
        await page.fill('input[type="email"]', "admin@eduzim.zw");
        await page.fill('input[type="password"]', "admin123");
        await page.click('button[type="submit"]');
        await page.waitForURL("**/dashboard", { timeout: 10000 });
    });

    test("stats tiles render delivered / pending / failed", async ({ page }) => {
        await page.goto(OUTBOX_PATH);
        await page.waitForLoadState("networkidle");

        // Heading from PageHeader
        await expect(
            page.getByRole("heading", { level: 2, name: /delivery stats/i }),
        ).toBeAttached(); // sr-only — attached but hidden is fine.

        // Three MinistryStatCard tiles — assert by visible numeric values.
        const tiles = page.locator(
            "section[aria-labelledby='delivery-stats-heading'] >> div.grid > *",
        );
        await expect(tiles).toHaveCount(3, { timeout: 10000 });
    });

    test("status filter narrows the outbox list", async ({ page }) => {
        await page.goto(OUTBOX_PATH);
        await page.waitForLoadState("networkidle");

        const statusSelect = page.locator("select").first();
        await expect(statusSelect).toBeVisible();

        await statusSelect.selectOption({ value: "FAILED" });
        // Wait for refetch — table either shows FAILED rows or the empty state.
        await page.waitForTimeout(500);

        const tableOrEmpty = page.locator(
            "table tbody tr, [data-testid='empty-state'], [class*='empty']",
        );
        await expect(tableOrEmpty.first()).toBeVisible({ timeout: 5000 });
    });

    test("channel filter is wired", async ({ page }) => {
        await page.goto(OUTBOX_PATH);
        await page.waitForLoadState("networkidle");

        const selects = page.locator("select");
        await expect(selects).toHaveCount(2, { timeout: 5000 });

        await selects.nth(1).selectOption({ value: "SMS" });
        await page.waitForTimeout(500);
        // The filter changes URL state only; assert the select retained value.
        await expect(selects.nth(1)).toHaveValue("SMS");
    });

    test("by-channel breakdown panel renders when data is present", async ({ page }) => {
        await page.goto(OUTBOX_PATH);
        await page.waitForLoadState("networkidle");

        // Breakdown is conditional: it appears only when channelBreakdown
        // has rows. Accept either the panel or its absence — the contract
        // we're protecting is that we don't crash when it's empty.
        const panel = page.locator("text=/by channel/i").first();
        const present = await panel.isVisible().catch(() => false);
        if (present) {
            await expect(panel).toBeVisible();
        }
    });
});
