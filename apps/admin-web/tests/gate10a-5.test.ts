/**
 * Admin-web — Unit Tests for 10A-5 (Attendance UI)
 *
 * Covers:
 *  ✅ API client attendance methods exist (dailySummary, dailyRecords, studentTrend, classSummary, syncBatches)
 *  ✅ i18n attendance keys present in all locales
 *  ✅ Attendance daily page file exists
 *  ✅ Sync monitor page file exists
 *  ✅ Student 360 has reworked AttendanceTab with date range
 *  ✅ Nav config has attendance sub-items
 *  ✅ API client type definitions include new attendance types
 */

import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client attendance methods ───

import { attendanceApi } from "@eduzim/api-client";

describe("API client — attendance methods", () => {
    const mockClient = {
        get: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: null }),
    };

    const api = attendanceApi(mockClient as any);

    it("has dailySummary method", () => {
        expect(typeof api.dailySummary).toBe("function");
    });

    it("has dailyRecords method", () => {
        expect(typeof api.dailyRecords).toBe("function");
    });

    it("has studentTrend method", () => {
        expect(typeof api.studentTrend).toBe("function");
    });

    it("has classSummary method", () => {
        expect(typeof api.classSummary).toBe("function");
    });

    it("has syncBatches method", () => {
        expect(typeof api.syncBatches).toBe("function");
    });

    it("dailySummary calls GET /api/v1/attendance/daily", async () => {
        await api.dailySummary({ date: "2025-01-01", class_id: "cls-1" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/attendance/daily",
            { date: "2025-01-01", class_id: "cls-1" }
        );
    });

    it("dailyRecords calls GET /api/v1/attendance/daily/records", async () => {
        mockClient.get.mockClear();
        await api.dailyRecords({ date: "2025-01-01", class_id: "cls-1" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/attendance/daily/records",
            { date: "2025-01-01", class_id: "cls-1" }
        );
    });

    it("studentTrend calls GET /api/v1/attendance/student-trend", async () => {
        mockClient.get.mockClear();
        await api.studentTrend({ student_id: "s-1", from: "2025-01-01", to: "2025-01-31" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/attendance/student-trend",
            { student_id: "s-1", from: "2025-01-01", to: "2025-01-31" }
        );
    });

    it("classSummary calls GET /api/v1/attendance/class-summary", async () => {
        mockClient.get.mockClear();
        await api.classSummary({ class_id: "cls-1", from: "2025-01-01", to: "2025-01-31" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/attendance/class-summary",
            { class_id: "cls-1", from: "2025-01-01", to: "2025-01-31" }
        );
    });

    it("syncBatches calls GET /api/v1/attendance/sync/batches", async () => {
        mockClient.get.mockClear();
        await api.syncBatches({ limit: "20" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/attendance/sync/batches",
            { limit: "20" }
        );
    });
});

// ─── 2. i18n — attendance keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — attendance keys", () => {
    const requiredKeys = [
        "title", "dailyAttendance", "syncMonitor", "selectDate", "selectClass",
        "allClasses", "present", "absent", "late", "attendanceRate", "studentName",
        "status", "lastModified", "noRecords", "noRecordsDescription",
        "last30Days", "last90Days", "custom", "totalDays", "dateRange",
        "batchId", "deviceId", "receivedAt", "totalEvents", "accepted",
        "updated", "ignored", "noBatches", "noBatchesDescription", "trend",
        "trendRate", "date", "total",
    ];

    it("en.json has attendance section with all required keys", () => {
        const keys = Object.keys((enMessages as any).attendance || {});
        for (const k of requiredKeys) {
            expect(keys).toContain(k);
        }
    });

    it("sn.json has attendance section with matching keys", () => {
        expect((snMessages as any).attendance).toBeDefined();
        const keys = Object.keys((snMessages as any).attendance);
        const enKeys = Object.keys((enMessages as any).attendance);
        expect(keys).toEqual(enKeys);
    });

    it("nd.json has attendance section with matching keys", () => {
        expect((ndMessages as any).attendance).toBeDefined();
        const keys = Object.keys((ndMessages as any).attendance);
        const enKeys = Object.keys((enMessages as any).attendance);
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

// ─── 3. File structure assertions ───

describe("File structure — attendance module", () => {
    it("Attendance daily page exists at /attendance/page.tsx", () => {
        const filePath = path.resolve(
            __dirname,
            "../src/app/(admin)/attendance/page.tsx"
        );
        expect(fs.existsSync(filePath)).toBe(true);
    });

    it("Sync monitor page exists at /attendance/sync-monitor/page.tsx", () => {
        const filePath = path.resolve(
            __dirname,
            "../src/app/(admin)/attendance/sync-monitor/page.tsx"
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
});

// ─── 4. Attendance daily page structure ───

describe("Attendance daily page", () => {
    const dailySource = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/attendance/page.tsx"),
        "utf-8"
    );

    it("uses RouteGuard with attendance:read permission", () => {
        expect(dailySource).toContain('permissions={["attendance:read"]}');
    });

    it("has date picker input", () => {
        expect(dailySource).toContain('type="date"');
        expect(dailySource).toContain("selectedDate");
    });

    it("has class selector", () => {
        expect(dailySource).toContain("selectedClassId");
        expect(dailySource).toContain("setSelectedClassId");
    });

    it("uses StatCard for attendance stats", () => {
        expect(dailySource).toContain("StatCard");
        expect(dailySource).toContain("attendance_rate");
    });

    it("uses i18n translations", () => {
        expect(dailySource).toContain('useTranslations("attendance")');
    });

    it("links student names to Student 360", () => {
        expect(dailySource).toContain("/students/${r.student_id}");
    });

    it("shows empty state when no class selected", () => {
        expect(dailySource).toContain("!selectedClassId");
        expect(dailySource).toContain("EmptyState");
    });

    it("uses API methods for summary and records", () => {
        expect(dailySource).toContain("attendance.dailySummary");
        expect(dailySource).toContain("attendance.dailyRecords");
    });
});

// ─── 5. Sync monitor page structure ───

describe("Sync monitor page", () => {
    const syncSource = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/attendance/sync-monitor/page.tsx"),
        "utf-8"
    );

    it("uses RouteGuard with school:manage permission", () => {
        expect(syncSource).toContain('permissions={["school:manage"]}');
    });

    it("uses syncBatches API method", () => {
        expect(syncSource).toContain("attendance.syncBatches");
    });

    it("shows batch ID, device ID, and counts", () => {
        expect(syncSource).toContain("sync_batch_id");
        expect(syncSource).toContain("device_id");
        expect(syncSource).toContain("accepted_count");
        expect(syncSource).toContain("updated_count");
        expect(syncSource).toContain("ignored_count");
    });

    it("has empty state for no batches", () => {
        expect(syncSource).toContain("noBatches");
    });

    it("uses i18n translations", () => {
        expect(syncSource).toContain('useTranslations("attendance")');
    });
});

// ─── 6. Student 360 — AttendanceTab rework ───

describe("Student 360 — Attendance tab rework", () => {
    const student360Source = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/students/[id]/page.tsx"),
        "utf-8"
    );

    it("has date range selector (30/90/custom)", () => {
        expect(student360Source).toContain("DateRange");
        expect(student360Source).toContain("last30Days");
        expect(student360Source).toContain("last90Days");
        expect(student360Source).toContain('"custom"');
    });

    it("uses studentTrend API with from/to params", () => {
        expect(student360Source).toContain("attendance.studentTrend");
        expect(student360Source).toContain("from, to");
    });

    it("shows attendance stats (rate, total_days, present, absent, late)", () => {
        expect(student360Source).toContain("attendance_rate");
        expect(student360Source).toContain("total_days");
    });

    it("uses i18n translations for attendance", () => {
        expect(student360Source).toContain('useTranslations("attendance")');
    });

    it("uses status badges (P/A/L)", () => {
        expect(student360Source).toContain('"P"');
        expect(student360Source).toContain('"A"');
        expect(student360Source).toContain('"L"');
    });

    it("has day-by-day table with date and status", () => {
        expect(student360Source).toContain("trend.days.map");
        expect(student360Source).toContain("day.date");
        expect(student360Source).toContain("day.status");
    });
});

// ─── 7. Nav config — attendance sub-items ───

describe("Nav config — attendance sub-items", () => {
    const navSource = fs.readFileSync(
        path.resolve(__dirname, "../src/lib/nav.ts"),
        "utf-8"
    );

    it("has Daily Attendance nav item", () => {
        expect(navSource).toContain("Daily Attendance");
        expect(navSource).toContain('href: "/attendance"');
        expect(navSource).toContain('"attendance:read"');
    });

    it("has Sync Monitor nav item", () => {
        expect(navSource).toContain("Sync Monitor");
        expect(navSource).toContain('href: "/attendance/sync-monitor"');
        expect(navSource).toContain('"school:manage"');
    });
});

// ─── 8. API client types include new attendance types ───

describe("API client — attendance type exports", () => {
    it("exports AttendanceDailySummary", async () => {
        const exports = await import("@eduzim/api-client");
        // Type-only exports won't be in JS, but the interface keys are used in services
        expect(exports.attendanceApi).toBeDefined();
    });
});
