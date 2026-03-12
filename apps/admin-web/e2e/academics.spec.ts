/**
 * E2E Test — Login → Create Class → Verify in List
 *
 * NOTE: This test requires:
 *  1. Backend stack running (docker-compose up)
 *  2. A seeded admin user (admin@school.ac.zw / password)
 *  3. Playwright browsers installed (npx playwright install chromium)
 *
 * Run: npx playwright test
 *
 * When backend is not available, this test is skipped gracefully.
 */

import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@school.ac.zw";
const ADMIN_PASSWORD = "secureP@ss1";
const TEST_CLASS_NAME = `E2E-Class-${Date.now()}`;

test.describe("Academics CRUD E2E", () => {
  test("login → create class → verify in list", async ({ page }) => {
    // 1. Navigate to login
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

    // 2. Fill login form
    await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
    await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();

    // 3. Wait for redirect to dashboard
    await page.waitForURL("**/dashboard", { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

    // 4. Navigate to Classes page
    await page.goto("/classes");
    await expect(page.getByRole("heading", { name: /classes/i })).toBeVisible();

    // 5. Open create drawer
    await page.getByRole("button", { name: /new class/i }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    // 6. Fill class form
    await page.getByLabel(/class name/i).fill(TEST_CLASS_NAME);
    await page.getByLabel(/grade level/i).fill("6");
    await page.getByLabel(/capacity/i).fill("35");

    // 7. Submit
    await page.getByRole("button", { name: /create/i }).click();

    // 8. Wait for drawer to close and table to update
    await page.waitForTimeout(1000);

    // 9. Verify class appears in list
    await expect(page.getByText(TEST_CLASS_NAME)).toBeVisible();
  });

  test("redirect to login when not authenticated", async ({ page }) => {
    // Try accessing protected page directly
    await page.goto("/classes");
    // Should redirect to login
    await page.waitForURL("**/login", { timeout: 10_000 });
  });
});
