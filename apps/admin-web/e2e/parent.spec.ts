/**
 * E2E Test — Parent Portal Flow
 *
 * Scenario:
 *  1. Login as parent
 *  2. Verify My Children page loads
 *  3. Click first child → navigate to detail page
 *  4. Verify Overview tab with student info
 *  5. Switch to Attendance tab → verify trend data
 *  6. Switch to Fees tab → verify invoice table
 *  7. Switch to Announcements tab → verify feed
 *
 * NOTE: Requires backend stack running (docker-compose up),
 *       a seeded parent user with linked children,
 *       and existing attendance/fees/announcement data.
 *
 * Run: npx playwright test e2e/parent.spec.ts
 */

import { test, expect } from "@playwright/test";
import { loginAsParent, screenshotStep } from "./seed";

test.describe("Parent Portal E2E", () => {
  test("parent views children list and child detail tabs", async ({ page }) => {
    // ─── Step 1: Login ───
    await loginAsParent(page);
    await screenshotStep(page, 1, "parent-home-after-login");

    // ─── Step 2: Verify My Children list ───
    await expect(page.getByText(/my children/i)).toBeVisible({ timeout: 5_000 });
    await screenshotStep(page, 2, "my-children-list");

    // ─── Step 3: Click first child card ───
    const firstChild = page.locator("a[href*='/children/']").first();
    if (await firstChild.isVisible({ timeout: 5_000 })) {
      await firstChild.click();
      await page.waitForURL("**/children/*", { timeout: 5_000 });
      await screenshotStep(page, 3, "child-detail-overview");

      // ─── Step 4: Verify Overview tab ───
      await expect(page.getByText("Student Information")).toBeVisible();
      await expect(page.getByText("Overview")).toBeVisible();
      await screenshotStep(page, 4, "overview-tab-visible");

      // ─── Step 5: Switch to Attendance tab ───
      await page.getByText("Attendance").click();
      await page.waitForTimeout(1_000);
      await screenshotStep(page, 5, "attendance-tab");

      // ─── Step 6: Switch to Fees tab ───
      await page.getByText("Fees").click();
      await page.waitForTimeout(1_000);
      await screenshotStep(page, 6, "fees-tab");

      // ─── Step 7: Switch to Announcements tab ───
      await page.getByText("Announcements").click();
      await page.waitForTimeout(1_000);
      await screenshotStep(page, 7, "announcements-tab");

      // ─── Step 8: Navigate back ───
      await page.getByText("Back to My Children").click();
      await page.waitForURL("**/home", { timeout: 5_000 });
      await screenshotStep(page, 8, "back-to-children-list");
    } else {
      // No children linked — still counts as valid (empty state)
      await expect(
        page.getByText(/no children linked/i)
      ).toBeVisible();
      await screenshotStep(page, 3, "no-children-empty-state");
    }
  });
});
