/**
 * Admin-web — Unit Tests for 10A-8 (Reports UI)
 *
 * Covers:
 *  ✅ API client reports methods (dashboard, attendanceTrend, financialSummary)
 *  ✅ i18n reports keys in all locales
 *  ✅ Reports page content assertions
 *  ✅ API client type definitions
 *  ✅ Nav config has Reports
 */

import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client reports methods ───

import { reportsApi } from "@eduzim/api-client";

describe("API client — reports methods", () => {
    const mockClient = {
        get: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: null }),
    };

    const api = reportsApi(mockClient as any);

    it("has dashboard method", () => {
        expect(typeof api.dashboard).toBe("function");
    });

    it("has attendanceTrend method", () => {
        expect(typeof api.attendanceTrend).toBe("function");
    });

    it("has financialSummary method", () => {
        expect(typeof api.financialSummary).toBe("function");
    });

    it("dashboard calls GET /api/v1/reports/dashboard", async () => {
        await api.dashboard();
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/reports/dashboard");
    });

    it("attendanceTrend calls GET /api/v1/reports/attendance/trend", async () => {
        mockClient.get.mockClear();
        await api.attendanceTrend({ from: "2025-01-01", to: "2025-01-07" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/reports/attendance/trend",
            { from: "2025-01-01", to: "2025-01-07" },
        );
    });

    it("financialSummary calls GET /api/v1/reports/financial/summary", async () => {
        mockClient.get.mockClear();
        await api.financialSummary({ year_id: "y-1" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/reports/financial/summary",
            { year_id: "y-1" },
        );
    });
});

// ─── 2. i18n — reports keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — reports keys", () => {
    const requiredKeys = [
        "title", "dashboard", "schoolWide",
        "totalStudents", "activeStudents", "attendanceToday",
        "outstandingFees", "collectedThisTerm", "announcementsThisMonth",
        "attendanceTrend", "financialSummary",
        "last7Days", "last30Days",
        "present", "absent", "late", "rate",
        "totalInvoiced", "totalPaid", "totalOutstanding", "collectionRate",
        "noData", "noDataDescription", "date",
        "scopeSchool", "scopeClass", "selectAcademicYear",
    ];

    it("en.json has reports section with all required keys", () => {
        const keys = Object.keys((enMessages as any).reports || {});
        for (const k of requiredKeys) {
            expect(keys).toContain(k);
        }
    });

    it("sn.json has reports section with matching keys", () => {
        expect((snMessages as any).reports).toBeDefined();
        const keys = Object.keys((snMessages as any).reports);
        const enKeys = Object.keys((enMessages as any).reports);
        expect(keys).toEqual(enKeys);
    });

    it("nd.json has reports section with matching keys", () => {
        expect((ndMessages as any).reports).toBeDefined();
        const keys = Object.keys((ndMessages as any).reports);
        const enKeys = Object.keys((enMessages as any).reports);
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

// ─── 3. Reports page content ───

describe("Reports page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/reports/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with report:read permission", () => {
        expect(src).toContain('permissions={["report:read"]}');
    });

    it("has KPI cards for key metrics", () => {
        expect(src).toContain("totalStudents");
        expect(src).toContain("attendanceToday");
        expect(src).toContain("outstandingFees");
        expect(src).toContain("collectedThisTerm");
        expect(src).toContain("announcementsThisMonth");
    });

    it("uses KpiCard components", () => {
        expect(src).toContain("KpiCard");
    });

    it("has attendance trend section with toggle", () => {
        expect(src).toContain("attendanceTrend");
        expect(src).toContain("trendRange");
        expect(src).toContain("last7Days");
        expect(src).toContain("last30Days");
    });

    it("shows attendance columns: date, present, absent, late, rate", () => {
        expect(src).toContain("d.present");
        expect(src).toContain("d.absent");
        expect(src).toContain("d.late");
        expect(src).toContain("d.rate");
    });

    it("has financial summary section", () => {
        expect(src).toContain("financialSummary");
        expect(src).toContain("f.total_invoiced");
        expect(src).toContain("f.total_paid");
        expect(src).toContain("f.total_outstanding");
    });

    it("calculates collection rate", () => {
        expect(src).toContain("colRate");
    });

    it("has credible empty states when no data", () => {
        expect(src).toContain("noData");
        expect(src).toContain("noDataDescription");
    });

    it("uses loading skeletons", () => {
        expect(src).toContain("animate-pulse");
    });

    it("uses reports API methods", () => {
        expect(src).toContain("reports.dashboard");
        expect(src).toContain("reports.attendanceTrend");
        expect(src).toContain("reports.financialSummary");
    });

    it("uses i18n translations", () => {
        expect(src).toContain('useTranslations("reports")');
    });

    it("defaults to school-wide scope", () => {
        expect(src).toContain("schoolWide");
    });

    it("color-codes attendance rates", () => {
        expect(src).toContain("text-green-600");
        expect(src).toContain("text-red-600");
        expect(src).toContain("text-amber-600");
    });
});

// ─── 4. API client types ───

describe("API client — report type shape", () => {
    it("DashboardData has correct fields", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: {
                    total_students: 100, active_students: 95, total_enrollments: 100,
                    attendance_today_rate: 85.5, outstanding_fees: 5000,
                    collected_this_term: 15000, announcements_this_month: 3,
                },
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.dashboard();
        expect(result.data.total_students).toBe(100);
        expect(result.data.attendance_today_rate).toBe(85.5);
        expect(result.data.outstanding_fees).toBe(5000);
        expect(result.data.collected_this_term).toBe(15000);
    });

    it("AttendanceTrendPoint has correct fields", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    date: "2025-01-01", present: 80, absent: 10,
                    late: 5, total: 95, rate: 84.2,
                }],
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.attendanceTrend({ from: "2025-01-01", to: "2025-01-07" });
        expect(result.data[0].rate).toBe(84.2);
        expect(result.data[0].present).toBe(80);
    });

    it("FinancialSummaryData has correct fields", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    academic_year_id: "y-1", total_invoiced: 50000,
                    total_paid: 30000, total_outstanding: 20000,
                }],
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.financialSummary();
        expect(result.data[0].total_outstanding).toBe(20000);
    });
});

// ─── 5. Nav — Reports ───

import { adminNav } from "../src/lib/nav";

describe("Nav config — Reports", () => {
    it("Intelligence section has Reports child", () => {
        const intel = adminNav.find((n) => n.title === "Intelligence");
        expect(intel).toBeDefined();
        const childTitles = intel?.children?.map((c) => c.title) ?? [];
        expect(childTitles).toContain("Reports");
    });

    it("Reports links to /reports with report:read", () => {
        const intel = adminNav.find((n) => n.title === "Intelligence");
        const item = intel?.children?.find((c) => c.title === "Reports");
        expect(item?.href).toBe("/reports");
        expect(item?.permission).toBe("report:read");
    });
});
