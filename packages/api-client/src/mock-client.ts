/**
 * EduZim — Mock API Client
 * ==========================
 * Returns mock data for every API route, matching the same interface as createClient.
 * Activate by setting NEXT_PUBLIC_MOCK_DATA=true in the app's .env.local.
 *
 * Supports role-based sessions: login with admin@eduzim.com, teacher@eduzim.com,
 * or parent@eduzim.com (password: 123456) to get the corresponding persona.
 */

import type { ApiMeta } from "./types";
import * as mock from "./mock-data";

const META: ApiMeta = {
    request_id: "mock-req-001",
    timestamp: new Date().toISOString(),
    page: 1,
    page_size: 50,
    total: 20,
    has_next: false,
};

function ok<T>(data: T, meta?: Partial<ApiMeta>) {
    return Promise.resolve({ data, meta: { ...META, ...meta } });
}

function err(status: number, message: string): never {
    const e = Object.assign(new Error(message), { status, code: "MOCK_ERROR", details: {}, requestId: "mock-req-err" });
    throw e;
}

// ─── Mock session state (persisted in sessionStorage on the client) ───

const VALID_CREDENTIALS: Record<string, string> = {
    "admin@eduzim.com": "123456",
    "teacher@eduzim.com": "123456",
    "parent@eduzim.com": "123456",
};

function getStoredSession(): string | null {
    try {
        if (typeof window !== "undefined") return sessionStorage.getItem("eduzim_mock_user");
    } catch { /* SSR */ }
    return _mockSessionEmail;
}

function setStoredSession(email: string | null) {
    _mockSessionEmail = email;
    try {
        if (typeof window !== "undefined") {
            if (email) sessionStorage.setItem("eduzim_mock_user", email);
            else sessionStorage.removeItem("eduzim_mock_user");
        }
    } catch { /* SSR */ }
}

let _mockSessionEmail: string | null = null;

function getMockMe() {
    const email = getStoredSession();
    return mock.getMockMeForUser(email ?? "admin@eduzim.com");
}

function getMockLogin(email: string) {
    return mock.getMockLoginForUser(email);
}

