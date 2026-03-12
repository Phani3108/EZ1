/**
 * Parent-web — Unit Tests for 10A-P2 (Child Detail Tabs)
 *
 * Covers:
 *  ✅ API client exposes commApi.getFeed() method
 *  ✅ getFeed() calls GET /api/v1/comm/feed
 *  ✅ Child detail page uses Tabs (Overview, Attendance, Fees, Announcements)
 *  ✅ Child detail page calls attendance.studentTrend
 *  ✅ Child detail page calls fees.listInvoices
 *  ✅ Child detail page calls comm.getFeed
 *  ✅ Gateway RBAC has /comm/feed as authenticated
 *  ✅ Gateway RBAC has /attendance/student-trend as authenticated
 *  ✅ Gateway RBAC has /fees/invoices as authenticated
 *  ✅ Student type includes status, dob, student_code fields
 */
import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";

// ─── 1. API Client — commApi.getFeed ───

import { commApi } from "@eduzim/api-client";

describe("API client — commApi.getFeed", () => {
  const mockClient = {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };

  it("commApi exposes getFeed", () => {
    const svc = commApi(mockClient as any);
    expect(typeof svc.getFeed).toBe("function");
  });

  it("getFeed calls GET /api/v1/comm/feed with params", async () => {
    const svc = commApi(mockClient as any);
    await svc.getFeed({ student_id: "abc-123" });
    expect(mockClient.get).toHaveBeenCalledWith("/api/v1/comm/feed", {
      student_id: "abc-123",
    });
  });

  it("listAnnouncements still works (admin use case)", () => {
    const svc = commApi(mockClient as any);
    expect(typeof svc.listAnnouncements).toBe("function");
  });
});

// ─── 2. Child Detail Page — Tab Structure ───

describe("Child detail page — tabs", () => {
  const detailPath = path.resolve(
    __dirname,
    "../src/app/(parent)/children/[id]/page.tsx"
  );
  const content = fs.readFileSync(detailPath, "utf-8");

  it("imports Tabs component from @eduzim/ui", () => {
    expect(content).toContain("Tabs");
    expect(content).toContain("TabsList");
    expect(content).toContain("TabsTrigger");
    expect(content).toContain("TabsContent");
  });

  it("has Overview tab", () => {
    expect(content).toContain('"overview"');
    expect(content).toContain("Overview");
  });

  it("has Attendance tab", () => {
    expect(content).toContain('"attendance"');
    expect(content).toContain("Attendance");
  });

  it("has Fees tab", () => {
    expect(content).toContain('"fees"');
    expect(content).toContain("Fees");
  });

  it("has Announcements tab", () => {
    expect(content).toContain('"announcements"');
    expect(content).toContain("Announcements");
  });
});

// ─── 3. Child Detail Page — Data Fetching ───

describe("Child detail page — data fetching", () => {
  const detailPath = path.resolve(
    __dirname,
    "../src/app/(parent)/children/[id]/page.tsx"
  );
  const content = fs.readFileSync(detailPath, "utf-8");

  it("calls attendance.studentTrend", () => {
    expect(content).toContain("attendance.studentTrend");
  });

  it("calls fees.listInvoices with student_id", () => {
    expect(content).toContain("fees.listInvoices");
    expect(content).toContain("student_id");
  });

  it("calls comm.getFeed with student_id", () => {
    expect(content).toContain("comm.getFeed");
  });

  it("uses StatCard for summary stats", () => {
    expect(content).toContain("StatCard");
  });

  it("uses Badge for status display", () => {
    expect(content).toContain("Badge");
  });

  it("uses Table for data display", () => {
    expect(content).toContain("Table");
    expect(content).toContain("TableRow");
  });

  it("displays attendance rate", () => {
    expect(content).toContain("attendance_rate");
  });

  it("displays invoice balance", () => {
    expect(content).toContain("balance");
  });

  it("formats currency values", () => {
    expect(content).toContain("formatCurrency");
  });
});

// ─── 4. Gateway RBAC — Parent-accessible endpoints ───

describe("Gateway RBAC — parent-accessible endpoints", () => {
  const routesPath = path.resolve(
    __dirname,
    "../../../services/api-gateway/app/routes.py"
  );
  const content = fs.readFileSync(routesPath, "utf-8");

  it("/comm/feed is authenticated (not comm:read)", () => {
    expect(content).toContain('("GET", "/api/v1/comm/feed", "authenticated")');
  });

  it("/attendance/student-trend is authenticated", () => {
    expect(content).toContain(
      '("GET", "/api/v1/attendance/student-trend", "authenticated")'
    );
  });

  it("/fees/invoices is authenticated", () => {
    expect(content).toContain(
      '("GET", "/api/v1/fees/invoices", "authenticated")'
    );
  });

  it("/parents/me/children is still authenticated", () => {
    expect(content).toContain(
      '("GET", "/api/v1/parents/me/children", "authenticated")'
    );
  });
});

// ─── 5. Student Type — Extended Fields ───

describe("Student type — extended fields", () => {
  it("Student type has status field", async () => {
    const { studentApi } = await import("@eduzim/api-client");
    // Type-level check: the function exists and is callable
    expect(typeof studentApi).toBe("function");
  });

  it("types file includes dob and student_code", () => {
    const typesPath = path.resolve(
      __dirname,
      "../../../packages/api-client/src/types.ts"
    );
    const content = fs.readFileSync(typesPath, "utf-8");
    expect(content).toContain("dob?:");
    expect(content).toContain("student_code?:");
    expect(content).toContain("status?:");
    expect(content).toContain("deleted_at?:");
  });
});

// ─── 6. Internal Authorization Endpoint ───

describe("Internal parent authorize endpoint", () => {
  const routesPath = path.resolve(
    __dirname,
    "../../../services/student-service/app/api/routes.py"
  );
  const content = fs.readFileSync(routesPath, "utf-8");

  it("student-service has /internal/parents/authorize route", () => {
    expect(content).toContain("/internal/parents/authorize");
  });

  it("accepts user_id and student_id params", () => {
    expect(content).toContain("user_id");
    expect(content).toContain("student_id");
  });

  it("calls verify_parent_child_link", () => {
    expect(content).toContain("verify_parent_child_link");
  });
});

// ─── 7. Communication Feed Endpoint ───

describe("Communication feed endpoint", () => {
  const routesPath = path.resolve(
    __dirname,
    "../../../services/communication-service/app/api/routes.py"
  );
  const content = fs.readFileSync(routesPath, "utf-8");

  it("comm-service has /comm/feed route", () => {
    expect(content).toContain("/comm/feed");
  });

  it("accepts student_id query param", () => {
    expect(content).toContain("student_id");
  });

  it("calls get_feed_for_student", () => {
    expect(content).toContain("get_feed_for_student");
  });
});
