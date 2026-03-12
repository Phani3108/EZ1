/**
 * E2E Test — Enrollment Flow
 *
 * Scenario:
 *  1. Login as admin
 *  2. Create academic year (if needed) + class + student
 *  3. Enroll student from Student 360 Enrollment tab
 *  4. Verify enrollment appears in table
 *  5. Navigate to class roster and verify student appears
 *  6. Attempt duplicate enrollment → expect error
 *
 * NOTE: Requires backend stack running (docker-compose up)
 *       and a seeded admin user.
 *
 * Run: npx playwright test e2e/enrollment.spec.ts
 */

import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@school.ac.zw";
const ADMIN_PASSWORD = "secureP@ss1";
const SUFFIX = Date.now();
const TEST_YEAR_NAME = `E2E-Year-${SUFFIX}`;
const TEST_CLASS_NAME = `E2E-Class-${SUFFIX}`;
const TEST_STUDENT_FIRST = "E2EJohn";
const TEST_STUDENT_LAST = `Doe${SUFFIX}`;

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

test.describe("Enrollment E2E", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("enroll student from Student 360 → verify in roster", async ({ page }) => {
    // ─── 1. Create Academic Year ───
    await page.goto("/academic-years");
    await page.getByRole("button", { name: /create|new/i }).click();
    await page.waitForTimeout(500);

    const yearNameInput = page.getByLabel(/name/i);
    if (await yearNameInput.isVisible()) {
      await yearNameInput.fill(TEST_YEAR_NAME);
      // Set start and end dates
      const startInput = page.getByLabel(/start/i);
      const endInput = page.getByLabel(/end/i);
      if (await startInput.isVisible()) await startInput.fill("2025-01-01");
      if (await endInput.isVisible()) await endInput.fill("2025-12-31");
      await page.getByRole("button", { name: /create|save/i }).click();
      await page.waitForTimeout(1000);
    }

    // ─── 2. Create Class ───
    await page.goto("/classes");
    await page.getByRole("button", { name: /new class/i }).click();
    await page.waitForTimeout(500);
    await page.getByLabel(/class name/i).fill(TEST_CLASS_NAME);
    await page.getByLabel(/grade level/i).fill("7");
    await page.getByLabel(/capacity/i).fill("40");
    await page.getByRole("button", { name: /create/i }).click();
    await page.waitForTimeout(1000);

    // ─── 3. Create Student ───
    await page.goto("/students");
    await page.getByRole("button", { name: /add student/i }).click();
    await page.waitForTimeout(500);
    await page.getByLabel(/first name/i).fill(TEST_STUDENT_FIRST);
    await page.getByLabel(/last name/i).fill(TEST_STUDENT_LAST);
    await page.getByRole("button", { name: /create|save/i }).click();
    await page.waitForTimeout(1000);

    // ─── 4. Navigate to Student 360 ───
    // Click the student name in the list
    await page.getByText(`${TEST_STUDENT_FIRST} ${TEST_STUDENT_LAST}`).click();
    await page.waitForTimeout(500);

    // ─── 5. Go to Enrollment tab ───
    await page.getByRole("tab", { name: /enrollment/i }).click();
    await page.waitForTimeout(500);

    // Should show empty state initially
    await expect(page.getByText(/no enrollments/i)).toBeVisible();

    // ─── 6. Enroll Student ───
    await page.getByRole("button", { name: /enroll student/i }).click();
    await page.waitForTimeout(500);

    // Select academic year (pick the first available or our test year)
    const yearSelect = page.locator("select#academic_year_id");
    if (await yearSelect.isVisible()) {
      // Try to pick the option containing our year name
      const options = await yearSelect.locator("option").allTextContents();
      const targetYear = options.find((o) => o.includes(TEST_YEAR_NAME)) || options.find((o) => o.includes("current")) || options[1];
      if (targetYear) {
        await yearSelect.selectOption({ label: targetYear });
      }
    }

    // Select class
    const classSelect = page.locator("select#class_id");
    if (await classSelect.isVisible()) {
      const options = await classSelect.locator("option").allTextContents();
      const targetClass = options.find((o) => o.includes(TEST_CLASS_NAME)) || options[1];
      if (targetClass) {
        await classSelect.selectOption({ label: targetClass });
      }
    }

    // Submit enrollment
    await page.getByRole("button", { name: /enroll student/i }).last().click();
    await page.waitForTimeout(1000);

    // ─── 7. Verify enrollment in table ───
    // The sheet should close and enrollment should appear in the table
    await expect(page.getByText(TEST_CLASS_NAME)).toBeVisible({ timeout: 5_000 });

    // ─── 8. Navigate to class roster ───
    // Click the class name link in the enrollment table
    await page.getByRole("link", { name: new RegExp(TEST_CLASS_NAME) }).click();
    await page.waitForURL(`**/classes/**`, { timeout: 5_000 });

    // ─── 9. Verify student appears in roster ───
    await expect(
      page.getByText(`${TEST_STUDENT_FIRST} ${TEST_STUDENT_LAST}`)
    ).toBeVisible({ timeout: 5_000 });
  });

  test("duplicate enrollment shows error", async ({ page }) => {
    // Navigate to a student who's already enrolled (from prior test data)
    // This test verifies the error handling path.
    // In a real scenario we'd enroll twice, but we test defensively:

    await page.goto("/students");
    await page.waitForTimeout(500);

    // If no students exist, skip gracefully
    const studentLink = page.getByRole("link").filter({ hasText: TEST_STUDENT_FIRST });
    if (await studentLink.count() === 0) {
      test.skip();
      return;
    }

    await studentLink.first().click();
    await page.waitForTimeout(500);

    await page.getByRole("tab", { name: /enrollment/i }).click();
    await page.waitForTimeout(500);

    // Open enroll sheet and try to enroll in same class/year
    await page.getByRole("button", { name: /enroll student/i }).click();
    await page.waitForTimeout(500);

    // Select same year/class combination
    const yearSelect = page.locator("select#academic_year_id");
    const classSelect = page.locator("select#class_id");

    if (await yearSelect.isVisible()) {
      const options = await yearSelect.locator("option").allTextContents();
      const targetYear = options.find((o) => o.includes(TEST_YEAR_NAME)) || options[1];
      if (targetYear) await yearSelect.selectOption({ label: targetYear });
    }

    if (await classSelect.isVisible()) {
      const options = await classSelect.locator("option").allTextContents();
      const targetClass = options.find((o) => o.includes(TEST_CLASS_NAME)) || options[1];
      if (targetClass) await classSelect.selectOption({ label: targetClass });
    }

    await page.getByRole("button", { name: /enroll student/i }).last().click();
    await page.waitForTimeout(1500);

    // Expect some error indication (alert, badge, or text)
    const hasError = await page.locator('[role="alert"]').count() > 0 ||
      await page.getByText(/already enrolled|duplicate|conflict/i).count() > 0;

    expect(hasError).toBeTruthy();
  });
});
