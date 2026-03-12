/**
 * EduZim — Centralized Mock Data
 * ================================
 * 30 students, 25 parents, 8 teachers, 6 classes, 12 subjects.
 * All data is Zimbabwe-specific: Harare Central Secondary School.
 * Used by all 3 dashboard apps when NEXT_PUBLIC_MOCK_DATA=true.
 */

import type {
    AcademicYear, Term, SchoolClass, TeacherClass, Subject,
    Student, Parent, Enrollment,
    AttendanceDailySummary, AttendanceDailyRecord, AttendanceStudentTrend, AttendanceClassSummary, AttendanceSyncBatch,
    FeeStructure, Invoice, Payment,
    Announcement, OutboxEntry,
    DashboardData, AttendanceTrendPoint, FinancialSummaryData,
    DropoutSummary, DropoutStudentRow, DropoutStudentDetail,
    User, Role, Permission,
    Assessment, AssessmentDetail, MarkEntry, StudentSubjectMarks, ClassPerformance,
    MeData, LoginData,
} from "./types";

const SCHOOL_ID = "sch_demo";
const NOW = "2026-03-12T12:00:00Z";
const TODAY = "2026-03-12";

const uid = (prefix: string, n: number) => `${prefix}-${String(n).padStart(3, "0")}`;

// ─── Academic Year & Terms ───

export const MOCK_ACADEMIC_YEAR: AcademicYear = {
    id: "ay-001", school_id: SCHOOL_ID, name: "2026 Academic Year",
    start_date: "2026-01-12", end_date: "2026-11-27", is_current: true, created_at: NOW,
};

export const MOCK_TERMS: Term[] = [
    { id: "term-001", academic_year_id: "ay-001", name: "Term 1", start_date: "2026-01-12", end_date: "2026-04-03", is_current: true, created_at: NOW },
    { id: "term-002", academic_year_id: "ay-001", name: "Term 2", start_date: "2026-05-05", end_date: "2026-08-07", is_current: false, created_at: NOW },
    { id: "term-003", academic_year_id: "ay-001", name: "Term 3", start_date: "2026-09-07", end_date: "2026-11-27", is_current: false, created_at: NOW },
];

// ─── Classes — Zimbabwe secondary school format ───

export const MOCK_CLASSES: SchoolClass[] = [
    { id: "cls-001", school_id: SCHOOL_ID, name: "Form 1A", section: "A", grade_level: 1, capacity: 45, is_active: true, created_at: NOW },
    { id: "cls-002", school_id: SCHOOL_ID, name: "Form 1B", section: "B", grade_level: 1, capacity: 45, is_active: true, created_at: NOW },
    { id: "cls-003", school_id: SCHOOL_ID, name: "Form 2A", section: "A", grade_level: 2, capacity: 42, is_active: true, created_at: NOW },
    { id: "cls-004", school_id: SCHOOL_ID, name: "Form 2B", section: "B", grade_level: 2, capacity: 40, is_active: true, created_at: NOW },
    { id: "cls-005", school_id: SCHOOL_ID, name: "Form 3A", section: "A", grade_level: 3, capacity: 38, is_active: true, created_at: NOW },
    { id: "cls-006", school_id: SCHOOL_ID, name: "Form 3B", section: "B", grade_level: 3, capacity: 38, is_active: true, created_at: NOW },
];

// Teacher (usr-002) assigned to Form 2A
export const MOCK_TEACHER_CLASSES: TeacherClass[] = [
    { ...MOCK_CLASSES[2], assignment_id: "ta-cls-003", academic_year_id: "ay-001" },
];

// ─── Subjects — Zimbabwe O-Level curriculum ───

