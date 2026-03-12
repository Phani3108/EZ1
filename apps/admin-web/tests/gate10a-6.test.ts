/**
 * Admin-web — Unit Tests for 10A-6 (Fees UI)
 *
 * Covers:
 *  ✅ API client fees methods exist (listStructures, createStructure, listInvoices,
 *     createInvoice, recordPayment, listPayments, listDefaulters)
 *  ✅ i18n fees keys present in all locales
 *  ✅ Fees page files exist
 *  ✅ Fee structures page content assertions
 *  ✅ Invoices page content assertions
 *  ✅ Defaulters page content assertions
 *  ✅ Student 360 FeesTab rework with Record Payment sheet
 *  ✅ Nav config has fee sub-items
 *  ✅ API client type definitions updated
 */

import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client fees methods ───

import { feesApi } from "@eduzim/api-client";

describe("API client — fees methods", () => {
    const mockClient = {
        get: vi.fn().mockResolvedValue({ data: {} }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: null }),
    };

    const api = feesApi(mockClient as any);

    it("has listStructures method", () => {
        expect(typeof api.listStructures).toBe("function");
    });

    it("has createStructure method", () => {
        expect(typeof api.createStructure).toBe("function");
    });

    it("has listInvoices method", () => {
        expect(typeof api.listInvoices).toBe("function");
    });

    it("has createInvoice method", () => {
        expect(typeof api.createInvoice).toBe("function");
    });

    it("has recordPayment method", () => {
        expect(typeof api.recordPayment).toBe("function");
    });

    it("has listPayments method", () => {
        expect(typeof api.listPayments).toBe("function");
    });

    it("has listDefaulters method", () => {
        expect(typeof api.listDefaulters).toBe("function");
    });

    it("listStructures calls GET /api/v1/fees/structures", async () => {
        await api.listStructures({ year_id: "y-1" });
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/fees/structures", { year_id: "y-1" });
    });

    it("createStructure calls POST /api/v1/fees/structures", async () => {
        const data = { name: "Term 1", academic_year_id: "y-1", items: [] };
        await api.createStructure(data);
        expect(mockClient.post).toHaveBeenCalledWith("/api/v1/fees/structures", data);
    });

    it("recordPayment calls POST /api/v1/fees/payments", async () => {
        mockClient.post.mockClear();
        const data = { invoice_id: "inv-1", amount: 100, method: "CASH" };
        await api.recordPayment(data);
        expect(mockClient.post).toHaveBeenCalledWith("/api/v1/fees/payments", data);
    });

    it("listPayments calls GET /api/v1/fees/payments", async () => {
        mockClient.get.mockClear();
        await api.listPayments({ invoice_id: "inv-1" });
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/fees/payments", { invoice_id: "inv-1" });
    });

    it("listDefaulters calls GET /api/v1/fees/defaulters", async () => {
        mockClient.get.mockClear();
        await api.listDefaulters();
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/fees/defaulters", undefined);
    });
});

// ─── 2. i18n — fees keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — fees keys", () => {
    const requiredKeys = [
        "title", "structures", "invoices", "defaulters",
        "createStructure", "createStructureDescription",
        "structureName", "academicYear", "lineItems", "addItem", "removeItem",
        "itemLabel", "itemAmount", "totalAmount",
        "noStructures", "noStructuresDescription",
        "createInvoice", "selectStudent", "selectStructure", "dueDate",
        "noInvoices", "noInvoicesDescription",
        "studentName", "amount", "paid", "balance", "status",
        "pending", "partial", "paidStatus", "overdue",
        "recordPayment", "recordPaymentDescription",
        "paymentAmount", "paymentMethod", "methodCash", "methodMobile", "methodBank",
        "reference", "referencePlaceholder",
        "paymentRecorded", "alreadyProcessed", "overpaymentError", "alreadyPaidError",
        "noDefaulters", "noDefaultersDescription",
        "outstandingBalance", "daysOverdue",
        "filterByStatus", "allStatuses", "payments",
    ];

    it("en.json has fees section with all required keys", () => {
        const keys = Object.keys((enMessages as any).fees || {});
        for (const k of requiredKeys) {
            expect(keys).toContain(k);
        }
    });

    it("sn.json has fees section with matching keys", () => {
        expect((snMessages as any).fees).toBeDefined();
        const keys = Object.keys((snMessages as any).fees);
        const enKeys = Object.keys((enMessages as any).fees);
        expect(keys).toEqual(enKeys);
    });

    it("nd.json has fees section with matching keys", () => {
        expect((ndMessages as any).fees).toBeDefined();
        const keys = Object.keys((ndMessages as any).fees);
        const enKeys = Object.keys((enMessages as any).fees);
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

describe("File structure — fees module", () => {
    it("Fee structures page exists", () => {
        expect(fs.existsSync(
            path.resolve(__dirname, "../src/app/(admin)/fees/structures/page.tsx"),
        )).toBe(true);
    });

    it("Invoices page exists", () => {
        expect(fs.existsSync(
            path.resolve(__dirname, "../src/app/(admin)/fees/invoices/page.tsx"),
        )).toBe(true);
    });

    it("Defaulters page exists", () => {
        expect(fs.existsSync(
            path.resolve(__dirname, "../src/app/(admin)/fees/defaulters/page.tsx"),
        )).toBe(true);
    });
});

// ─── 4. Fee Structures page content ───

describe("Fee Structures page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/fees/structures/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with fees:read permission", () => {
        expect(src).toContain('permissions={["fees:read"]}');
    });

    it("has year filter", () => {
        expect(src).toContain("selectedYearId");
        expect(src).toContain("listAcademicYears");
    });

    it("has create structure form with line items", () => {
        expect(src).toContain("addItem");
        expect(src).toContain("removeItem");
        expect(src).toContain("LineItem");
    });

    it("shows live calculated total", () => {
        expect(src).toContain("total.toFixed(2)");
    });

    it("uses fees API methods", () => {
        expect(src).toContain("fees.listStructures");
        expect(src).toContain("fees.createStructure");
    });

    it("uses i18n translations", () => {
        expect(src).toContain('useTranslations("fees")');
    });

    it("uses correct Sheet API (onClose)", () => {
        expect(src).toContain("onClose");
        expect(src).not.toContain("SheetContent");
        expect(src).not.toContain("SheetTrigger");
    });
});

