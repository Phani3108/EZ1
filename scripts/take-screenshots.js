/**
 * EduZim Screenshot Script
 * Takes 10-12 screenshots per portal for README carousel.
 * Run: node scripts/take-screenshots.js
 */

const { chromium } = require("/Users/phani.m/Downloads/EduZim-main/node_modules/.pnpm/playwright-core@1.58.2/node_modules/playwright-core");
const path = require("path");
const fs = require("fs");

const OUT_DIR = path.join(__dirname, "..", "docs", "screenshots");
fs.mkdirSync(OUT_DIR, { recursive: true });

const CREDS = {
  admin:   { email: "admin@eduzim.com",   password: "123456", port: 3000, prefix: "admin" },
  parent:  { email: "parent@eduzim.com",  password: "123456", port: 3001, prefix: "parent" },
  teacher: { email: "teacher@eduzim.com", password: "123456", port: 3002, prefix: "teacher" },
};

async function login(page, base, email, password) {
  await page.goto(`${base}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  // Fill credentials (fields are pre-filled but let's be explicit)
  const emailInput = page.locator('input[type="email"], input[name="email"]').first();
  const passInput  = page.locator('input[type="password"]').first();
  await emailInput.fill(email);
  await passInput.fill(password);
}

async function shot(page, name, prefix) {
  await page.waitForTimeout(1200);
  const file = path.join(OUT_DIR, `${prefix}-${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  console.log(`  ✓ ${prefix}-${name}.png`);
  return `docs/screenshots/${prefix}-${name}.png`;
}

async function takeAdminScreenshots(browser) {
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  const base = "http://localhost:3000";
  const p = "admin";
  const files = [];

  console.log("\n📸 Admin Portal");

  // 1. Login page
  await page.goto(`${base}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  files.push(await shot(page, "01-login", p));

  // 2. Fill & submit login
  await login(page, base, CREDS.admin.email, CREDS.admin.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(`**/(dashboard|login)*`, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2000);
  files.push(await shot(page, "02-dashboard", p));

  // 3. Students list
  await page.goto(`${base}/students`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "03-students", p));

  // 4. Student detail
  const firstRow = page.locator("table tbody tr").first();
  const viewBtn = firstRow.locator("a, button").last();
  await viewBtn.click().catch(async () => {
    await page.goto(`${base}/students`, { waitUntil: "networkidle" });
  });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "04-student-detail", p));

  // 5. Attendance
  await page.goto(`${base}/attendance`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "05-attendance", p));

  // 6. Assessments
  await page.goto(`${base}/assessments`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "06-assessments", p));

  // 7. Fees / Invoices
  await page.goto(`${base}/fees/invoices`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "07-fees-invoices", p));

  // 8. Communication / Announcements
  await page.goto(`${base}/communication/announcements`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "08-announcements", p));

  // 9. Enrollments
  await page.goto(`${base}/enrollments`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "09-enrollments", p));

  // 10. Language switch (open switcher)
  await page.goto(`${base}/dashboard`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  // Try clicking the language button in the header
  const langBtn = page.locator('[aria-label*="lang"], button:has-text("EN"), button:has-text("Shona"), [data-testid="lang"]').first();
  await langBtn.click().catch(() => {});
  await page.waitForTimeout(800);
  files.push(await shot(page, "10-language-switch", p));

  // 11. Reports
  await page.goto(`${base}/reports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "11-reports", p));

  // 12. Students Import
  await page.goto(`${base}/students/import`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "12-import", p));

  await page.close();
  return files;
}

async function takeParentScreenshots(browser) {
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  const base = "http://localhost:3001";
  const p = "parent";
  const files = [];

  console.log("\n📸 Parent Portal");

  // 1. Login
  await page.goto(`${base}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  files.push(await shot(page, "01-login", p));

  // 2. Submit & land on home
  await login(page, base, CREDS.parent.email, CREDS.parent.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(`**/home*`, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2000);
  files.push(await shot(page, "02-home", p));

  // 3. Attendance calendar
  await page.goto(`${base}/attendance`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "03-attendance", p));

  // 4. Fees / invoices
  await page.goto(`${base}/fees`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "04-fees", p));

  // 5. Announcements feed
  await page.goto(`${base}/announcements`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "05-announcements", p));

  // 6. Language switch
  const langBtn = page.locator('[aria-label*="lang"], button:has-text("EN"), button:has-text("Shona"), [data-testid="lang"]').first();
  await langBtn.click().catch(() => {});
  await page.waitForTimeout(800);
  files.push(await shot(page, "06-language-switch", p));

  // 7. Home with Shona / after lang change
  await page.goto(`${base}/home`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "07-home-shona", p));

  // 8. My Children / profile section
  await page.goto(`${base}/home`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  // scroll down
  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(500);
  files.push(await shot(page, "08-home-scroll", p));

  await page.close();
  return files;
}

async function takeTeacherScreenshots(browser) {
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  const base = "http://localhost:3002";
  const p = "teacher";
  const files = [];

  console.log("\n📸 Teacher Portal");

  // 1. Login
  await page.goto(`${base}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  files.push(await shot(page, "01-login", p));

  // 2. Submit & land on today
  await login(page, base, CREDS.teacher.email, CREDS.teacher.password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(`**/today*`, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2000);
  files.push(await shot(page, "02-today", p));

  // 3. My Classes
  await page.goto(`${base}/classes`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "03-classes", p));

  // 4. Class detail — first class
  const classRow = page.locator("table tbody tr, [class*='card'], [class*='list'] > *").first();
  await classRow.click().catch(() => {});
  await page.waitForTimeout(1500);
  files.push(await shot(page, "04-class-detail", p));

  // 5. Announcements
  await page.goto(`${base}/announcements`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "05-announcements", p));

  // 6. Sync Center (offline queue)
  await page.goto(`${base}/sync-center`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "06-sync-center", p));

  // 7. Language switch
  await page.goto(`${base}/today`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const langBtn = page.locator('[aria-label*="lang"], button:has-text("EN"), button:has-text("Shona"), [data-testid="lang"]').first();
  await langBtn.click().catch(() => {});
  await page.waitForTimeout(800);
  files.push(await shot(page, "07-language-switch", p));

  // 8. Today with Shona UI
  await page.goto(`${base}/today`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  files.push(await shot(page, "08-today-shona", p));

  // 9. Student detail
  await page.goto(`${base}/classes`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  files.push(await shot(page, "09-classes-list", p));

  await page.close();
  return files;
}

(async () => {
  console.log("🚀 Launching EduZim Screenshot Runner...");
  const browser = await chromium.launch({ headless: true });

  try {
    const adminFiles   = await takeAdminScreenshots(browser);
    const parentFiles  = await takeParentScreenshots(browser);
    const teacherFiles = await takeTeacherScreenshots(browser);

    const manifest = { admin: adminFiles, parent: parentFiles, teacher: teacherFiles };
    fs.writeFileSync(
      path.join(OUT_DIR, "manifest.json"),
      JSON.stringify(manifest, null, 2),
    );

    console.log(`\n✅ Done! ${adminFiles.length + parentFiles.length + teacherFiles.length} screenshots saved to docs/screenshots/`);
  } catch (err) {
    console.error("Error:", err);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
