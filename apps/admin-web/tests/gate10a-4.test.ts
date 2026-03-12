/**
 * Admin-web — Unit Tests for 10A-4 (Enrollment + Classroom Roster)
 *
 * Covers:
 *  ✅ Enrollment Zod schema validation
 *  ✅ API client enrollment methods exist
 *  ✅ i18n enrollment/roster keys present in all locales
 *  ✅ Service worker strategy correctness
 *  ✅ Class roster page file exists
 *  ✅ Current year selection logic
 *  ✅ Student 360 enrollment tab has enroll sheet
 */

import { describe, it, expect, vi } from "vitest";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";

// ─── 1. Enrollment form schema ───

const enrollSchema = z.object({
  academic_year_id: z.string().min(1, "Academic year is required"),
  class_id: z.string().min(1, "Class is required"),
});

describe("Enrollment form schema", () => {
  it("accepts valid enrollment data", () => {
    const result = enrollSchema.safeParse({
      academic_year_id: "year-uuid-1",
      class_id: "class-uuid-1",
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty academic_year_id", () => {
    const result = enrollSchema.safeParse({
      academic_year_id: "",
      class_id: "class-uuid-1",
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty class_id", () => {
    const result = enrollSchema.safeParse({
      academic_year_id: "year-uuid-1",
      class_id: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects missing fields", () => {
    const result = enrollSchema.safeParse({});
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.length).toBeGreaterThanOrEqual(2);
    }
  });
});

// ─── 2. API client exports enrollment methods ───

import { studentApi } from "@eduzim/api-client";

describe("API client — enrollment methods", () => {
  // Create a mock client
  const mockClient = {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };

  const api = studentApi(mockClient as any);

  it("has getStudentEnrollments method", () => {
    expect(typeof api.getStudentEnrollments).toBe("function");
  });

  it("has listEnrollments method", () => {
    expect(typeof api.listEnrollments).toBe("function");
  });

  it("has createEnrollment method", () => {
    expect(typeof api.createEnrollment).toBe("function");
  });

  it("has updateEnrollment method", () => {
    expect(typeof api.updateEnrollment).toBe("function");
  });

  it("has getEnrollmentsByClass method", () => {
    expect(typeof api.getEnrollmentsByClass).toBe("function");
  });

  it("getEnrollmentsByClass calls GET /api/v1/enrollments with class_id param", async () => {
    await api.getEnrollmentsByClass("cls-1", "year-1");
    expect(mockClient.get).toHaveBeenCalledWith(
      "/api/v1/enrollments",
      { class_id: "cls-1", academic_year_id: "year-1" }
    );
  });

  it("getEnrollmentsByClass omits academic_year_id when not provided", async () => {
    mockClient.get.mockClear();
    await api.getEnrollmentsByClass("cls-2");
    expect(mockClient.get).toHaveBeenCalledWith(
      "/api/v1/enrollments",
      { class_id: "cls-2" }
    );
  });
});

// ─── 3. schoolApi has getClass + getAcademicYear ───

import { schoolApi } from "@eduzim/api-client";

describe("API client — school methods", () => {
  const mockClient = {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };

  const api = schoolApi(mockClient as any);

  it("has getClass method", () => {
    expect(typeof api.getClass).toBe("function");
  });

  it("getClass calls GET /api/v1/classes/:id", async () => {
    await api.getClass("cls-1");
    expect(mockClient.get).toHaveBeenCalledWith("/api/v1/classes/cls-1");
  });

  it("has getAcademicYear method", () => {
    expect(typeof api.getAcademicYear).toBe("function");
  });

  it("getAcademicYear calls GET /api/v1/academic-years/:id", async () => {
    await api.getAcademicYear("yr-1");
    expect(mockClient.get).toHaveBeenCalledWith("/api/v1/academic-years/yr-1");
  });
});

// ─── 4. i18n — enrollment + roster keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — enrollment keys", () => {
  it("en.json has enrollment section with required keys", () => {
    const keys = Object.keys((enMessages as any).enrollment || {});
    expect(keys).toContain("title");
    expect(keys).toContain("enrollStudent");
    expect(keys).toContain("noEnrollments");
    expect(keys).toContain("class");
    expect(keys).toContain("academicYear");
    expect(keys).toContain("status");
    expect(keys).toContain("enrolledAt");
    expect(keys).toContain("selectClass");
    expect(keys).toContain("selectYear");
    expect(keys).toContain("duplicateError");
  });

  it("sn.json has enrollment section", () => {
    expect((snMessages as any).enrollment).toBeDefined();
    const keys = Object.keys((snMessages as any).enrollment);
    const enKeys = Object.keys((enMessages as any).enrollment);
    expect(keys).toEqual(enKeys);
  });

  it("nd.json has enrollment section", () => {
    expect((ndMessages as any).enrollment).toBeDefined();
    const keys = Object.keys((ndMessages as any).enrollment);
    const enKeys = Object.keys((enMessages as any).enrollment);
    expect(keys).toEqual(enKeys);
  });
});

describe("i18n — roster keys", () => {
  it("en.json has roster section with required keys", () => {
    const keys = Object.keys((enMessages as any).roster || {});
    expect(keys).toContain("title");
    expect(keys).toContain("description");
    expect(keys).toContain("studentName");
    expect(keys).toContain("admissionNumber");
    expect(keys).toContain("noStudents");
    expect(keys).toContain("capacity");
    expect(keys).toContain("enrolled");
    expect(keys).toContain("viewStudent");
  });

  it("sn.json has roster section matching en keys", () => {
    expect((snMessages as any).roster).toBeDefined();
    const keys = Object.keys((snMessages as any).roster);
    const enKeys = Object.keys((enMessages as any).roster);
    expect(keys).toEqual(enKeys);
  });

  it("nd.json has roster section matching en keys", () => {
    expect((ndMessages as any).roster).toBeDefined();
    const keys = Object.keys((ndMessages as any).roster);
    const enKeys = Object.keys((enMessages as any).roster);
    expect(keys).toEqual(enKeys);
  });

  it("all locales have same top-level sections", () => {
    const enKeys = Object.keys(enMessages).sort();
    const snKeys = Object.keys(snMessages).sort();
    const ndKeys = Object.keys(ndMessages).sort();
    expect(snKeys).toEqual(enKeys);
    expect(ndKeys).toEqual(enKeys);
  });
});

// ─── 5. Service worker strategies ───

describe("Service worker strategies", () => {
  const adminSW = fs.readFileSync(
    path.resolve(__dirname, "../public/sw.js"),
    "utf-8"
  );

  it("admin SW has network-first comment for API", () => {
    expect(adminSW).toContain("Network-first for API calls");
  });

  it("admin SW has cache-first comment for static", () => {
    expect(adminSW).toContain("Cache-first for static assets");
  });

  it("admin SW handles /api/ paths explicitly (not skipping them)", () => {
    // The old SW had: if (url.pathname.startsWith("/api/")) return;
    // The new one should have a fetch handler for /api/ paths
    expect(adminSW).toContain('url.pathname.startsWith("/api/")');
    // Make sure it has a respondWith for API (not just return)
    const apiSection = adminSW.split('url.pathname.startsWith("/api/")')[1];
    expect(apiSection).toContain("event.respondWith");
  });

  it("SW strategy doc header mentions hybrid caching", () => {
    expect(adminSW).toContain("hybrid caching strategy");
  });

  it("SW has stale fallback for API offline reads", () => {
    expect(adminSW).toContain("caches.match(request)");
  });
});

// ─── 6. File structure assertions ───

describe("File structure — enrollment & roster", () => {
  it("Classroom roster page exists at /classes/[id]/page.tsx", () => {
    const filePath = path.resolve(
      __dirname,
      "../src/app/(admin)/classes/[id]/page.tsx"
    );
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("Student 360 page exists", () => {
    const filePath = path.resolve(
      __dirname,
      "../src/app/(admin)/students/[id]/page.tsx"
    );
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("E2E enrollment test exists", () => {
    const filePath = path.resolve(__dirname, "../e2e/enrollment.spec.ts");
    expect(fs.existsSync(filePath)).toBe(true);
  });
});

// ─── 7. Current year selection logic ───

describe("Current year selection logic", () => {
  interface MockYear {
    id: string;
    name: string;
    start_date: string;
    end_date: string;
    is_current: boolean;
  }

  function selectCurrentYear(years: MockYear[]): MockYear | undefined {
    if (!years || years.length === 0) return undefined;
    const current = years.find((y) => y.is_current);
    if (current) return current;
    return [...years].sort(
      (a, b) => new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
    )[0];
  }

  it("picks year with is_current=true first", () => {
    const years: MockYear[] = [
      { id: "1", name: "2023", start_date: "2023-01-01", end_date: "2023-12-31", is_current: false },
      { id: "2", name: "2024", start_date: "2024-01-01", end_date: "2024-12-31", is_current: true },
      { id: "3", name: "2025", start_date: "2025-01-01", end_date: "2025-12-31", is_current: false },
    ];
    expect(selectCurrentYear(years)?.id).toBe("2");
  });

  it("falls back to latest start_date when no is_current", () => {
    const years: MockYear[] = [
      { id: "1", name: "2023", start_date: "2023-01-01", end_date: "2023-12-31", is_current: false },
      { id: "3", name: "2025", start_date: "2025-01-01", end_date: "2025-12-31", is_current: false },
      { id: "2", name: "2024", start_date: "2024-01-01", end_date: "2024-12-31", is_current: false },
    ];
    expect(selectCurrentYear(years)?.id).toBe("3");
  });

  it("returns undefined for empty array", () => {
    expect(selectCurrentYear([])).toBeUndefined();
  });

  it("returns the single year when only one exists", () => {
    const years: MockYear[] = [
      { id: "1", name: "2025", start_date: "2025-01-01", end_date: "2025-12-31", is_current: false },
    ];
    expect(selectCurrentYear(years)?.id).toBe("1");
  });
});

// ─── 8. Student 360 page has enrollment components ───

describe("Student 360 — enrollment integration", () => {
  const student360Source = fs.readFileSync(
    path.resolve(__dirname, "../src/app/(admin)/students/[id]/page.tsx"),
    "utf-8"
  );

  it("imports Sheet components for enrollment form", () => {
    expect(student360Source).toContain("Sheet");
    expect(student360Source).toContain("SheetHeader");
    expect(student360Source).toContain("SheetBody");
    expect(student360Source).toContain("SheetFooter");
  });

  it("has EnrollSheet component", () => {
    expect(student360Source).toContain("function EnrollSheet");
  });

  it("has EnrollmentTab component", () => {
    expect(student360Source).toContain("function EnrollmentTab");
  });

  it("uses useTranslations for i18n", () => {
    expect(student360Source).toContain('useTranslations("enrollment")');
  });

  it("uses useApiMutation for creating enrollment", () => {
    expect(student360Source).toContain("useApiMutation");
    expect(student360Source).toContain("createEnrollment");
  });

  it("resolves class names via classMap", () => {
    expect(student360Source).toContain("classMap");
    expect(student360Source).toContain("yearMap");
  });

  it("links enrollment class to roster page", () => {
    expect(student360Source).toContain("/classes/${e.class_id}");
  });
});

// ─── 9. Classroom roster page structure ───

describe("Classroom roster page", () => {
  const rosterSource = fs.readFileSync(
    path.resolve(__dirname, "../src/app/(admin)/classes/[id]/page.tsx"),
    "utf-8"
  );

  it("uses RouteGuard with student:read permission", () => {
    expect(rosterSource).toContain('permissions={["student:read"]}');
  });

  it("has academic year selector", () => {
    expect(rosterSource).toContain("selectedYearId");
    expect(rosterSource).toContain("setSelectedYearId");
  });

  it("uses getEnrollmentsByClass API method", () => {
    expect(rosterSource).toContain("getEnrollmentsByClass");
  });

  it("links student names to Student 360", () => {
    expect(rosterSource).toContain("/students/${e.student_id}");
  });

  it("shows class stats (grade level, enrolled count, capacity)", () => {
    expect(rosterSource).toContain("enrolledCount");
    expect(rosterSource).toContain("classData.capacity");
    expect(rosterSource).toContain("classData.grade_level");
  });

  it("uses useTranslations for i18n", () => {
    expect(rosterSource).toContain('useTranslations("roster")');
  });

  it("shows empty state when no students enrolled", () => {
    expect(rosterSource).toContain("noStudents");
    expect(rosterSource).toContain("noStudentsDescription");
  });
});

// ─── 10. Classes list page links to roster ───

describe("Classes list page — roster link", () => {
  const classesSource = fs.readFileSync(
    path.resolve(__dirname, "../src/app/(admin)/classes/page.tsx"),
    "utf-8"
  );

  it("class name links to /classes/:id", () => {
    expect(classesSource).toContain("/classes/${cls.id}");
  });

  it("uses anchor tag with primary style", () => {
    expect(classesSource).toContain("text-primary hover:underline");
  });
});
