/**
 * Admin-web — Unit Tests for 10B-2 (Dropout Risk Monitor)
 *
 * Covers:
 *  ✅ API client dropout methods (dropoutSummary, dropoutStudents, dropoutStudentDetail)
 *  ✅ i18n dropout keys in all locales
 *  ✅ Dropout page content assertions
 *  ✅ Risk badge component
 *  ✅ Dropout drawer component
 *  ✅ Student 360 risk badge integration
 *  ✅ Nav config has Dropout Risk
 *  ✅ API client dropout type definitions
 */

import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client dropout methods ───

import { reportsApi } from "@eduzim/api-client";

describe("API client — dropout methods", () => {
    const mockClient = {
        get: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: null }),
    };

    const api = reportsApi(mockClient as any);

    it("has dropoutSummary method", () => {
        expect(typeof api.dropoutSummary).toBe("function");
    });

    it("has dropoutStudents method", () => {
        expect(typeof api.dropoutStudents).toBe("function");
    });

    it("has dropoutStudentDetail method", () => {
        expect(typeof api.dropoutStudentDetail).toBe("function");
    });

    it("dropoutSummary calls GET /api/v1/reports/dropout/summary", async () => {
        mockClient.get.mockClear();
        await api.dropoutSummary();
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/reports/dropout/summary");
    });

    it("dropoutStudents calls GET /api/v1/reports/dropout/students", async () => {
        mockClient.get.mockClear();
        await api.dropoutStudents();
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/reports/dropout/students",
            undefined,
        );
    });

    it("dropoutStudents passes filter params", async () => {
        mockClient.get.mockClear();
        await api.dropoutStudents({ band: "HIGH" });
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/reports/dropout/students",
            { band: "HIGH" },
        );
    });

    it("dropoutStudentDetail calls correct URL", async () => {
        mockClient.get.mockClear();
        await api.dropoutStudentDetail("s-123");
        expect(mockClient.get).toHaveBeenCalledWith(
            "/api/v1/reports/dropout/student/s-123",
        );
    });
});

// ─── 2. i18n — dropout keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — dropout keys", () => {
    const requiredKeys = [
        "title", "description",
        "totalStudents", "atRisk",
        "low", "medium", "high", "critical",
        "filterByBand", "all",
        "studentCode", "studentName",
        "riskScore", "riskBand", "signalCount", "primaryReason",
        "viewDetails", "page", "noStudents",
        "riskDetail", "riskDetailDescription",
        "computedAt", "signals", "noSignals", "lookbackDays",
        "signalsComputedFor", "primaryReason",
    ];

    it("en.json has dropout section with all required keys", () => {
        expect((enMessages as any).dropout).toBeDefined();
        const keys = Object.keys((enMessages as any).dropout);
        for (const k of requiredKeys) {
            expect(keys).toContain(k);
        }
    });

    it("sn.json has dropout section with matching keys", () => {
        expect((snMessages as any).dropout).toBeDefined();
        const keys = Object.keys((snMessages as any).dropout);
        const enKeys = Object.keys((enMessages as any).dropout);
        expect(keys).toEqual(enKeys);
    });

    it("nd.json has dropout section with matching keys", () => {
        expect((ndMessages as any).dropout).toBeDefined();
        const keys = Object.keys((ndMessages as any).dropout);
        const enKeys = Object.keys((enMessages as any).dropout);
        expect(keys).toEqual(enKeys);
    });

    it("all locales have same top-level sections", () => {
        const enKeys = Object.keys(enMessages).sort();
        const snKeys = Object.keys(snMessages).sort();
        const ndKeys = Object.keys(ndMessages).sort();
        expect(snKeys).toEqual(enKeys);
        expect(ndKeys).toEqual(enKeys);
    });

    it("nav has dropoutRisk key in all locales", () => {
        expect((enMessages as any).nav.dropoutRisk).toBeDefined();
        expect((snMessages as any).nav.dropoutRisk).toBeDefined();
        expect((ndMessages as any).nav.dropoutRisk).toBeDefined();
    });
});

// ─── 3. Dropout page content ───

describe("Dropout dashboard page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/intelligence/dropout/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with report:read permission", () => {
        expect(src).toContain('permissions={["report:read"]}');
    });

    it("has KPI cards for risk band breakdown", () => {
        expect(src).toContain("total_students");
        expect(src).toContain("at_risk_count");
        expect(src).toContain("LOW");
        expect(src).toContain("MEDIUM");
        expect(src).toContain("HIGH");
        expect(src).toContain("CRITICAL");
    });

    it("has band filter buttons", () => {
        expect(src).toContain("bandFilter");
        expect(src).toContain("setBandFilter");
    });

    it("has student risk table with expected columns", () => {
        expect(src).toContain("student_code");
        expect(src).toContain("risk_score");
        expect(src).toContain("risk_band");
        expect(src).toContain("signal_count");
        expect(src).toContain("top_signal");
        expect(src).toContain("primaryReason");
    });

    it("has lookback date range display", () => {
        expect(src).toContain('data-testid="lookback-range"');
        expect(src).toContain("signalsComputedFor");
        expect(src).toContain("CalendarRange");
    });

    it("uses RiskBadge component", () => {
        expect(src).toContain("RiskBadge");
    });

    it("uses DropoutDrawer for drilldown", () => {
        expect(src).toContain("DropoutDrawer");
    });

    it("has pagination controls", () => {
        expect(src).toContain("setPage");
        expect(src).toContain("pageSize");
    });

    it("uses reports API dropout methods", () => {
        expect(src).toContain("reports.dropoutSummary");
        expect(src).toContain("reports.dropoutStudents");
    });

    it("uses loading skeletons", () => {
        expect(src).toContain("animate-pulse");
    });
});

