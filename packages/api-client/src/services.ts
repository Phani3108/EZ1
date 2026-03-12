/**
 * EduZim API Client — Service Methods
 * =====================================
 * Typed wrappers for every backend endpoint the UI needs.
 */

import type { ApiClient } from "./client";
import type {
  LoginRequest,
  LoginData,
  MeData,
  AcademicYear,
  Term,
  SchoolClass,
  TeacherClass,
  Subject,
  Student,
  Parent,
  Enrollment,
  AttendanceDailySummary,
  AttendanceDailyRecord,
  AttendanceStudentTrend,
  AttendanceClassSummary,
  AttendanceSyncBatch,
  AttendanceSyncRequest,
  AttendanceSyncResult,
  FeeStructure,
  Invoice,
  Payment,
  Defaulter,
  Announcement,
  OutboxEntry,
  DashboardData,
  AttendanceTrendPoint,
  FinancialSummaryData,
  DropoutSummary,
  DropoutStudentRow,
  DropoutStudentDetail,
  User,
  Role,
  Permission,
  Assessment,
  AssessmentDetail,
  BulkMarksResult,
  StudentSubjectMarks,
  ClassPerformance,
  CreateAssessmentRequest,
  BulkMarksRequest,
} from "./types";

// ─── Auth ───

export function authApi(client: ApiClient) {
  return {
    login(data: LoginRequest) {
      return client.post<LoginData>("/api/v1/auth/login", data);
    },
    me() {
      return client.get<MeData>("/api/v1/auth/me");
    },
    refresh() {
      return client.post<LoginData>("/api/v1/auth/refresh", {});
    },
    logout() {
      return client.post<{ message: string }>("/api/v1/auth/logout");
    },
  };
}

// ─── School / Academics ───

export function schoolApi(client: ApiClient) {
  return {
    // Academic years
    listAcademicYears(params?: Record<string, string>) {
      return client.get<AcademicYear[]>("/api/v1/academic-years", params);
    },
    getAcademicYear(id: string) {
      return client.get<AcademicYear>(`/api/v1/academic-years/${id}`);
    },
    createAcademicYear(data: Partial<AcademicYear>) {
      return client.post<AcademicYear>("/api/v1/academic-years", data);
    },
    updateAcademicYear(id: string, data: Partial<AcademicYear>) {
      return client.put<AcademicYear>(`/api/v1/academic-years/${id}`, data);
    },

    // Terms
    listTerms(params?: Record<string, string>) {
      return client.get<Term[]>("/api/v1/terms", params);
    },
    createTerm(data: Partial<Term>) {
      return client.post<Term>("/api/v1/terms", data);
    },
    updateTerm(id: string, data: Partial<Term>) {
      return client.put<Term>(`/api/v1/terms/${id}`, data);
    },

    // Classes
    listClasses(params?: Record<string, string>) {
      return client.get<SchoolClass[]>("/api/v1/classes", params);
    },
    getClass(id: string) {
      return client.get<SchoolClass>(`/api/v1/classes/${id}`);
    },
    createClass(data: Partial<SchoolClass>) {
      return client.post<SchoolClass>("/api/v1/classes", data);
    },
    updateClass(id: string, data: Partial<SchoolClass>) {
      return client.put<SchoolClass>(`/api/v1/classes/${id}`, data);
    },
    deleteClass(id: string) {
      return client.delete<void>(`/api/v1/classes/${id}`);
    },

    // Subjects
    listSubjects(params?: Record<string, string>) {
      return client.get<Subject[]>("/api/v1/subjects", params);
    },
    createSubject(data: Partial<Subject>) {
      return client.post<Subject>("/api/v1/subjects", data);
    },
    updateSubject(id: string, data: Partial<Subject>) {
      return client.put<Subject>(`/api/v1/subjects/${id}`, data);
    },
    deleteSubject(id: string) {
      return client.delete<void>(`/api/v1/subjects/${id}`);
    },
  };
}

// ─── Teacher Self-Service ───

export function teacherApi(client: ApiClient) {
  return {
    getMyClasses() {
      return client.get<TeacherClass[]>("/api/v1/teachers/me/classes");
    },
  };
}

// ─── Students ───