export const MOCK_SUBJECTS: Subject[] = [
    { id: "sub-001", school_id: SCHOOL_ID, name: "Mathematics", code: "MATH", created_at: NOW },
    { id: "sub-002", school_id: SCHOOL_ID, name: "English Language", code: "ENG", created_at: NOW },
    { id: "sub-003", school_id: SCHOOL_ID, name: "Shona", code: "SHO", created_at: NOW },
    { id: "sub-004", school_id: SCHOOL_ID, name: "Ndebele", code: "NDE", created_at: NOW },
    { id: "sub-005", school_id: SCHOOL_ID, name: "Combined Science", code: "SCI", created_at: NOW },
    { id: "sub-006", school_id: SCHOOL_ID, name: "History", code: "HIS", created_at: NOW },
    { id: "sub-007", school_id: SCHOOL_ID, name: "Geography", code: "GEO", created_at: NOW },
    { id: "sub-008", school_id: SCHOOL_ID, name: "Agriculture", code: "AGR", created_at: NOW },
    { id: "sub-009", school_id: SCHOOL_ID, name: "Commerce", code: "COM", created_at: NOW },
    { id: "sub-010", school_id: SCHOOL_ID, name: "Accounts", code: "ACC", created_at: NOW },
    { id: "sub-011", school_id: SCHOOL_ID, name: "Art & Craft", code: "ART", created_at: NOW },
    { id: "sub-012", school_id: SCHOOL_ID, name: "Physical Education", code: "PE", created_at: NOW },
];

// ─── Students (30) — Zimbabwean names & Harare addresses ───

interface StudentExtra extends Student {
    address?: string;
    city?: string;
    phone?: string;
}

const STUDENT_NAMES: [string, string, string, string, string][] = [
    // [first, last, gender, suburb, dob-year]
    ["Tendai", "Moyo", "M", "Mbare", "2012"],
    ["Rudo", "Sibanda", "F", "Highfield", "2012"],
    ["Tatenda", "Nyathi", "M", "Glen Norah", "2011"],
    ["Chipo", "Dube", "F", "Kuwadzana", "2012"],
    ["Farai", "Mpofu", "M", "Chitungwiza", "2011"],
    ["Tariro", "Ncube", "F", "Budiriro", "2012"],
    ["Tinashe", "Ndlovu", "M", "Dzivarasekwa", "2011"],
    ["Tsitsi", "Gumbo", "F", "Mabelreign", "2012"],
    ["Kudakwashe", "Phiri", "M", "Harare CBD", "2011"],
    ["Nyasha", "Chirwa", "F", "Avondale", "2012"],
    ["Takudzwa", "Banda", "M", "Waterfalls", "2011"],
    ["Rumbidzai", "Mutasa", "F", "Tafara", "2012"],
    ["Blessing", "Chitiyo", "M", "Glen View", "2011"],
    ["Makanaka", "Zimunya", "F", "Hatfield", "2012"],
    ["Simbarashe", "Mhaka", "M", "Greendale", "2011"],
    ["Tambudzai", "Mugabe", "F", "Borrowdale", "2012"],
    ["Tawanda", "Chatiza", "M", "Msasa", "2011"],
    ["Rufaro", "Masuku", "F", "Braeside", "2012"],
    ["Munyaradzi", "Shava", "M", "Mufakose", "2011"],
    ["Yeukai", "Tembo", "F", "Epworth", "2012"],
    ["Prosper", "Hove", "M", "Kambuzuma", "2011"],
    ["Vimbai", "Mushonga", "F", "Sunningdale", "2012"],
    ["Kudzai", "Mafuta", "M", "Dzivarasekwa", "2011"],
    ["Rutendo", "Sigauke", "F", "Mbare", "2012"],
    ["Tafadzwa", "Mambo", "M", "Glen Norah", "2011"],
    ["Panashe", "Maposa", "F", "Highfield", "2012"],
    ["Simba", "Makoni", "M", "Harare CBD", "2011"],
    ["Gloria", "Mhuriro", "F", "Avondale", "2012"],
    ["Tinashe", "Chikwanda", "M", "Waterfalls", "2011"],
    ["Nyaradzo", "Gatsi", "F", "Chitungwiza", "2012"],
];

export const MOCK_STUDENTS: StudentExtra[] = STUDENT_NAMES.map(([first, last, gender, suburb, year], i) => ({
    id: uid("stu", i + 1), school_id: SCHOOL_ID,
    first_name: first, last_name: last,
    gender, date_of_birth: `${year}-${String((i % 12) + 1).padStart(2, "0")}-${String((i % 28) + 1).padStart(2, "0")}`,
    student_code: `STU-${String(i + 1).padStart(3, "0")}`,
    admission_date: "2026-01-12", status: i < 27 ? "active" : "inactive" as "active" | "inactive",
    is_active: i < 27,
    address: `${10 + i * 3} ${suburb} Road, ${suburb}, Harare`,
    city: "Harare",
    created_at: NOW, updated_at: NOW,
}));

// ─── Parents (25) ───

