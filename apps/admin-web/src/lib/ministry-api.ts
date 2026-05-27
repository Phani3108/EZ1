/**
 * Ministry (MoPSE) API helpers — admin-web `(ministry)` route group.
 *
 * DEC-013 + ADR 020: Ministry is read-only. Every helper here is a GET.
 * The helpers thinly wrap `@eduzim/api-client` so the page components
 * can render with a stable typed contract.
 */
import { api } from "./api";

export type Scope = "national" | "province" | "district";

export interface MinistrySchool {
  id: string;
  name: string;
  province_code: string | null;
  district_code: string | null;
  school_type: string | null;
  is_active: boolean;
}

export interface EnrolmentNational {
  schools: number;
  students: number;
}

export interface EnrolmentProvinceRow {
  province_code: string | null;
  province_name: string | null;
  schools: number;
  students: number;
}

export interface EnrolmentDistrictRow {
  district_code: string | null;
  district_name: string | null;
  province_code: string | null;
  schools: number;
  students: number;
}

export interface AttendanceNational {
  days: number;
  records: number;
  present: number;
  rate: number | null;
}

export interface AttendanceScopeRow {
  province_code?: string | null;
  district_code?: string | null;
  records: number;
  present: number;
  rate: number | null;
}

export interface GeographyRow {
  provinces: Array<{
    code: string;
    name: string;
    region: string;
    capital: string;
    country: string;
  }>;
  districts: Array<{
    code: string;
    name: string;
    province_code: string;
  }>;
}

export interface DropoutScopeRow {
  province_code?: string | null;
  district_code?: string | null;
  active: number;
  dropouts: number;
  dropout_rate: number | null;
}

export interface DropoutNational {
  active: number;
  dropouts: number;
  dropout_rate: number | null;
}

export interface PassRateRow {
  province_code?: string | null;
  district_code?: string | null;
  subject_id: string;
  subject_name: string;
  graded: number;
  passes: number;
  pass_rate: number | null;
}

export interface PtrRow {
  province_code?: string | null;
  district_code?: string | null;
  active_students: number;
  teachers: number;
  ptr: number | null;
  devices_per_school: number | null;
  electricity_coverage: number | null;
}

export interface FeesRow {
  school_id: string;
  invoices: number;
  total_invoiced: number;
  total_paid: number;
  outstanding: number;
  collection_rate: number | null;
}

export interface DefaultersRow {
  school_id: string;
  overdue_invoices: number;
  partial_invoices: number;
  overdue_amount: number;
  partial_amount: number;
}

export interface ComplianceRow {
  school_id: string;
  template_id: string;
  template_code: string;
  template_title: string;
  draft: number;
  submitted: number;
  accepted: number;
  rejected: number;
  total: number;
}

export interface ComparativeRow {
  school_id: string | null;
  label: string;
  province_code: string | null;
  district_code: string | null;
  active_students: number;
  dropouts: number;
  teachers: number;
  ptr: number | null;
}

export interface PolicyImpactWindow {
  value: number | null;
  n: number;
  window: [string, string];
}

export interface PolicyImpactResult {
  metric: string;
  before: PolicyImpactWindow;
  after: PolicyImpactWindow;
  delta: number | null;
}

export interface DonorsNational {
  sponsorships: number;
  committed: number;
  received: number;
  fulfilment_rate: number | null;
}

export interface DonorsScopeRow {
  province_code?: string | null;
  district_code?: string | null;
  sponsorships: number;
  committed: number;
  received: number;
  fulfilment_rate: number | null;
}

export interface UnescoExport {
  country_code: string;
  reporting_year: number;
  schools: { total: number; by_type: Record<string, number> };
  enrolment: {
    total_active: number;
    by_province: Array<{ province_code: string | null; active: number }>;
  };
  teachers: { total: number };
  attendance: { national_rate_trailing_30d: number | null };
  dropouts: { national_count: number; national_rate: number | null };
  generated_at: string;
}

export const ministryApi = {
  geography: () =>
    api.get<GeographyRow>("/api/v1/ministry/geography"),

  schools: (params?: { province_code?: string; district_code?: string }) =>
    api.get<MinistrySchool[]>("/api/v1/ministry/schools", params as Record<string, string> | undefined),

  enrolmentNational: () =>
    api.get<EnrolmentNational>("/api/v1/ministry/enrolment", { scope: "national" }),

  enrolmentProvince: () =>
    api.get<EnrolmentProvinceRow[]>("/api/v1/ministry/enrolment", { scope: "province" }),

  enrolmentDistrict: () =>
    api.get<EnrolmentDistrictRow[]>("/api/v1/ministry/enrolment", { scope: "district" }),

  attendance: (scope: Scope, days = 30) =>
    api.get<AttendanceNational | AttendanceScopeRow[]>("/api/v1/ministry/attendance", {
      scope,
      days: String(days),
    }),

  dropouts: (scope: Scope) =>
    api.get<DropoutNational | DropoutScopeRow[]>("/api/v1/ministry/dropouts", { scope }),

  passRate: (scope: Scope) =>
    api.get<PassRateRow[]>("/api/v1/ministry/pass-rate", { scope }),

  ptr: (scope: Scope) =>
    api.get<PtrRow | PtrRow[]>("/api/v1/ministry/ptr", { scope }),

  compliance: (period_label?: string) =>
    api.get<ComplianceRow[]>(
      "/api/v1/ministry/compliance",
      period_label ? { period_label } : undefined,
    ),

  fees: () =>
    api.get<FeesRow[]>("/api/v1/ministry/fees"),

  defaulters: () =>
    api.get<DefaultersRow[]>("/api/v1/ministry/fees/defaulters"),

  comparative: (params?: {
    province_code?: string;
    district_code?: string;
    anonymize?: boolean;
  }) =>
    api.get<ComparativeRow[]>("/api/v1/ministry/comparative", {
      ...(params?.province_code && { province_code: params.province_code }),
      ...(params?.district_code && { district_code: params.district_code }),
      ...(params?.anonymize && { anonymize: "true" }),
    }),

  policyImpact: (params: {
    metric: "attendance_rate" | "dropout_rate";
    before_start: string;
    before_end: string;
    after_start: string;
    after_end: string;
    province_code?: string;
    district_code?: string;
  }) =>
    api.get<PolicyImpactResult>("/api/v1/ministry/policy-impact", params as Record<string, string>),

  donors: (scope: Scope) =>
    api.get<DonorsNational | DonorsScopeRow[]>("/api/v1/ministry/donors", { scope }),

  unesco: (year: number) =>
    api.get<UnescoExport>("/api/v1/ministry/exports/unesco", { year: String(year) }),
};