export function studentApi(client: ApiClient) {
  return {
    list(params?: Record<string, string>) {
      return client.get<Student[]>("/api/v1/students", params);
    },
    get(id: string) {
      return client.get<Student>(`/api/v1/students/${id}`);
    },
    create(data: Partial<Student>) {
      return client.post<Student>("/api/v1/students", data);
    },
    update(id: string, data: Partial<Student>) {
      return client.put<Student>(`/api/v1/students/${id}`, data);
    },
    delete(id: string) {
      return client.delete<void>(`/api/v1/students/${id}`);
    },
    getStudentParents(studentId: string) {
      return client.get<Parent[]>(`/api/v1/students/${studentId}/parents`);
    },
    getStudentEnrollments(studentId: string) {
      return client.get<Enrollment[]>(`/api/v1/students/${studentId}/enrollments`);
    },

    // Parents
    listParents(params?: Record<string, string>) {
      return client.get<Parent[]>("/api/v1/parents", params);
    },
    getParent(id: string) {
      return client.get<Parent>(`/api/v1/parents/${id}`);
    },
    createParent(data: Partial<Parent>) {
      return client.post<Parent>("/api/v1/parents", data);
    },
    updateParent(id: string, data: Partial<Parent>) {
      return client.put<Parent>(`/api/v1/parents/${id}`, data);
    },
    deleteParent(id: string) {
      return client.delete<void>(`/api/v1/parents/${id}`);
    },
    getParentChildren(parentId: string) {
      return client.get<Student[]>(`/api/v1/parents/${parentId}/children`);
    },
    getMyChildren() {
      return client.get<Student[]>("/api/v1/parents/me/children");
    },
    linkParent(studentId: string, parentId: string) {
      return client.post<void>(
        `/api/v1/students/${studentId}/parents/${parentId}`
      );
    },
    unlinkParent(studentId: string, parentId: string) {
      return client.delete<void>(
        `/api/v1/students/${studentId}/parents/${parentId}`
      );
    },

    // Enrollments
    listEnrollments(params?: Record<string, string>) {
      return client.get<Enrollment[]>("/api/v1/enrollments", params);
    },
    getEnrollmentsByClass(classId: string, academicYearId?: string) {
      const params: Record<string, string> = { class_id: classId };
      if (academicYearId) params.academic_year_id = academicYearId;
      return client.get<Enrollment[]>("/api/v1/enrollments", params);
    },
    createEnrollment(data: Partial<Enrollment>) {
      return client.post<Enrollment>("/api/v1/enrollments", data);
    },
    updateEnrollment(id: string, data: Partial<Enrollment>) {
      return client.put<Enrollment>(`/api/v1/enrollments/${id}`, data);
    },
  };
}

// ─── Attendance ───

export function attendanceApi(client: ApiClient) {
  return {
    dailySummary(params: Record<string, string>) {
      return client.get<AttendanceDailySummary>(
        "/api/v1/attendance/daily",
        params
      );
    },
    dailyRecords(params: Record<string, string>) {
      return client.get<AttendanceDailyRecord[]>(
        "/api/v1/attendance/daily/records",
        params
      );
    },
    studentTrend(params: Record<string, string>) {
      return client.get<AttendanceStudentTrend>(
        "/api/v1/attendance/student-trend",
        params
      );
    },
    classSummary(params: Record<string, string>) {
      return client.get<AttendanceClassSummary>(
        "/api/v1/attendance/class-summary",
        params
      );
    },
    syncBatches(params?: Record<string, string>) {
      return client.get<AttendanceSyncBatch[]>(
        "/api/v1/attendance/sync/batches",
        params
      );
    },
    syncAttendance(data: AttendanceSyncRequest) {
      return client.post<AttendanceSyncResult>(
        "/api/v1/attendance/sync",
        data
      );
    },
  };
}

// ─── Fees ───

export function feesApi(client: ApiClient) {
  return {
    listStructures(params?: Record<string, string>) {
      return client.get<FeeStructure[]>("/api/v1/fees/structures", params);
    },
    createStructure(data: Record<string, unknown>) {
      return client.post<FeeStructure>("/api/v1/fees/structures", data);
    },
    listInvoices(params?: Record<string, string>) {
      return client.get<Invoice[]>("/api/v1/fees/invoices", params);
    },
    createInvoice(data: Record<string, unknown>) {
      return client.post<Invoice>("/api/v1/fees/invoices", data);
    },
    recordPayment(data: Record<string, unknown>) {
      return client.post<{ payment: Payment; invoice: Invoice; already_processed: boolean }>(
        "/api/v1/fees/payments", data,
      );
    },
    listPayments(params?: Record<string, string>) {
      return client.get<Payment[]>("/api/v1/fees/payments", params);
    },
    listDefaulters(params?: Record<string, string>) {
      return client.get<Defaulter[]>("/api/v1/fees/defaulters", params);
    },
  };
}