// ─── 5. Invoices page content ───

describe("Invoices page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/fees/invoices/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with fees:read permission", () => {
        expect(src).toContain('permissions={["fees:read"]}');
    });

    it("has status filter", () => {
        expect(src).toContain("statusFilter");
        expect(src).toContain("PENDING");
        expect(src).toContain("PARTIAL");
        expect(src).toContain('"PAID"');
        expect(src).toContain("OVERDUE");
    });

    it("shows invoice amounts correctly", () => {
        expect(src).toContain("total_amount");
        expect(src).toContain("paid_amount");
        expect(src).toContain("inv.balance");
    });

    it("links student names to Student 360", () => {
        expect(src).toContain("/students/${inv.student_id}");
    });

    it("has create invoice form", () => {
        expect(src).toContain("fees.createInvoice");
        expect(src).toContain("formStudentId");
        expect(src).toContain("formStructureId");
        expect(src).toContain("formDueDate");
    });

    it("uses correct Sheet API", () => {
        expect(src).toContain("onClose");
        expect(src).not.toContain("SheetTrigger");
    });
});

// ─── 6. Defaulters page content ───

describe("Defaulters page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/fees/defaulters/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with fees:read permission", () => {
        expect(src).toContain('permissions={["fees:read"]}');
    });

    it("shows outstanding balance in destructive color", () => {
        expect(src).toContain("text-destructive");
        expect(src).toContain("inv.balance");
    });

    it("calculates days overdue", () => {
        expect(src).toContain("daysOverdue");
    });

    it("links to student 360", () => {
        expect(src).toContain("/students/${inv.student_id}");
    });

    it("uses fees.listDefaulters API", () => {
        expect(src).toContain("fees.listDefaulters");
    });
});

// ─── 7. Student 360 FeesTab rework ───

describe("Student 360 — Fees tab rework", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/students/[id]/page.tsx"), "utf-8",
    );

    it("uses updated Invoice type (total_amount, paid_amount)", () => {
        expect(src).toContain("inv.total_amount");
        expect(src).toContain("inv.paid_amount");
    });

    it("has Record Payment sheet with proper Sheet API", () => {
        expect(src).toContain("Record Payment Sheet");
        expect(src).toContain("payingInvoice");
        expect(src).toContain("onClose");
    });

    it("has payment method selector (Cash, Mobile, Bank)", () => {
        expect(src).toContain('"CASH"');
        expect(src).toContain('"MOBILE"');
        expect(src).toContain('"BANK"');
    });

    it("shows balance context in payment sheet", () => {
        expect(src).toContain("payingInvoice.balance");
    });

    it("handles overpayment error display", () => {
        expect(src).toContain("payError");
        expect(src).toContain("bg-destructive/10");
    });

    it("disables submit while pending", () => {
        expect(src).toContain("payPending");
    });

    it("uses fees i18n translations", () => {
        expect(src).toContain('useTranslations("fees")');
    });
});

// ─── 8. Nav config — fee sub-items ───

import { adminNav } from "../src/lib/nav";

describe("Nav config — fee sub-items", () => {
    const ops = adminNav.find((n) => n.title === "Operations");

    it("has Fee Structures, Invoices, and Defaulters nav items", () => {
        const childTitles = ops?.children?.map((c) => c.title) ?? [];
        expect(childTitles).toContain("Fee Structures");
        expect(childTitles).toContain("Invoices");
        expect(childTitles).toContain("Defaulters");
    });

    it("Fee Structures links to /fees/structures with fees:read", () => {
        const item = ops?.children?.find((c) => c.title === "Fee Structures");
        expect(item?.href).toBe("/fees/structures");
        expect(item?.permission).toBe("fees:read");
    });

    it("Invoices links to /fees/invoices with fees:read", () => {
        const item = ops?.children?.find((c) => c.title === "Invoices");
        expect(item?.href).toBe("/fees/invoices");
        expect(item?.permission).toBe("fees:read");
    });

    it("Defaulters links to /fees/defaulters with fees:read", () => {
        const item = ops?.children?.find((c) => c.title === "Defaulters");
        expect(item?.href).toBe("/fees/defaulters");
        expect(item?.permission).toBe("fees:read");
    });
});

// ─── 9. API client types updated ───

describe("API client — fee type exports", () => {
    it("FeeStructure has items and total fields", async () => {
        // Verify types exist through the feesApi factory
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    id: "1", school_id: "s1", academic_year_id: "y1",
                    name: "Test", is_active: true,
                    items: [{ id: "i1", label: "Tuition", amount: 100, currency: "USD" }],
                    total: 100, created_at: "2025-01-01",
                }],
            }),
            post: vi.fn().mockResolvedValue({ data: {} }),
            put: vi.fn().mockResolvedValue({ data: {} }),
            delete: vi.fn().mockResolvedValue({ data: null }),
        };
        const api = feesApi(mockClient as any);
        const result = await api.listStructures();
        expect(result.data[0].items).toBeDefined();
        expect(result.data[0].total).toBe(100);
    });
});
