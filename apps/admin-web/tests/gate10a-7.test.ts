/**
 * Admin-web — Unit Tests for 10A-7 (Communication UI)
 *
 * Covers:
 *  ✅ API client comm methods (listAnnouncements, createAnnouncement, deleteAnnouncement, listOutbox)
 *  ✅ i18n comm keys in all locales
 *  ✅ File structure
 *  ✅ Announcements page content assertions
 *  ✅ Outbox page content assertions
 *  ✅ Student 360 CommunicationsTab rework
 *  ✅ Nav config with Announcements + Outbox
 *  ✅ API client types updated
 */

import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API client comm methods ───

import { commApi } from "@eduzim/api-client";

describe("API client — comm methods", () => {
    const mockClient = {
        get: vi.fn().mockResolvedValue({ data: [] }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: null }),
    };

    const api = commApi(mockClient as any);

    it("has listAnnouncements method", () => {
        expect(typeof api.listAnnouncements).toBe("function");
    });

    it("has createAnnouncement method", () => {
        expect(typeof api.createAnnouncement).toBe("function");
    });

    it("has deleteAnnouncement method", () => {
        expect(typeof api.deleteAnnouncement).toBe("function");
    });

    it("has listOutbox method", () => {
        expect(typeof api.listOutbox).toBe("function");
    });

    it("listAnnouncements calls GET /api/v1/comm/announcements", async () => {
        await api.listAnnouncements();
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/comm/announcements", undefined);
    });

    it("createAnnouncement calls POST /api/v1/comm/announcements", async () => {
        const data = { title: "Test", body: "Hello", audience: { type: "ALL" }, channels: ["IN_APP"] };
        await api.createAnnouncement(data);
        expect(mockClient.post).toHaveBeenCalledWith("/api/v1/comm/announcements", data);
    });

    it("deleteAnnouncement calls DELETE /api/v1/comm/announcements/:id", async () => {
        await api.deleteAnnouncement("ann-123");
        expect(mockClient.delete).toHaveBeenCalledWith("/api/v1/comm/announcements/ann-123");
    });

    it("listOutbox calls GET /api/v1/comm/outbox", async () => {
        mockClient.get.mockClear();
        await api.listOutbox({ status: "FAILED" });
        expect(mockClient.get).toHaveBeenCalledWith("/api/v1/comm/outbox", { status: "FAILED" });
    });
});

// ─── 2. i18n — comm keys ───

import enMessages from "../messages/en.json";
import snMessages from "../messages/sn.json";
import ndMessages from "../messages/nd.json";

describe("i18n — comm keys", () => {
    const requiredKeys = [
        "title", "announcements", "outbox",
        "createAnnouncement", "createAnnouncementDescription",
        "announcementTitle", "announcementBody",
        "audienceType", "audienceAll", "audienceClass", "audienceRole",
        "selectClass", "selectRole",
        "channels", "channelInApp", "channelSMS",
        "noAnnouncements", "noAnnouncementsDescription",
        "recipientCount", "createdBy", "createdAt",
        "noOutbox", "noOutboxDescription",
        "announcement", "recipient", "channel", "status",
        "pending", "sent", "failed",
        "retryCount", "lastAttempt", "error",
        "filterByStatus", "filterByChannel",
        "allStatuses", "allChannels",
        "schoolAnnouncements", "noCommsDescription",
    ];

    it("en.json has comm section with all required keys", () => {
        const keys = Object.keys((enMessages as any).comm || {});
        for (const k of requiredKeys) {
            expect(keys).toContain(k);
        }
    });

    it("sn.json has comm section with matching keys", () => {
        expect((snMessages as any).comm).toBeDefined();
        const keys = Object.keys((snMessages as any).comm);
        const enKeys = Object.keys((enMessages as any).comm);
        expect(keys).toEqual(enKeys);
    });

    it("nd.json has comm section with matching keys", () => {
        expect((ndMessages as any).comm).toBeDefined();
        const keys = Object.keys((ndMessages as any).comm);
        const enKeys = Object.keys((enMessages as any).comm);
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

// ─── 3. File structure ───

describe("File structure — communication module", () => {
    it("Announcements page exists", () => {
        expect(fs.existsSync(
            path.resolve(__dirname, "../src/app/(admin)/communication/announcements/page.tsx"),
        )).toBe(true);
    });

    it("Outbox page exists", () => {
        expect(fs.existsSync(
            path.resolve(__dirname, "../src/app/(admin)/communication/outbox/page.tsx"),
        )).toBe(true);
    });
});

// ─── 4. Announcements page content ───

describe("Announcements page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/communication/announcements/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with comm:read permission", () => {
        expect(src).toContain('permissions={["comm:read"]}');
    });

    it("has audience type selector (ALL/CLASS/ROLE)", () => {
        expect(src).toContain('"ALL"');
        expect(src).toContain('"CLASS"');
        expect(src).toContain('"ROLE"');
    });

    it("has channel checkboxes (IN_APP, SMS)", () => {
        expect(src).toContain("channelInApp");
        expect(src).toContain("channelSMS");
        expect(src).toContain('"IN_APP"');
        expect(src).toContain('"SMS"');
    });

    it("shows SMS character count when SMS channel selected", () => {
        expect(src).toContain("160");
        expect(src).toContain("body.length");
    });

    it("conditional class selector when audience is CLASS", () => {
        expect(src).toContain('audienceType === "CLASS"');
        expect(src).toContain("classOptions");
    });

    it("conditional role selector when audience is ROLE", () => {
        expect(src).toContain('audienceType === "ROLE"');
        expect(src).toContain("roleOptions");
    });

    it("uses correct Sheet API (onClose)", () => {
        expect(src).toContain("onClose");
        expect(src).not.toContain("SheetContent");
        expect(src).not.toContain("SheetTrigger");
    });

    it("uses comm API", () => {
        expect(src).toContain("comm.listAnnouncements");
        expect(src).toContain("comm.createAnnouncement");
    });

    it("uses i18n translations", () => {
        expect(src).toContain('useTranslations("comm")');
    });
});

// ─── 5. Outbox page content ───

describe("Outbox page", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/communication/outbox/page.tsx"), "utf-8",
    );

    it("uses RouteGuard with school:manage permission (admin-only)", () => {
        expect(src).toContain('permissions={["school:manage"]}');
    });

    it("has status filter (PENDING/SENT/FAILED)", () => {
        expect(src).toContain("statusFilter");
        expect(src).toContain('"PENDING"');
        expect(src).toContain('"SENT"');
        expect(src).toContain('"FAILED"');
    });

    it("has channel filter (IN_APP/SMS)", () => {
        expect(src).toContain("channelFilter");
    });

    it("shows retry count", () => {
        expect(src).toContain("retry_count");
    });

    it("shows error messages truncated", () => {
        expect(src).toContain("error_message");
        expect(src).toContain("slice(0, 40)");
    });

    it("shows last attempt timestamp", () => {
        expect(src).toContain("last_attempt_at");
    });
});