const PARENT_DATA: [string, string, string, string, string, string][] = [
    // [first, last, phone, email, relationship, suburb]
    ["Grace", "Moyo", "+263771234001", "grace.moyo@gmail.com", "Mother", "Mbare"],
    ["Joseph", "Sibanda", "+263771234002", "joseph.sibanda@gmail.com", "Father", "Highfield"],
    ["Memory", "Nyathi", "+263771234003", "memory.nyathi@yahoo.com", "Mother", "Glen Norah"],
    ["Peter", "Dube", "+263771234004", "peter.dube@gmail.com", "Father", "Kuwadzana"],
    ["Alice", "Mpofu", "+263771234005", "alice.mpofu@hotmail.com", "Mother", "Chitungwiza"],
    ["John", "Ncube", "+263771234006", "john.ncube@gmail.com", "Father", "Budiriro"],
    ["Esther", "Ndlovu", "+263771234007", "esther.ndlovu@gmail.com", "Mother", "Dzivarasekwa"],
    ["Daniel", "Gumbo", "+263771234008", "daniel.gumbo@yahoo.com", "Father", "Mabelreign"],
    ["Faith", "Phiri", "+263771234009", "faith.phiri@gmail.com", "Mother", "Harare CBD"],
    ["Michael", "Chirwa", "+263771234010", "michael.chirwa@gmail.com", "Father", "Avondale"],
    ["Sarah", "Banda", "+263771234011", "sarah.banda@gmail.com", "Mother", "Waterfalls"],
    ["Emmanuel", "Mutasa", "+263771234012", "emmanuel.mutasa@gmail.com", "Father", "Tafara"],
    ["Loveness", "Chitiyo", "+263771234013", "loveness.chitiyo@yahoo.com", "Mother", "Glen View"],
    ["Thomas", "Zimunya", "+263771234014", "thomas.zimunya@gmail.com", "Father", "Hatfield"],
    ["Ruth", "Mhaka", "+263771234015", "ruth.mhaka@gmail.com", "Mother", "Greendale"],
    ["George", "Mugabe", "+263771234016", "george.mugabe@hotmail.com", "Father", "Borrowdale"],
    ["Florence", "Chatiza", "+263771234017", "florence.chatiza@gmail.com", "Mother", "Msasa"],
    ["Samuel", "Masuku", "+263771234018", "samuel.masuku@gmail.com", "Father", "Braeside"],
    ["Martha", "Shava", "+263771234019", "martha.shava@gmail.com", "Mother", "Mufakose"],
    ["David", "Tembo", "+263771234020", "david.tembo@yahoo.com", "Father", "Epworth"],
    ["Patience", "Hove", "+263771234021", "patience.hove@gmail.com", "Mother", "Kambuzuma"],
    ["Isaiah", "Mushonga", "+263771234022", "isaiah.mushonga@gmail.com", "Father", "Sunningdale"],
    ["Blessed", "Mafuta", "+263771234023", "blessed.mafuta@gmail.com", "Mother", "Dzivarasekwa"],
    ["Raymond", "Sigauke", "+263771234024", "raymond.sigauke@gmail.com", "Father", "Mbare"],
    ["Constance", "Maposa", "+263771234025", "constance.maposa@yahoo.com", "Mother", "Highfield"],
];

export const MOCK_PARENTS: Parent[] = PARENT_DATA.map(([first, last, phone, email, relationship], i) => ({
    id: uid("par", i + 1), school_id: SCHOOL_ID,
    first_name: first, last_name: last, phone, email, relationship,
    created_at: NOW,
}));

// Parent → Student mapping
export const MOCK_PARENT_CHILDREN: Record<string, string[]> = {};
MOCK_PARENTS.forEach((p, i) => {
    const childIdxA = i * 1; // first child index
    const childIdxB = (i + 15) % 30; // second child (offset to avoid all pairs being adjacent)
    MOCK_PARENT_CHILDREN[p.id] = [
        MOCK_STUDENTS[childIdxA]?.id,
        childIdxB !== childIdxA ? MOCK_STUDENTS[childIdxB]?.id : undefined,
    ].filter((x): x is string => Boolean(x));
});

// The demo parent@eduzim.com is linked to Tendai Moyo (stu-001) only
MOCK_PARENT_CHILDREN[uid("par", 1)] = [MOCK_STUDENTS[0].id];

// ─── Enrollments (30) — distributed across 6 classes ───

