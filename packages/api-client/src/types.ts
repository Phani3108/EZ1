/**
 * EduZim API Client — Types
 * ==========================
 * Shared types matching the backend envelope format.
 */

// ─── Envelope ───

export interface ApiMeta {
  request_id: string;
  timestamp: string;
  page?: number;
  page_size?: number;
  total?: number;
  has_next?: boolean;
}

export interface ApiSuccess<T> {
  data: T;
  meta: ApiMeta;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export type ApiResponse<T> = ApiSuccess<T>;

// ─── Auth ───

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserBrief {
  id: string;
  name: string;
  email: string;
  roles: string[];
}

export interface LoginData {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: UserBrief;
}

export interface UserPreferences {
  language: "en" | "sn" | "nd";
  theme_pref: "joyful" | "focus" | "sovereign";
  text_size: "sm" | "md" | "lg" | "xl";
  high_contrast: boolean;
  read_aloud_enabled: boolean;
  reduced_motion: boolean;
}

export interface MeData {
  id: string;
  email: string;
  full_name: string;
  school_id: string;
  is_active: boolean;
  roles: string[];
  permissions: string[];
  preferences: UserPreferences;
}

// ─── School / Academics ───

export interface AcademicYear {
  id: string;
  school_id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  created_at: string;
}

export interface Term {
  id: string;
  academic_year_id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  created_at: string;
}

export interface SchoolClass {
  id: string;
  school_id: string;
  name: string;
  section: string;
  grade_level?: number;
  capacity: number | null;
  is_active: boolean;
  created_at: string;
}

export interface TeacherClass extends SchoolClass {
  assignment_id: string;
  academic_year_id: string;
}

export interface Subject {
  id: string;
  school_id: string;
  name: string;
  code: string;
  description?: string;
  created_at: string;
}

// ─── Students ───

export interface Student {
  id: string;
  school_id: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string;
  dob?: string;
  gender?: string;
  admission_number?: string;
  student_code?: string;
  admission_date?: string;
  status?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at?: string;
}

export interface Parent {
  id: string;
  school_id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  relationship?: string;
  created_at: string;
}

export interface Enrollment {
  id: string;
  student_id: string;
  class_id: string;
  academic_year_id: string;
  status: string;
  enrolled_at: string;
}

// ─── Attendance ───

export interface AttendanceDailySummary {
  date: string;
  P: number;
  A: number;
  L: number;
  total: number;
  attendance_rate: number;
}

export interface AttendanceDailyRecord {
  id: string;
  student_id: string;
  class_id: string;
  date: string;
  status: string;
  /**
   * Phase 11a / T-002. 0 = daily / homeroom mark (legacy). 1..N = a
   * specific period in the school's schedule. Optional on the wire so
   * older clients that don't know about periods still parse correctly.
   */
  period_number?: number;
  marked_by_user_id?: string;
  last_modified_at: string;
}

export interface AttendanceStudentTrend {
  student_id: string;
  from: string;
  to: string;
  total_days: number;
  present: number;
  absent: number;
  late: number;
  attendance_rate: number;
  days: { date: string; status: string }[];
}

export interface AttendanceClassSummary {
  class_id: string;
  from: string;
  to: string;
  days: { date: string; total: number; present: number; absent: number; late: number; rate: number }[];
}

export interface AttendanceSyncBatch {
  id: string;
  device_id: string;
  sync_batch_id: string;
  received_at: string;
  total_events: number;
  accepted_count: number;
  updated_count: number;
  ignored_count: number;
}

export interface AttendanceSyncEvent {
  client_event_id: string;
  class_id: string;
  student_id: string;
  date: string;
  status: "P" | "A" | "L";
  /**
   * Phase 11a / T-002. Optional in the wire payload — when omitted, the
   * backend treats it as 0 (daily / homeroom / all-day mark, the legacy
   * single-row-per-student-per-day mode). Set to 1..N to record an
   * attendance row for a specific period (secondary-school mode).
   */
  period_number?: number;
  last_modified_at: string;
}

export interface AttendanceSyncRequest {
  device_id: string;
  sync_batch_id: string;
  generated_at?: string;
  events: AttendanceSyncEvent[];
}

export interface AttendanceSyncResult {
  accepted: number;
  updated: number;
  ignored: number;
  already_processed?: boolean;
}

// ─── Fees ───

export interface FeeItem {
  id: string;
  label: string;
  amount: number;
  currency: string;
}

export interface FeeStructure {
  id: string;
  school_id: string;
  academic_year_id: string;
  term_id?: string;
  name: string;
  is_active: boolean;
  items: FeeItem[];
  total: number;
  created_at: string;
}

export interface Invoice {
  id: string;
  school_id: string;
  student_id: string;
  fee_structure_id: string;
  total_amount: number;
  paid_amount: number;
  balance: number;
  currency: string;
  due_date: string;
  status: string;
  created_at: string;
}

export interface Payment {
  id: string;
  school_id: string;
  invoice_id: string;
  amount: number;
  currency: string;
  method: string;
  reference?: string;
  paid_at: string;
  created_at: string;
}

// Defaulters endpoint returns Invoice[] (overdue invoices)
export type Defaulter = Invoice;

// ─── Communication ───

export interface Announcement {
  id: string;
  school_id: string;
  title: string;
  body: string;
  audience_type: string;
  audience_class_id: string | null;
  audience_role: string | null;
  created_by: string;
  created_at: string;
  deleted_at: string | null;
}

export interface OutboxEntry {
  id: string;
  school_id: string;
  announcement_id: string;
  user_id: string;
  channel: string;
  status: string;
  retry_count: number;
  last_attempt_at: string | null;
  error_message: string | null;
  created_at: string;
}

// ─── Phase 11b / T-011 — parent-teacher messaging ───

export interface MessageThread {
  id: string;
  school_id: string;
  teacher_user_id: string;
  parent_user_id: string;
  last_message_at: string | null;
  /**
   * Unread count from the VIEWER's perspective (server determines which
   * side this is based on the caller's identity).
   */
  unread_count: number;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  sender_user_id: string;
  sender_role: "Teacher" | "Parent" | string;
  body: string;
  redacted: boolean;
  redacted_at: string | null;
  read_at: string | null;
  created_at: string;
}

// ─── Reports ───

export interface DashboardData {
  total_students: number;
  active_students: number;
  total_enrollments: number;
  total_classes?: number;
  attendance_today_rate: number;
  attendance_rate?: number;
  outstanding_fees: number;
  total_outstanding?: number;
  total_revenue?: number;
  collected_this_term: number;
  announcements_this_month: number;
  announcements_count?: number;
}

export interface AttendanceTrendPoint {
  date: string;
  present: number;
  absent: number;
  late: number;
  total: number;
  rate: number;
}

export interface FinancialSummaryData {
  academic_year_id: string;
  total_invoiced: number;
  total_paid: number;
  total_outstanding: number;
}

// ─── Dropout Intelligence ───

export interface DropoutSignal {
  code: string;
  label: string;
  points: number;
  evidence: string;
}

export interface DropoutSummary {
  total_students: number;
  at_risk_count: number;
  band_breakdown: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
    CRITICAL: number;
  };
  top_signals: { code: string; count: number }[];
}

