/**
 * Phase 15b — Onboarding + Invitation API helpers.
 *
 * Thin typed wrappers around the gateway endpoints introduced in
 * Phase 15a. Used by the (admin)/setup/** wizard.
 */
import { api } from "./api";

export type StepStatus = "green" | "amber" | "red";

export interface ChecklistEntry {
  step: string;
  label: string;
  status: StepStatus;
  evidence: Record<string, unknown>;
}

export interface OnboardingStatus {
  school_id: string;
  school_is_live: boolean;
  went_live_at: string | null;
  checklist: ChecklistEntry[];
  go_live_eligible: boolean;
  go_live_blockers: string[];
}

export interface InviteRow {
  id: string;
  school_id: string;
  role: string;
  full_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  target_resource_id: string | null;
  target_resource_type: string | null;
  extra: string | null;
  request_status: "pending" | "dispatched" | "failed" | "superseded";
  identity_invitation_id: string | null;
  last_error: string | null;
  requested_at: string | null;
  dispatched_at: string | null;
}

export interface InviteOutboxRow {
  id: string;
  invitation_id: string;
  channel: "sms" | "whatsapp" | "email" | "manual";
  provider_name: string | null;
  recipient_email: string | null;
  recipient_phone: string | null;
  subject: string | null;
  body: string | null;
  manual_code: string | null;
  invite_url: string | null;
  status: "queued" | "sent" | "delivered" | "manual_pending" | "failed";
  retry_count: number;
  last_attempt_at: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface StudentDraftRow {
  id: string;
  first_name: string;
  last_name: string;
  student_code: string | null;
  parent_phone: string | null;
  parent_email: string | null;
  review_status: "pending" | "approved" | "rejected";
  submitted_at: string | null;
}

export interface TemplateInfo {
  entity: string;
  headers: string[];
  example_count: number;
  csv_url: string;
}

export const onboardingApi = {
  status: () => api.get<OnboardingStatus>("/api/v1/onboarding/status"),

  goLive: () => api.post<OnboardingStatus>("/api/v1/onboarding/go-live"),

  listInviteRequests: (params?: { role?: string; status?: string }) =>
    api.get<InviteRow[]>(
      "/api/v1/bulk/invite-requests",
      params as Record<string, string> | undefined,
    ),

  listInviteOutbox: (params?: { status?: string }) =>
    api.get<InviteOutboxRow[]>(
      "/api/v1/comm/invite-outbox",
      params as Record<string, string> | undefined,
    ),

  listStudentDrafts: (status: "pending" | "approved" | "rejected" = "pending") =>
    api.get<StudentDraftRow[]>(
      "/api/v1/drafts/students",
      { status },
    ),

  approveStudentDraft: (id: string, body: {
    student_code?: string;
    class_id?: string;
    academic_year_id?: string;
  } = {}) =>
    api.post<{ draft: StudentDraftRow; student_id: string }>(
      `/api/v1/drafts/students/${id}/approve`,
      body,
    ),

  rejectStudentDraft: (id: string, reason: string) =>
    api.post<StudentDraftRow>(
      `/api/v1/drafts/students/${id}/reject`,
      { reason },
    ),

  listTemplates: () =>
    api.get<TemplateInfo[]>("/api/v1/templates"),
};

export const invitationsApi = {
  /** Create an invitation in identity. */
  create: (body: {
    school_id: string;
    role: string;
    full_name: string;
    contact_email?: string;
    contact_phone?: string;
    target_resource_id?: string;
    target_resource_type?: string;
  }) => api.post<{
    id: string;
    school_id: string;
    role: string;
    raw_token?: string;
    manual_code: string;
    contact_email: string | null;
    contact_phone: string | null;
  }>("/api/v1/invitations", body),

  /** Manually trigger dispatch (admin-web does this after the create
   * call succeeds, or when retrying a failed delivery). */
  dispatch: (body: {
    invitation_id: string;
    school_name: string;
    role: string;
    full_name: string;
    contact_email?: string;
    contact_phone?: string;
    manual_code: string;
    invite_url: string;
  }) => api.post<{
    invite_outbox_id: string;
    channel: string;
    provider_name: string | null;
    status: string;
    body_excerpt: string;
  }>("/api/v1/comm/invitations/dispatch", body),

  resend: (token: string) =>
    api.post<{ raw_token?: string; manual_code: string }>(
      `/api/v1/invitations/${token}/resend`,
    ),
};
