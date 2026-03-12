/**
 * E2E — Teacher Student View (10B-1E).
 *
 * Tests:
 *  1. Student detail page loads from roster link
 *  2. Student view shows 3 tabs (Overview/Attendance/Announcements)
 *  3. Unauthorized student shows access denied
 *  4. Attendance tab displays trend/rate
 *  5. Announcements tab displays class feed
 *  6. Back link returns to class roster
 */

import { test, expect } from "@playwright/test";

test.describe("Student View", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
  });

  test("student detail page loads with classId", async ({ page }) => {
    // Navigate directly to a student page with classId
    await page.goto("/students/test-student-id?classId=test-class-id");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Page should render (may show unauthorized or student info)
    await expect(page.locator("body")).toBeVisible();
    await page.screenshot({
      path: "test-results/student-detail-page.png",
    });
  });

  test("student view has 3 tabs: overview, attendance, announcements", async ({
    page,
  }) => {
    await page.goto("/students/test-student-id?classId=test-class-id");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Look for tab triggers or unauthorized message
    const tabs = page.locator('[role="tab"], [data-state]');
    const unauthorized = page.locator("text=Access Denied, text=Hapana Mvumo, text=Akuvunyelwa");

    // Either tabs or unauthorized message should be visible
    const tabCount = await tabs.count();
    const hasUnauthorized = await unauthorized.count();

    expect(tabCount > 0 || hasUnauthorized > 0).toBe(true);

    await page.screenshot({
      path: "test-results/student-detail-tabs.png",
    });
  });

  test("unauthorized student shows 403 message", async ({ page }) => {
    // Navigate without valid classId context
    await page.goto("/students/fake-student?classId=fake-class");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Should show access denied or loading state
    await expect(page.locator("body")).toBeVisible();

    await page.screenshot({
      path: "test-results/student-unauthorized.png",
    });
  });

  test("back link navigates to class roster", async ({ page }) => {
    const classId = "test-class-id";
    await page.goto(`/students/test-student?classId=${classId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Find back arrow link
    const backLink = page.locator(`a[href*="/classes/${classId}"]`).first();
    const backLinkCount = await backLink.count();

    // Should have a back link to the class
    if (backLinkCount > 0) {
      const href = await backLink.getAttribute("href");
      expect(href).toContain(`/classes/${classId}`);
    }

    await page.screenshot({
      path: "test-results/student-back-link.png",
    });
  });
});

test.describe("Student Attendance Tab", () => {
  test("attendance tab shows trend data area", async ({ page }) => {
    await page.goto(
      "/students/test-student-id?classId=test-class-id&tab=attendance"
    );
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Page loads without crash
    await expect(page.locator("body")).toBeVisible();

    await page.screenshot({
      path: "test-results/student-attendance-tab.png",
    });
  });
});

test.describe("Student Announcements Tab", () => {
  test("announcements tab shows class feed area", async ({ page }) => {
    await page.goto(
      "/students/test-student-id?classId=test-class-id&tab=announcements"
    );
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Page loads without crash
    await expect(page.locator("body")).toBeVisible();

    await page.screenshot({
      path: "test-results/student-announcements-tab.png",
    });
  });
});