// ─── 4. Risk badge component ───

describe("Risk badge component", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/components/risk-badge.tsx"), "utf-8",
    );

    it("has data-testid risk-badge", () => {
        expect(src).toContain('data-testid="risk-badge"');
    });

    it("has data-band and data-score attributes", () => {
        expect(src).toContain("data-band={band}");
        expect(src).toContain("data-score={score}");
    });

    it("supports all 4 risk bands", () => {
        expect(src).toContain("LOW");
        expect(src).toContain("MEDIUM");
        expect(src).toContain("HIGH");
        expect(src).toContain("CRITICAL");
    });

    it("has colored dot indicator", () => {
        expect(src).toContain("bg-green-500");
        expect(src).toContain("bg-amber-500");
        expect(src).toContain("bg-orange-500");
        expect(src).toContain("bg-red-500");
    });

    it("supports sm and md sizes", () => {
        expect(src).toContain('"sm"');
        expect(src).toContain('"md"');
    });

    it("has optional onClick prop for interactivity", () => {
        expect(src).toContain("onClick");
        expect(src).toContain("cursor-pointer");
    });

    it("exports RiskScoreBar component", () => {
        expect(src).toContain("export function RiskScoreBar");
    });

    it("RiskScoreBar shows 0-100 scale", () => {
        expect(src).toContain("/100");
    });
});

// ─── 5. Dropout drawer component ───

describe("Dropout drawer component", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/components/dropout-drawer.tsx"), "utf-8",
    );

    it("exports DropoutDrawer component", () => {
        expect(src).toContain("export function DropoutDrawer");
    });

    it("fetches student detail from API", () => {
        expect(src).toContain("reports.dropoutStudentDetail");
    });

    it("shows RiskBadge in drawer", () => {
        expect(src).toContain("RiskBadge");
    });

    it("shows RiskScoreBar in drawer", () => {
        expect(src).toContain("RiskScoreBar");
    });

    it("displays signal cards", () => {
        expect(src).toContain("signal.label");
        expect(src).toContain("signal.points");
    });

    it("has signal icon mapping", () => {
        expect(src).toContain("CalendarX");
        expect(src).toContain("DollarSign");
    });

    it("uses onClose callback prop", () => {
        expect(src).toContain("onClose");
    });
});

// ─── 6. Student 360 integration ───

describe("Student 360 — risk badge integration", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/students/[id]/page.tsx"), "utf-8",
    );

    it("imports RiskBadge component", () => {
        expect(src).toContain("RiskBadge");
    });

    it("imports DropoutDrawer component", () => {
        expect(src).toContain("DropoutDrawer");
    });

    it("fetches dropout student detail", () => {
        expect(src).toContain("reports.dropoutStudentDetail");
    });

    it("has risk drawer open state", () => {
        expect(src).toContain("riskDrawerOpen");
    });

    it("toggles drawer on badge click", () => {
        expect(src).toContain("setRiskDrawerOpen");
    });
});

// ─── 7. Nav — Dropout Risk ───

import { adminNav } from "../src/lib/nav";

describe("Nav config — Dropout Risk", () => {
    it("Intelligence section has Dropout Risk child", () => {
        const intel = adminNav.find((n) => n.title === "Intelligence");
        expect(intel).toBeDefined();
        const childTitles = intel?.children?.map((c) => c.title) ?? [];
        expect(childTitles).toContain("Dropout Risk");
    });

    it("Dropout Risk links to /intelligence/dropout with report:read", () => {
        const intel = adminNav.find((n) => n.title === "Intelligence");
        const item = intel?.children?.find((c) => c.title === "Dropout Risk");
        expect(item?.href).toBe("/intelligence/dropout");
        expect(item?.permission).toBe("report:read");
    });
});

// ─── 8. API client type definitions ───

describe("API client — dropout type definitions", () => {
    it("DropoutSummary shape is correct", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: {
                    total_students: 200,
                    at_risk_count: 25,
                    band_breakdown: { LOW: 10, MEDIUM: 8, HIGH: 5, CRITICAL: 2 },
                    top_signals: [{ code: "CONSEC_3", label: "3+ consecutive absences", count: 12 }],
                },
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.dropoutSummary();
        expect(result.data.total_students).toBe(200);
        expect(result.data.at_risk_count).toBe(25);
        expect(result.data.band_breakdown.CRITICAL).toBe(2);
    });

    it("DropoutStudentRow shape is correct", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    student_id: "s-1", student_code: "SC001",
                    first_name: "John", last_name: "Doe",
                    risk_score: 65, risk_band: "HIGH",
                    signal_count: 3, top_signal: "5+ consecutive absences",
                }],
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.dropoutStudents();
        expect(result.data[0].risk_score).toBe(65);
        expect(result.data[0].risk_band).toBe("HIGH");
        expect(result.data[0].signal_count).toBe(3);
    });

    it("DropoutStudentDetail shape is correct", async () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: {
                    student_id: "s-1", risk_score: 85, risk_band: "CRITICAL",
                    signals: [
                        { code: "CONSEC_10", label: "10+ consecutive absences", points: 60, evidence: "10 days" },
                        { code: "FEE_OUTSTANDING", label: "Outstanding balance", points: 10, evidence: "$150" },
                    ],
                    computed_at: "2025-01-15T10:00:00Z",
                    lookback_days: 30,
                },
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = reportsApi(mockClient as any);
        const result = await api.dropoutStudentDetail("s-1");
        expect(result.data.risk_score).toBe(85);
        expect(result.data.signals).toHaveLength(2);
        expect(result.data.signals[0].code).toBe("CONSEC_10");
        expect(result.data.lookback_days).toBe(30);
    });
});