export interface DropoutStudentRow {
  student_id: string;
  student_code: string;
  first_name: string;
  last_name: string;
  risk_score: number;
  risk_band: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  signal_count: number;
  top_signal: string | null;
}

export interface DropoutStudentDetail {
  student_id: string;
  risk_score: number;
  risk_band: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  signals: DropoutSignal[];
  computed_at: string;
  lookback_days: number;
}

// ─── Users ───

export interface User {
  id: string;
  email: string;
  full_name: string;
  school_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  roles: { id: string; name: string }[];
  permissions: string[];
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  school_id?: string;
  created_at: string;
  permissions: { id: string; name: string; resource: string; action: string }[];
}

export interface Permission {
  id: string;
  name: string;
  description?: string;
  resource: string;
  action: string;
}

// ─── Assessments ───

export interface Assessment {
  id: string;
  school_id: string;
  academic_year_id: string;
  term_id: string;
  class_id: string;
  subject_id: string;
  name: string;
  assessment_type: "QUIZ" | "TEST" | "EXAM" | "ASSIGNMENT";
  date: string;
  max_marks: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface MarkEntry {
  id: string;
  assessment_id: string;
  student_id: string;
  marks: number | null;
  is_absent: boolean;
  remarks: string | null;
  graded_by: string;
  graded_at: string;
}

export interface AssessmentDetail extends Assessment {
  marks: MarkEntry[];
}

export interface BulkMarksResult {
  accepted: number;
  updated: number;
  errors: string[];
}

export interface StudentSubjectMarks {
  subject_id: string;
  average_pct: number | null;
  graded_count: number;
  assessments: {
    assessment: Assessment;
    mark: MarkEntry;
  }[];
}

export interface SubjectPerformance {
  subject_id: string;
  avg_pct: number | null;
  pass_rate: number | null;
  assessment_count: number;
  student_count: number;
}

export interface ClassPerformance {
  subjects: SubjectPerformance[];
}

// Phase 11c / T-015 — cross-assessment gradebook payload.
export interface GradebookCell {
  marks: number | null;
  is_absent: boolean;
  remarks: string | null;
}
export interface GradebookRow {
  student_id: string;
  marks: Record<string, GradebookCell>; // keyed by assessment_id
  graded_count: number;
  average_pct: number | null;
}
export interface GradebookAssessment {
  id: string;
  name: string;
  assessment_type: string;
  date: string;
  max_marks: number;
  subject_id: string;
}
export interface ClassGradebook {
  class_id: string;
  term_id: string | null;
  subject_id: string | null;
  assessments: GradebookAssessment[];
  rows: GradebookRow[];
}

export interface CreateAssessmentRequest {
  academic_year_id: string;
  term_id: string;
  class_id: string;
  subject_id: string;
  name: string;
  assessment_type: "QUIZ" | "TEST" | "EXAM" | "ASSIGNMENT";
  date: string;
  max_marks: number;
}

export interface BulkMarksRequest {
  marks: {
    student_id: string;
    marks?: number | null;
    is_absent: boolean;
    remarks?: string;
  }[];
}

// ─── Diagnostics ───

export type IntegrationCategory =
  | "core"
  | "payments"
  | "messaging"
  | "reporting"
  | "assessment";

export type IntegrationStatus =
  | "ok"
  | "degraded"
  | "down"
  | "not_configured"
  | "unknown";

export interface IntegrationCheck {
  id: string;
  label: string;
  status: IntegrationStatus;
  detail?: string;
  latency_ms?: number;
  http_status?: number;
  error?: string;
  [key: string]: unknown;
}

export interface IntegrationSummary {
  id: string;
  label: string;
  category: IntegrationCategory | string;
  description: string;
  status: IntegrationStatus;
  latency_ms?: number;
  http_status?: number;
  message?: string;
  deep_probe?: boolean;
}

export interface IntegrationProbeResult extends IntegrationSummary {
  deep_probe: boolean;
  checks?: IntegrationCheck[];
}

// ─── Paynow / Payments ───

export type PaynowMethod = "ECOCASH" | "ONEMONEY" | "MUKURU" | "TELECASH" | "BANK";

export type PaynowTxnStatus =
  | "INITIATED"
  | "SENT"
  | "PENDING"
  | "PAID"
  | "CANCELLED"
  | "FAILED"
  | "EXPIRED";

export interface PaynowInitiateResult {
  transaction_ref: string;
  status: "PENDING";
  poll_url: string;
  instructions: string;
  demo_mode: boolean;
}

export interface PaymentTransactionStatus {
  transaction_ref: string;
  status: PaynowTxnStatus;
  paynow_reference?: string | null;
  amount: number;
  currency: string;
  method: PaynowMethod;
  instructions?: string | null;
  last_error?: string | null;
  initiated_at?: string | null;
  confirmed_at?: string | null;
}

// ─── Notification outbox ───

export interface OutboxStats {
  totals: Record<string, number>;          // { PENDING: 3, DELIVERED: 4210, FAILED: 2, SENT: 0 }
  by_channel: Record<string, Record<string, number>>;
  // e.g. { SMS: { PENDING: 1, FAILED: 1 }, EMAIL: { DELIVERED: 4210 } }
}