export const MOCK_ENROLLMENTS: Enrollment[] = MOCK_STUDENTS.map((s, i) => ({
    id: uid("enr", i + 1), student_id: s.id,
    class_id: MOCK_CLASSES[i % 6].id, academic_year_id: "ay-001",
    status: "active", enrolled_at: "2026-01-12T08:00:00Z",
}));

// ─── Attendance — 30 days × 30 students ───

function genAttendanceDays(): { date: string; status: "P" | "A" | "L" }[] {
    const days: { date: string; status: "P" | "A" | "L" }[] = [];
    for (let i = 29; i >= 0; i--) {
        const d = new Date(Date.now() - i * 86400000);
        const dow = d.getDay(); // 0=Sun, 6=Sat
        if (dow === 0 || dow === 6) continue; // skip weekends
        days.push({
            date: d.toISOString().slice(0, 10),
            status: "P",
        });
    }
    return days;
}

const SCHOOL_DAYS = genAttendanceDays();

export const MOCK_ATTENDANCE_RECORDS: AttendanceDailyRecord[] = MOCK_STUDENTS.flatMap((s, si) => {
    const classId = MOCK_ENROLLMENTS[si].class_id;
    return SCHOOL_DAYS.map((day, di) => ({
        id: `att-${si + 1}-${di + 1}`,
        student_id: s.id, class_id: classId, date: day.date,
        // Sprinkle absences/lates realistically
        status: (si % 5 === 4 && di % 7 === 3) ? "A" :
            (si % 3 === 2 && di % 5 === 1) ? "L" : "P",
        last_modified_at: NOW,
    }));
});

export const MOCK_ATTENDANCE_SUMMARY: AttendanceDailySummary = {
    date: TODAY, P: 26, A: 2, L: 2, total: 30, attendance_rate: 86.7,
};

export const MOCK_ATTENDANCE_TREND: AttendanceStudentTrend = {
    student_id: "stu-001", from: SCHOOL_DAYS[0]?.date ?? TODAY, to: TODAY,
    total_days: SCHOOL_DAYS.length, present: Math.round(SCHOOL_DAYS.length * 0.9),
    absent: Math.round(SCHOOL_DAYS.length * 0.06), late: Math.round(SCHOOL_DAYS.length * 0.04),
    attendance_rate: 90,
    days: SCHOOL_DAYS.map((d, i) => ({
        date: d.date,
        status: i % 9 === 8 ? "A" : i % 7 === 6 ? "L" : "P",
    })),
};

export const MOCK_ATTENDANCE_CLASS_SUMMARY: AttendanceClassSummary = {
    class_id: "cls-003", from: SCHOOL_DAYS[0]?.date ?? TODAY, to: TODAY,
    days: SCHOOL_DAYS.map((d, i) => ({
        date: d.date, total: 5, present: 4 + (i % 2), absent: 1 - (i % 2),
        late: i % 3 === 0 ? 1 : 0, rate: 80 + (i % 2) * 10,
    })),
};

export const MOCK_SYNC_BATCHES: AttendanceSyncBatch[] = [
    { id: "sb-001", device_id: "dev-001", sync_batch_id: "batch-001", received_at: NOW, total_events: 30, accepted_count: 28, updated_count: 2, ignored_count: 0 },
    { id: "sb-002", device_id: "dev-001", sync_batch_id: "batch-002", received_at: NOW, total_events: 25, accepted_count: 25, updated_count: 0, ignored_count: 0 },
];

// ─── Fees — USD + ZWG (Zimbabwe Gold) ───

export const MOCK_FEE_STRUCTURES: FeeStructure[] = [
    {
        id: "fs-001", school_id: SCHOOL_ID, academic_year_id: "ay-001", term_id: "term-001",
        name: "Term 1 School Fees — 2026", is_active: true, total: 450,
        items: [
            { id: "fi-001", label: "Tuition", amount: 300, currency: "USD" },
            { id: "fi-002", label: "Development Levy", amount: 60, currency: "USD" },
            { id: "fi-003", label: "Sports & Recreation", amount: 40, currency: "USD" },
            { id: "fi-004", label: "Library", amount: 30, currency: "USD" },
            { id: "fi-005", label: "ICT", amount: 20, currency: "USD" },
        ],
        created_at: NOW,
    },
    {
        id: "fs-002", school_id: SCHOOL_ID, academic_year_id: "ay-001", term_id: "term-001",
        name: "Term 1 Activity Fees — 2026", is_active: true, total: 80,
        items: [
            { id: "fi-006", label: "Drama Club", amount: 20, currency: "USD" },
            { id: "fi-007", label: "Music", amount: 25, currency: "USD" },
            { id: "fi-008", label: "Field Trips", amount: 35, currency: "USD" },
        ],
        created_at: NOW,
    },
];