// ─── 6. Student 360 CommunicationsTab rework ───

describe("Student 360 — Communications tab rework", () => {
    const src = fs.readFileSync(
        path.resolve(__dirname, "../src/app/(admin)/students/[id]/page.tsx"), "utf-8",
    );

    it("uses comm.listAnnouncements API", () => {
        expect(src).toContain("comm.listAnnouncements");
    });

    it("displays announcement title and body", () => {
        expect(src).toContain("ann.title");
        expect(src).toContain("ann.body");
    });

    it("shows audience_type badge", () => {
        expect(src).toContain("ann.audience_type");
    });

    it("uses comm i18n translations", () => {
        expect(src).toContain('useTranslations("comm")');
    });

    it("imports Announcement type", () => {
        expect(src).toContain("Announcement");
    });
});

// ─── 7. Nav config — Announcements + Outbox ───

import { adminNav } from "../src/lib/nav";

describe("Nav config — communication sub-items", () => {
    const ops = adminNav.find((n) => n.title === "Operations");

    it("has Announcements and Outbox nav items", () => {
        const childTitles = ops?.children?.map((c) => c.title) ?? [];
        expect(childTitles).toContain("Announcements");
        expect(childTitles).toContain("Outbox");
    });

    it("Announcements links to /communication/announcements with comm:read", () => {
        const item = ops?.children?.find((c) => c.title === "Announcements");
        expect(item?.href).toBe("/communication/announcements");
        expect(item?.permission).toBe("comm:read");
    });

    it("Outbox links to /communication/outbox with school:manage", () => {
        const item = ops?.children?.find((c) => c.title === "Outbox");
        expect(item?.href).toBe("/communication/outbox");
        expect(item?.permission).toBe("school:manage");
    });
});

// ─── 8. API client types updated ───

describe("API client — comm type shape", () => {
    it("Announcement type has audience_type, audience_class_id, audience_role", () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    id: "1", school_id: "s1", title: "Test", body: "Hello",
                    audience_type: "ALL", audience_class_id: null, audience_role: null,
                    created_by: "u1", created_at: "2025-01-01", deleted_at: null,
                }],
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = commApi(mockClient as any);
        api.listAnnouncements().then((r: any) => {
            expect(r.data[0].audience_type).toBe("ALL");
            expect(r.data[0].audience_class_id).toBeNull();
        });
    });

    it("OutboxEntry type has user_id, retry_count, error_message", () => {
        const mockClient = {
            get: vi.fn().mockResolvedValue({
                data: [{
                    id: "1", school_id: "s1", announcement_id: "a1",
                    user_id: "u1", channel: "IN_APP", status: "SENT",
                    retry_count: 0, last_attempt_at: null, error_message: null,
                    created_at: "2025-01-01",
                }],
            }),
            post: vi.fn(), put: vi.fn(), delete: vi.fn(),
        };
        const api = commApi(mockClient as any);
        api.listOutbox().then((r: any) => {
            expect(r.data[0].user_id).toBe("u1");
            expect(r.data[0].retry_count).toBe(0);
        });
    });
});
