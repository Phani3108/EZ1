/**
 * E2E Seed Helper — shared login + data creation utilities.
 *
 * Usage:
 *   import { loginAsAdmin, loginAsParent, uniqueSuffix } from "./seed";
 *
 * These helpers keep e2e specs DRY and ensure consistent
 * naming conventions for test data.
 */

import type { Page } from "@playwright/test";

// ─── Config ───

export const ADMIN_EMAIL = "admin@school.ac.zw";
export const ADMIN_PASSWORD = "secureP@ss1";
export const PARENT_EMAIL = "parent@school.ac.zw";
export const PARENT_PASSWORD = "secureP@ss1";

/**
 * Returns a unique suffix to prevent collisions across parallel test runs.
 */
export function uniqueSuffix(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

/**
 * Login as admin user. Waits for /dashboard redirect.
 */
export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

/**
 * Login as parent user. Waits for /home redirect.
 */
export async function loginAsParent(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(PARENT_EMAIL);
  await page.getByLabel(/password/i).fill(PARENT_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("**/home", { timeout: 10_000 });
}

/**
 * Take a named screenshot with consistent naming convention.
 * Screenshots go into the test-results/ folder automatically.
 *
 * Naming: step-{stepNumber}-{description}.png
 */
export async function screenshotStep(
  page: Page,
  stepNumber: number,
  description: string,
) {
  const name = `step-${String(stepNumber).padStart(2, "0")}-${description
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")}`;
  await page.screenshot({ path: `test-results/${name}.png`, fullPage: true });
}