export const MOCK_INVOICES: Invoice[] = MOCK_STUDENTS.map((s, i) => {
    const paid = i < 20 ? 450 : i < 26 ? 225 : 0;
    const status = paid >= 450 ? "PAID" : paid > 0 ? "PARTIAL" : "UNPAID";
    return {
        id: uid("inv", i + 1), school_id: SCHOOL_ID, student_id: s.id,
        fee_structure_id: "fs-001", total_amount: 450, paid_amount: paid,
        balance: 450 - paid, currency: "USD",
        due_date: "2026-02-28", status,
        created_at: NOW,
    };
});

export const MOCK_PAYMENTS: Payment[] = MOCK_INVOICES.filter((inv) => inv.paid_amount > 0).map((inv, i) => ({
    id: uid("pay", i + 1), school_id: SCHOOL_ID, invoice_id: inv.id,
    amount: inv.paid_amount, currency: "USD",
    method: i % 3 === 0 ? "CASH" : i % 3 === 1 ? "EcoCash" : "ZIPIT",
    reference: `TXN-2026${String(1000 + i).padStart(4, "0")}`,
    paid_at: NOW, created_at: NOW,
}));

export const MOCK_DEFAULTERS: Invoice[] = MOCK_INVOICES.filter((inv) => inv.balance > 0);

// ─── Communication ───

export const MOCK_ANNOUNCEMENTS: Announcement[] = [
    { id: "ann-001", school_id: SCHOOL_ID, title: "Welcome Back — Term 1 2026", body: "Dear parents and guardians, welcome back to the 2026 academic year at Harare Central Secondary School. We trust you all had a restful holiday and are ready for a productive term.", audience_type: "ALL", audience_class_id: null, audience_role: null, created_by: "usr-001", created_at: "2026-01-12T08:00:00Z", deleted_at: null },
    { id: "ann-002", school_id: SCHOOL_ID, title: "National Schools Sports Day — 28 March 2026", body: "All students are encouraged to participate in the National Schools Sports Day on 28 March. PE kits are mandatory. Parental consent forms available at the school office.", audience_type: "ALL", audience_class_id: null, audience_role: null, created_by: "usr-001", created_at: "2026-02-20T10:00:00Z", deleted_at: null },
    { id: "ann-003", school_id: SCHOOL_ID, title: "Form 2A Science Trip — Harare Gardens", body: "Form 2A will conduct a botanical study at Harare Gardens on 25 March 2026. Signed permission slips and $5 contribution required by 20 March.", audience_type: "CLASS", audience_class_id: "cls-003", audience_role: null, created_by: "usr-002", created_at: "2026-03-01T09:00:00Z", deleted_at: null },
    { id: "ann-004", school_id: SCHOOL_ID, title: "Term 1 Fee Payment Deadline", body: "Kindly ensure all Term 1 2026 fees are settled by 28 February 2026 to avoid disruptions to your child's education. Contact the bursar's office for payment plans.", audience_type: "ALL", audience_class_id: null, audience_role: "parent", created_by: "usr-001", created_at: "2026-03-02T14:00:00Z", deleted_at: null },
    { id: "ann-005", school_id: SCHOOL_ID, title: "Parent-Teacher Meetings — 28 March 2026", body: "Parent-teacher consultation meetings are scheduled for 28 March 2026 from 8:00 AM – 1:00 PM. Please confirm your preferred time slot with the class teacher.", audience_type: "ALL", audience_class_id: null, audience_role: null, created_by: "usr-001", created_at: "2026-03-03T08:00:00Z", deleted_at: null },
    { id: "ann-006", school_id: SCHOOL_ID, title: "Zimbabwe Schools Examination Notice", body: "ZIMSEC O-Level trial examinations for Form 3 students will commence on 20 April 2026. Timetables are available at the school reception.", audience_type: "ALL", audience_class_id: null, audience_role: null, created_by: "usr-001", created_at: "2026-03-10T11:00:00Z", deleted_at: null },
];

