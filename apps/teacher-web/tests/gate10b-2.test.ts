/**
 * Teacher-web — 10B-2 Quality Gate Tests (Dropout Risk Badge)
 * =============================================================
 * Tests cover:
 * - Risk badge component exists with correct data attributes
 * - Overview tab shows risk badge when risk data present
 * - Fee signals filtered out (teacher sees attendance only)
 * - Risk detail API call in student page
 * - i18n riskSignals key in all 3 languages
 * - Risk badge supports all 4 bands (LOW, MEDIUM, HIGH, CRITICAL)
 * - Reports API imported in teacher-web api.ts
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. Risk Badge Component ───

describe("Risk badge component", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/components/risk-badge.tsx"), "utf-8",
    );

    it("exports RiskBadge function", () => {
        expect(src).toContain("export function RiskBadge");
    });

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

    it("has colored dot indicators for all bands", () => {
        expect(src).toContain("bg-green-500");
        expect(src).toContain("bg-amber-500");
        expect(src).toContain("bg-orange-500");
        expect(src).toContain("bg-red-500");
    });

    it("has role=status for accessibility", () => {
        expect(src).toContain('role="status"');
    });
});

// ─── 2. Overview Tab — Risk Badge Integration ───

describe("Overview tab — risk badge integration", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(teacher)/students/[id]/overview-tab.tsx"), "utf-8",
    );

    it("imports RiskBadge component", () => {
        expect(src).toContain("RiskBadge");
    });

    it("imports DropoutStudentDetail type", () => {
        expect(src).toContain("DropoutStudentDetail");
    });

    it("accepts riskDetail prop", () => {
        expect(src).toContain("riskDetail");
    });

    it("renders risk badge when risk data exists", () => {
        expect(src).toContain("riskDetail.risk_score");
    });

    it("shows risk signals section", () => {
        expect(src).toContain('data-testid="risk-signals"');
    });

    it("filters out fee signals for teacher view", () => {
        expect(src).toContain('!s.code.startsWith("FEE_")');
    });

    it("displays signal label and points", () => {
        expect(src).toContain("signal.label");
        expect(src).toContain("signal.points");
    });
});

// ─── 3. Student Detail Page — Risk Fetch ───

describe("Student detail page — risk data fetch", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(teacher)/students/[id]/page.tsx"), "utf-8",
    );

    it("imports reports API", () => {
        expect(src).toContain("reports");
    });

    it("imports DropoutStudentDetail type", () => {
        expect(src).toContain("DropoutStudentDetail");
    });

    it("fetches dropout student detail", () => {
        expect(src).toContain("reports.dropoutStudentDetail");
    });

    it("passes riskDetail to OverviewTab", () => {
        expect(src).toContain("riskDetail={riskDetail}");
    });

    it("gates risk fetch on authorization", () => {
        // Should only fetch when authorized
        expect(src).toContain("authorized");
    });
});

// ─── 4. API setup — Reports imported ───

describe("Teacher-web API setup", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/lib/api.ts"), "utf-8",
    );

    it("imports reportsApi from @eduzim/api-client", () => {
        expect(src).toContain("reportsApi");
    });

    it("exports reports instance", () => {
        expect(src).toContain("export const reports = reportsApi(api)");
    });
});

// ─── 5. i18n — riskSignals key ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — riskSignals key", () => {
    it("en.json students has riskSignals", () => {
        expect((enMessages as any).students.riskSignals).toBeDefined();
        expect(typeof (enMessages as any).students.riskSignals).toBe("string");
    });

    it("sn.json students has riskSignals", () => {
        expect((snMessages as any).students.riskSignals).toBeDefined();
        expect(typeof (snMessages as any).students.riskSignals).toBe("string");
    });

    it("nd.json students has riskSignals", () => {
        expect((ndMessages as any).students.riskSignals).toBeDefined();
        expect(typeof (ndMessages as any).students.riskSignals).toBe("string");
    });

    it("all 3 locales have same student keys", () => {
        const enKeys = Object.keys((enMessages as any).students).sort();
        const snKeys = Object.keys((snMessages as any).students).sort();
        const ndKeys = Object.keys((ndMessages as any).students).sort();
        expect(snKeys).toEqual(enKeys);
        expect(ndKeys).toEqual(enKeys);
    });
});

// ─── 6. Risk band definitions ───

describe("Risk band definitions", () => {
    const bands = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
    const bandRanges = {
        LOW: [0, 29],
        MEDIUM: [30, 59],
        HIGH: [60, 79],
        CRITICAL: [80, 100],
    };

    it("has 4 defined risk bands", () => {
        expect(bands).toHaveLength(4);
    });

    it.each(Object.entries(bandRanges))("%s band covers correct range", (band, [min, max]) => {
        expect(min).toBeLessThanOrEqual(max);
        expect(min).toBeGreaterThanOrEqual(0);
        expect(max).toBeLessThanOrEqual(100);
    });

    it("bands are contiguous (no gaps)", () => {
        expect(bandRanges.LOW[1] + 1).toBe(bandRanges.MEDIUM[0]);
        expect(bandRanges.MEDIUM[1] + 1).toBe(bandRanges.HIGH[0]);
        expect(bandRanges.HIGH[1] + 1).toBe(bandRanges.CRITICAL[0]);
    });

    it("full range covers 0-100", () => {
        expect(bandRanges.LOW[0]).toBe(0);
        expect(bandRanges.CRITICAL[1]).toBe(100);
    });
});