/** Path-matching router for mock data */
function route(method: string, path: string, params?: Record<string, string>, body?: unknown) {
    // Normalize
    const p = path.replace(/\/+$/, "");

    // Auth
    if (p === "/api/v1/auth/me") {
        const session = getStoredSession();
        if (!session) err(401, "Unauthenticated");
        return ok(getMockMe());
    }
    if (p === "/api/v1/auth/login" && method === "POST") {
        const b = body as { email?: string; password?: string } | null;
        const email = b?.email?.trim().toLowerCase() ?? "";
        const password = b?.password ?? "";
        if (VALID_CREDENTIALS[email] && VALID_CREDENTIALS[email] === password) {
            setStoredSession(email);
            return ok(getMockLogin(email));
        }
        err(401, "Invalid email or password");
    }
    if (p === "/api/v1/auth/refresh") {
        const session = getStoredSession();
        if (!session) err(401, "No active session");
        return ok(getMockLogin(session!));
    }
    if (p === "/api/v1/auth/logout") {
        setStoredSession(null);
        return ok({ message: "OK" });
    }

    // Academic years
    if (p === "/api/v1/academic-years") return ok([mock.MOCK_ACADEMIC_YEAR]);
    if (p.match(/^\/api\/v1\/academic-years\/[\w-]+$/)) return ok(mock.MOCK_ACADEMIC_YEAR);

    // Terms
    if (p === "/api/v1/terms") return ok(mock.MOCK_TERMS);
    if (p.match(/^\/api\/v1\/terms\/[\w-]+$/)) return ok(mock.MOCK_TERMS[0]);

    // Classes
    if (p === "/api/v1/classes" && method === "GET") return ok(mock.MOCK_CLASSES);
    if (p.match(/^\/api\/v1\/classes\/[\w-]+$/) && method === "GET") {
        const id = p.split("/").pop()!;
        return ok(mock.MOCK_CLASSES.find((c) => c.id === id) || mock.MOCK_CLASSES[0]);
    }
    if (p === "/api/v1/classes" && method === "POST") return ok(mock.MOCK_CLASSES[0]);
    if (p.match(/^\/api\/v1\/classes\/[\w-]+$/) && method === "PUT") return ok(mock.MOCK_CLASSES[0]);
    if (p.match(/^\/api\/v1\/classes\/[\w-]+$/) && method === "DELETE") return ok(null);

    // Subjects
    if (p === "/api/v1/subjects") return ok(mock.MOCK_SUBJECTS);
    if (p.match(/^\/api\/v1\/subjects\/[\w-]+$/)) return ok(mock.MOCK_SUBJECTS[0]);

    // Teacher classes
    if (p === "/api/v1/teachers/me/classes") return ok(mock.MOCK_TEACHER_CLASSES);

    // Students
    if (p === "/api/v1/students" && method === "GET") return ok(mock.MOCK_STUDENTS, { total: 20 });
    if (p.match(/^\/api\/v1\/students\/[\w-]+\/parents$/)) {
        const sid = p.split("/")[4];
        const parentIds = Object.entries(mock.MOCK_PARENT_CHILDREN)
            .filter(([, kids]) => kids.includes(sid))
            .map(([pid]) => pid);
        return ok(mock.MOCK_PARENTS.filter((p) => parentIds.includes(p.id)));
    }
    if (p.match(/^\/api\/v1\/students\/[\w-]+\/enrollments$/)) {
        const sid = p.split("/")[4];
        return ok(mock.MOCK_ENROLLMENTS.filter((e) => e.student_id === sid));
    }
    if (p.match(/^\/api\/v1\/students\/[\w-]+$/)) {
        const id = p.split("/").pop()!;
        return ok(mock.MOCK_STUDENTS.find((s) => s.id === id) || mock.MOCK_STUDENTS[0]);
    }

    // Parents
    if (p === "/api/v1/parents/me/children") return ok(mock.MOCK_STUDENTS.slice(0, 2));
    if (p.match(/^\/api\/v1\/parents\/[\w-]+\/children$/)) {
        const pid = p.split("/")[4];
        const childIds = mock.MOCK_PARENT_CHILDREN[pid] || [];
        return ok(mock.MOCK_STUDENTS.filter((s) => childIds.includes(s.id)));
    }
    if (p === "/api/v1/parents") return ok(mock.MOCK_PARENTS, { total: 10 });
    if (p.match(/^\/api\/v1\/parents\/[\w-]+$/)) {
        const id = p.split("/").pop()!;
        return ok(mock.MOCK_PARENTS.find((par) => par.id === id) || mock.MOCK_PARENTS[0]);
    }

    // Enrollments
    if (p === "/api/v1/enrollments" && method === "GET") {
        if (params?.class_id) {
            return ok(mock.MOCK_ENROLLMENTS.filter((e) => e.class_id === params.class_id));
        }
        return ok(mock.MOCK_ENROLLMENTS);
    }
    if (p === "/api/v1/enrollments" && method === "POST") return ok(mock.MOCK_ENROLLMENTS[0]);

    // Attendance
    if (p === "/api/v1/attendance/daily") return ok(mock.MOCK_ATTENDANCE_SUMMARY);
    if (p === "/api/v1/attendance/daily/records") {
        if (params?.class_id) {
            return ok(mock.MOCK_ATTENDANCE_RECORDS.filter((r) => r.class_id === params.class_id));
        }
        return ok(mock.MOCK_ATTENDANCE_RECORDS);
    }
    if (p === "/api/v1/attendance/student-trend") return ok(mock.MOCK_ATTENDANCE_TREND);
    if (p === "/api/v1/attendance/class-summary") return ok(mock.MOCK_ATTENDANCE_CLASS_SUMMARY);
    if (p === "/api/v1/attendance/sync/batches") return ok(mock.MOCK_SYNC_BATCHES);
    if (p === "/api/v1/attendance/sync") return ok({ accepted: 20, updated: 0, ignored: 0 });

    // Fees
    if (p === "/api/v1/fees/structures") return ok(mock.MOCK_FEE_STRUCTURES);
    if (p === "/api/v1/fees/invoices") {
        if (params?.student_id) {
            return ok(mock.MOCK_INVOICES.filter((i) => i.student_id === params.student_id));
        }
        return ok(mock.MOCK_INVOICES);
    }
    if (p === "/api/v1/fees/payments") return ok(mock.MOCK_PAYMENTS);
    if (p === "/api/v1/fees/defaulters") return ok(mock.MOCK_DEFAULTERS);

    // Paynow — payment initiate + status polling
    if (p === "/api/v1/fees/payments/initiate" && method === "POST") {
        const ref = `EDU-MOCK-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
        return ok({
            transaction_ref: ref,
            status: "PENDING",
            poll_url: "",
            instructions: "Demo mode: no real payment was triggered. In production, the parent would receive a USSD prompt on their phone.",
            demo_mode: true,
        });
    }
    if (p.match(/^\/api\/v1\/fees\/payments\/[\w-]+\/status$/) && method === "GET") {
        const ref = p.split("/")[5];
        return ok({
            transaction_ref: ref,
            status: "PAID",
            paynow_reference: "PNW-MOCK-001",
            amount: 50,
            currency: "USD",
            method: "ECOCASH",
            instructions: "Demo mode — auto-marked PAID after 1 poll.",
            last_error: null,
            initiated_at: new Date(Date.now() - 5000).toISOString(),
            confirmed_at: new Date().toISOString(),
        });
    }

    // Communication
    if (p === "/api/v1/comm/announcements" && method === "GET") return ok(mock.MOCK_ANNOUNCEMENTS);
    if (p === "/api/v1/comm/announcements" && method === "POST") return ok({ announcement: mock.MOCK_ANNOUNCEMENTS[0], outbox_created: 3, recipient_count: 20, channels: ["SMS", "EMAIL"] });
    if (p === "/api/v1/comm/feed") return ok(mock.MOCK_ANNOUNCEMENTS);
    if (p.match(/^\/api\/v1\/comm\/announcements\/[\w-]+$/) && method === "DELETE") return ok(mock.MOCK_ANNOUNCEMENTS[0]);
    if (p === "/api/v1/comm/outbox") return ok(mock.MOCK_OUTBOX);
    if (p === "/api/v1/comm/outbox/stats") return ok({
        totals: { DELIVERED: 4210, PENDING: 12, FAILED: 3, SENT: 0 },
        by_channel: {
            SMS: { DELIVERED: 1850, PENDING: 8, FAILED: 2 },
            EMAIL: { DELIVERED: 2102, PENDING: 3, FAILED: 1 },
            IN_APP: { DELIVERED: 258, PENDING: 1 },
        },
    });
    if (p.match(/^\/api\/v1\/comm\/outbox\/[\w-]+\/retry$/) && method === "POST") {
        const id = p.split("/")[5];
        return ok({ id, status: "PENDING", retried: true });
    }

    // Reports
    if (p === "/api/v1/reports/dashboard") return ok(mock.MOCK_DASHBOARD);
    if (p === "/api/v1/reports/attendance/trend") return ok(mock.MOCK_ATTENDANCE_TREND_POINTS);
    if (p === "/api/v1/reports/financial/summary") return ok(mock.MOCK_FINANCIAL_SUMMARY);
    if (p === "/api/v1/reports/dropout/summary") return ok(mock.MOCK_DROPOUT_SUMMARY);
    if (p === "/api/v1/reports/dropout/students") return ok(mock.MOCK_DROPOUT_STUDENTS);
    if (p.match(/^\/api\/v1\/reports\/dropout\/student\/[\w-]+$/)) return ok(mock.MOCK_DROPOUT_DETAIL);

    // Users & Roles
    if (p === "/api/v1/users" && method === "GET") return ok(mock.MOCK_USERS);
    if (p.match(/^\/api\/v1\/users\/[\w-]+$/) && method === "GET") {
        const id = p.split("/").pop()!;
        return ok(mock.MOCK_USERS.find((u) => u.id === id) || mock.MOCK_USERS[0]);
    }
    if (p === "/api/v1/roles") return ok(mock.MOCK_ROLES);
    if (p === "/api/v1/permissions") return ok(mock.MOCK_PERMISSIONS);

    // Assessments
    if (p === "/api/v1/assessments" && method === "GET") {
        let filtered = mock.MOCK_ASSESSMENTS;
        if (params?.class_id) filtered = filtered.filter((a) => a.class_id === params.class_id);
        if (params?.term_id) filtered = filtered.filter((a) => a.term_id === params.term_id);
        if (params?.subject_id) filtered = filtered.filter((a) => a.subject_id === params.subject_id);
        return ok(filtered);
    }
    if (p === "/api/v1/assessments" && method === "POST") return ok(mock.MOCK_ASSESSMENTS[0]);
    if (p.match(/^\/api\/v1\/assessments\/[\w-]+\/marks\/bulk$/)) return ok({ accepted: 5, updated: 0, errors: [] });
    if (p.match(/^\/api\/v1\/assessments\/students\/[\w-]+\/marks$/)) return ok(mock.MOCK_STUDENT_SUBJECT_MARKS);
    if (p.match(/^\/api\/v1\/assessments\/classes\/[\w-]+\/performance$/)) return ok(mock.MOCK_CLASS_PERFORMANCE);
    if (p.match(/^\/api\/v1\/assessments\/[\w-]+$/)) {
        const id = p.split("/").pop()!;
        return ok(mock.MOCK_ASSESSMENT_DETAILS.find((a) => a.id === id) || mock.MOCK_ASSESSMENT_DETAILS[0]);
    }

    // Diagnostics
    if (p === "/api/v1/diagnostics/services") return ok({ integrations: mock.MOCK_INTEGRATIONS });
    if (p.match(/^\/api\/v1\/diagnostics\/probe\/[\w-]+$/) && method === "POST") {
        const id = p.split("/").pop()!;
        const summary = mock.MOCK_INTEGRATIONS.find((i) => i.id === id);
        if (id === "fees-service") return ok(mock.MOCK_INTEGRATION_PROBE);
        return ok({
            id,
            label: summary?.label ?? id,
            category: summary?.category ?? "core",
            description: summary?.description ?? "",
            status: summary?.status ?? "ok",
            deep_probe: false,
            message: "Deep probe not implemented yet — showing a quick health check instead.",
            checks: [
                { id: "health", label: "Service health", status: summary?.status ?? "ok", latency_ms: summary?.latency_ms, detail: "Service responded to /health." },
            ],
        });
    }

    // Fallback — return empty data
    console.warn(`[MockClient] Unmatched route: ${method} ${p}`);
    return ok(null);
}

/**
 * Creates a mock API client with the same interface as createClient.
 * All routes resolve with mock data instead of making HTTP calls.
 */
export function createMockClient() {
    return {
        get<T>(path: string, params?: Record<string, string>) {
            return route("GET", path, params) as Promise<{ data: T; meta: typeof META }>;
        },
        post<T>(path: string, body?: unknown) {
            return route("POST", path, undefined, body) as Promise<{ data: T; meta: typeof META }>;
        },
        put<T>(path: string, body?: unknown) {
            return route("PUT", path, undefined, body) as Promise<{ data: T; meta: typeof META }>;
        },
        patch<T>(path: string, body?: unknown) {
            return route("PATCH", path, undefined, body) as Promise<{ data: T; meta: typeof META }>;
        },
        delete<T>(path: string) {
            return route("DELETE", path) as Promise<{ data: T; meta: typeof META }>;
        },
    };
}