export const MOCK_OUTBOX: OutboxEntry[] = MOCK_ANNOUNCEMENTS.flatMap((ann, ai) =>
    [0, 1, 2].map((ui) => ({
        id: `ob-${ai + 1}-${ui + 1}`, school_id: SCHOOL_ID, announcement_id: ann.id,
        user_id: uid("usr", ui + 1), channel: ui === 0 ? "SMS" : "EMAIL",
        status: ui === 2 ? "FAILED" : "SENT", retry_count: ui === 2 ? 2 : 0,
        last_attempt_at: NOW, error_message: ui === 2 ? "Network timeout" : null, created_at: NOW,
    }))
);

// ─── Dashboard ───

export const MOCK_DASHBOARD: DashboardData = {
    total_students: 30, active_students: 27, total_enrollments: 30,
    total_classes: 6, attendance_today_rate: 0.867, attendance_rate: 0.867,
    outstanding_fees: 1800, total_outstanding: 1800, total_revenue: 11700,
    collected_this_term: 11700, announcements_this_month: 4, announcements_count: 6,
};

// ─── Attendance Trend (Reports) ───

export const MOCK_ATTENDANCE_TREND_POINTS: AttendanceTrendPoint[] =
    SCHOOL_DAYS.map((d, i) => ({
        date: d.date, present: 25 + (i % 4), absent: 3 - (i % 3), late: 2 - (i % 2), total: 30,
        rate: (25 + (i % 4)) / 30,
    }));

// ─── Financial Summary ───

export const MOCK_FINANCIAL_SUMMARY: FinancialSummaryData[] = [{
    academic_year_id: "ay-001", total_invoiced: 13500, total_paid: 11700, total_outstanding: 1800,
}];

// ─── Dropout Intelligence ───

export const MOCK_DROPOUT_SUMMARY: DropoutSummary = {
    total_students: 30, at_risk_count: 5,
    band_breakdown: { LOW: 2, MEDIUM: 2, HIGH: 1, CRITICAL: 0 },
    top_signals: [
        { code: "ABSENCE_STREAK", count: 3 },
        { code: "FEE_ARREARS", count: 4 },
    ],
};

export const MOCK_DROPOUT_STUDENTS: DropoutStudentRow[] = [
    { student_id: "stu-025", student_code: "STU-025", first_name: "Tafadzwa", last_name: "Mambo", risk_score: 76, risk_band: "HIGH", signal_count: 3, top_signal: "Absent 6 consecutive school days" },
    { student_id: "stu-028", student_code: "STU-028", first_name: "Gloria", last_name: "Mhuriro", risk_score: 58, risk_band: "MEDIUM", signal_count: 2, top_signal: "Fee arrears exceeding 90 days" },
    { student_id: "stu-019", student_code: "STU-019", first_name: "Munyaradzi", last_name: "Shava", risk_score: 54, risk_band: "MEDIUM", signal_count: 2, top_signal: "Declining attendance trend" },
    { student_id: "stu-023", student_code: "STU-023", first_name: "Kudzai", last_name: "Mafuta", risk_score: 32, risk_band: "LOW", signal_count: 1, top_signal: "3 absences in past 14 days" },
    { student_id: "stu-030", student_code: "STU-030", first_name: "Nyaradzo", last_name: "Gatsi", risk_score: 28, risk_band: "LOW", signal_count: 1, top_signal: "Late arrival pattern" },
];

export const MOCK_DROPOUT_DETAIL: DropoutStudentDetail = {
    student_id: "stu-025", risk_score: 76, risk_band: "HIGH",
    signals: [
        { code: "ABSENCE_STREAK", label: "Absence Streak", points: 30, evidence: "Absent 6 consecutive school days (Mar 2–9, 2026)" },
        { code: "FEE_ARREARS", label: "Fee Arrears", points: 28, evidence: "Outstanding balance $450 unpaid for 42 days" },
        { code: "LATE_PATTERN", label: "Late Arrival", points: 18, evidence: "Late 5 times in the past 3 weeks" },
    ],
    computed_at: NOW, lookback_days: 30,
};

// ─── Teachers (Users) ───