// ─── Communication ───

export function commApi(client: ApiClient) {
  return {
    listAnnouncements(params?: Record<string, string>) {
      return client.get<Announcement[]>("/api/v1/comm/announcements", params);
    },
    getFeed(params: Record<string, string>) {
      return client.get<Announcement[]>("/api/v1/comm/feed", params);
    },
    createAnnouncement(data: Record<string, unknown>) {
      return client.post<{ announcement: Announcement; outbox_created: number; recipient_count: number; channels: string[] }>("/api/v1/comm/announcements", data);
    },
    deleteAnnouncement(id: string) {
      return client.delete<Announcement>(`/api/v1/comm/announcements/${id}`);
    },
    listOutbox(params?: Record<string, string>) {
      return client.get<OutboxEntry[]>("/api/v1/comm/outbox", params);
    },
  };
}

// ─── Reports ───

export function reportsApi(client: ApiClient) {
  return {
    dashboard() {
      return client.get<DashboardData>("/api/v1/reports/dashboard");
    },
    attendanceTrend(params: Record<string, string>) {
      return client.get<AttendanceTrendPoint[]>("/api/v1/reports/attendance/trend", params);
    },
    financialSummary(params?: Record<string, string>) {
      return client.get<FinancialSummaryData[]>("/api/v1/reports/financial/summary", params);
    },

    // Dropout Intelligence
    dropoutSummary() {
      return client.get<DropoutSummary>("/api/v1/reports/dropout/summary");
    },
    dropoutStudents(params?: Record<string, string>) {
      return client.get<DropoutStudentRow[]>("/api/v1/reports/dropout/students", params);
    },
    dropoutStudentDetail(studentId: string) {
      return client.get<DropoutStudentDetail>(
        `/api/v1/reports/dropout/student/${studentId}`
      );
    },
  };
}

// ─── Users & Roles ───

export function usersApi(client: ApiClient) {
  return {
    list(params?: Record<string, string>) {
      return client.get<User[]>("/api/v1/users", params);
    },
    get(id: string) {
      return client.get<User>(`/api/v1/users/${id}`);
    },
    create(data: Record<string, unknown>) {
      return client.post<User>("/api/v1/users", data);
    },
    update(id: string, data: Record<string, unknown>) {
      return client.put<User>(`/api/v1/users/${id}`, data);
    },
    resetPassword(id: string, newPassword: string) {
      return client.post<{ message: string }>(
        `/api/v1/users/${id}/reset-password`,
        { new_password: newPassword }
      );
    },

    // Roles
    listRoles() {
      return client.get<Role[]>("/api/v1/roles");
    },
    createRole(data: Partial<Role>) {
      return client.post<Role>("/api/v1/roles", data);
    },
    updateRole(id: string, data: Partial<Role>) {
      return client.put<Role>(`/api/v1/roles/${id}`, data);
    },
    assignPermission(roleId: string, permissionId: string) {
      return client.post<Role>(`/api/v1/roles/${roleId}/permissions`, {
        permission_id: permissionId,
      });
    },

    // Permissions
    listPermissions() {
      return client.get<Permission[]>("/api/v1/permissions");
    },
  };
}

// ─── Assessments ───

export function assessmentApi(client: ApiClient) {
  return {
    create(data: CreateAssessmentRequest) {
      return client.post<Assessment>("/api/v1/assessments", data);
    },
    list(params: { class_id: string; term_id: string; subject_id?: string }) {
      return client.get<Assessment[]>("/api/v1/assessments", params as Record<string, string>);
    },
    get(id: string) {
      return client.get<AssessmentDetail>(`/api/v1/assessments/${id}`);
    },
    bulkUpsertMarks(assessmentId: string, data: BulkMarksRequest) {
      return client.post<BulkMarksResult>(
        `/api/v1/assessments/${assessmentId}/marks/bulk`,
        data
      );
    },
    studentMarks(studentId: string, params?: { term_id?: string }) {
      return client.get<StudentSubjectMarks[]>(
        `/api/v1/assessments/students/${studentId}/marks`,
        params as Record<string, string>
      );
    },
    classPerformance(classId: string, params?: { term_id?: string }) {
      return client.get<ClassPerformance>(
        `/api/v1/assessments/classes/${classId}/performance`,
        params as Record<string, string>
      );
    },
  };
}