export const MOCK_TEACHERS = [
    { id: "usr-002", email: "teacher@eduzim.com", full_name: "Takesure Moyo", class: "Form 2A", subjects: ["Mathematics", "Science"], employee_id: "EMP-002", phone: "+263772000001" },
    { id: "usr-004", email: "mufundiwa.dube@hararecentral.edu.zw", full_name: "Mufundiwa Dube", class: "Form 1A", subjects: ["English Language", "History"], employee_id: "EMP-004", phone: "+263772000002" },
    { id: "usr-005", email: "tendai.ncube@hararecentral.edu.zw", full_name: "Tendai Ncube", class: "Form 1B", subjects: ["Shona", "Ndebele"], employee_id: "EMP-005", phone: "+263772000003" },
    { id: "usr-006", email: "prisca.chirwa@hararecentral.edu.zw", full_name: "Prisca Chirwa", class: "Form 2B", subjects: ["Geography", "Agriculture"], employee_id: "EMP-006", phone: "+263772000004" },
    { id: "usr-007", email: "elias.banda@hararecentral.edu.zw", full_name: "Elias Banda", class: "Form 3A", subjects: ["Commerce", "Accounts"], employee_id: "EMP-007", phone: "+263772000005" },
    { id: "usr-008", email: "rudo.mutasa@hararecentral.edu.zw", full_name: "Rudo Mutasa", class: "Form 3B", subjects: ["Art & Craft", "Physical Education"], employee_id: "EMP-008", phone: "+263772000006" },
];

// ─── Users ───

export const MOCK_USERS: User[] = [
    { id: "usr-001", email: "admin@eduzim.com", full_name: "Adminstrator Harare Central", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-001", name: "SchoolAdmin" }], permissions: ["*"] },
    { id: "usr-002", email: "teacher@eduzim.com", full_name: "Takesure Moyo", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read", "comm:read"] },
    { id: "usr-003", email: "parent@eduzim.com", full_name: "Grace Moyo", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-003", name: "Parent" }], permissions: ["student:read", "fees:read", "comm:read"] },
    { id: "usr-004", email: "mufundiwa.dube@hararecentral.edu.zw", full_name: "Mufundiwa Dube", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read"] },
    { id: "usr-005", email: "tendai.ncube@hararecentral.edu.zw", full_name: "Tendai Ncube", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read"] },
    { id: "usr-006", email: "prisca.chirwa@hararecentral.edu.zw", full_name: "Prisca Chirwa", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read"] },
    { id: "usr-007", email: "elias.banda@hararecentral.edu.zw", full_name: "Elias Banda", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read"] },
    { id: "usr-008", email: "rudo.mutasa@hararecentral.edu.zw", full_name: "Rudo Mutasa", school_id: SCHOOL_ID, is_active: true, created_at: NOW, updated_at: NOW, roles: [{ id: "role-002", name: "Teacher" }], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read"] },
];

export const MOCK_ROLES: Role[] = [
    { id: "role-001", name: "SchoolAdmin", description: "Full system access for school administration", school_id: SCHOOL_ID, created_at: NOW, permissions: [{ id: "perm-001", name: "*", resource: "*", action: "*" }] },
    { id: "role-002", name: "Teacher", description: "Class management, attendance and assessments", school_id: SCHOOL_ID, created_at: NOW, permissions: [{ id: "perm-002", name: "attendance:read", resource: "attendance", action: "read" }, { id: "perm-003", name: "attendance:write", resource: "attendance", action: "write" }] },
    { id: "role-003", name: "Parent", description: "View child information, attendance and fees", school_id: SCHOOL_ID, created_at: NOW, permissions: [{ id: "perm-004", name: "student:read", resource: "student", action: "read" }] },
];

export const MOCK_PERMISSIONS: Permission[] = [
    { id: "perm-001", name: "*", resource: "*", action: "*", description: "Full access" },
    { id: "perm-002", name: "attendance:read", resource: "attendance", action: "read" },
    { id: "perm-003", name: "attendance:write", resource: "attendance", action: "write" },
    { id: "perm-004", name: "student:read", resource: "student", action: "read" },
    { id: "perm-005", name: "student:write", resource: "student", action: "write" },
    { id: "perm-006", name: "school:manage", resource: "school", action: "manage" },
    { id: "perm-007", name: "report:read", resource: "report", action: "read" },
    { id: "perm-008", name: "fees:read", resource: "fees", action: "read" },
    { id: "perm-009", name: "fees:write", resource: "fees", action: "write" },
    { id: "perm-010", name: "comm:read", resource: "comm", action: "read" },
    { id: "perm-011", name: "comm:write", resource: "comm", action: "write" },
    { id: "perm-012", name: "assessment:read", resource: "assessment", action: "read" },
    { id: "perm-013", name: "assessment:write", resource: "assessment", action: "write" },
];

// ─── Assessments ───

export const MOCK_ASSESSMENTS: Assessment[] = MOCK_SUBJECTS.slice(0, 6).map((sub, i) => ({
    id: uid("asm", i + 1), school_id: SCHOOL_ID, academic_year_id: "ay-001",
    term_id: "term-001", class_id: "cls-003", subject_id: sub.id,
    name: `${sub.name} — Test 1`, assessment_type: i % 2 === 0 ? "TEST" : "QUIZ" as const,
    date: "2026-02-28", max_marks: 100,
    created_by: "usr-002", created_at: NOW, updated_at: NOW,
}));

export const MOCK_MARK_ENTRIES: MarkEntry[] = MOCK_ASSESSMENTS.flatMap((asm, ai) =>
    MOCK_STUDENTS.slice(0, 5).map((s, si) => ({
        id: `mk-${ai + 1}-${si + 1}`, assessment_id: asm.id, student_id: s.id,
        marks: 45 + Math.floor((ai * 7 + si * 13) % 50), is_absent: false,
        remarks: null, graded_by: "usr-002", graded_at: NOW,
    }))
);

export const MOCK_ASSESSMENT_DETAILS: AssessmentDetail[] = MOCK_ASSESSMENTS.map((asm) => ({
    ...asm,
    marks: MOCK_MARK_ENTRIES.filter((m) => m.assessment_id === asm.id),
}));

export const MOCK_STUDENT_SUBJECT_MARKS: StudentSubjectMarks[] = MOCK_SUBJECTS.slice(0, 6).map((sub, si) => ({
    subject_id: sub.id, average_pct: 60 + (si * 6) % 30, graded_count: 1,
    assessments: [{
        assessment: MOCK_ASSESSMENTS[si],
        mark: MOCK_MARK_ENTRIES.find((m) => m.assessment_id === MOCK_ASSESSMENTS[si]?.id) ?? MOCK_MARK_ENTRIES[0],
    }],
}));

export const MOCK_CLASS_PERFORMANCE: ClassPerformance = {
    subjects: MOCK_SUBJECTS.slice(0, 6).map((sub, si) => ({
        subject_id: sub.id, avg_pct: 65 + (si * 4) % 22,
        pass_rate: 75 + (si * 3) % 20, assessment_count: 1, student_count: 5,
    })),
};

// ─── Auth — role-based MOCK_ME per user type ───

const MOCK_ME_ADMIN: MeData = {
    id: "usr-001", email: "admin@eduzim.com", full_name: "Administrator — Harare Central",
    school_id: SCHOOL_ID, is_active: true,
    roles: ["SchoolAdmin"], permissions: ["*"],
};

const MOCK_ME_TEACHER: MeData = {
    id: "usr-002", email: "teacher@eduzim.com", full_name: "Takesure Moyo",
    school_id: SCHOOL_ID, is_active: true,
    roles: ["Teacher"], permissions: ["attendance:read", "attendance:write", "assessment:read", "assessment:write", "student:read", "comm:read"],
};

const MOCK_ME_PARENT: MeData = {
    id: "usr-003", email: "parent@eduzim.com", full_name: "Grace Moyo",
    school_id: SCHOOL_ID, is_active: true,
    roles: ["Parent"], permissions: ["student:read", "fees:read", "comm:read"],
};

export function getMockMeForUser(email: string): MeData {
    if (email === "teacher@eduzim.com") return MOCK_ME_TEACHER;
    if (email === "parent@eduzim.com") return MOCK_ME_PARENT;
    return MOCK_ME_ADMIN;
}

export function getMockLoginForUser(email: string): LoginData {
    const me = getMockMeForUser(email);
    return {
        access_token: `mock-jwt-${me.roles[0]?.toLowerCase()}-token`,
        refresh_token: `mock-refresh-${me.roles[0]?.toLowerCase()}`,
        expires_in: 3600,
        user: { id: me.id, name: me.full_name, email: me.email, roles: me.roles },
    };
}

// Legacy exports for backwards compatibility
export const MOCK_ME = MOCK_ME_ADMIN;
export const MOCK_LOGIN = getMockLoginForUser("admin@eduzim.com");

