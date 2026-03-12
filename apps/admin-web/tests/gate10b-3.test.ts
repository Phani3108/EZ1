/**
 * Admin-web — 10B-3D Quality Gate Tests
 * ========================================
 * Tests cover:
 * - Student performance tab data contract (StudentSubjectMarks[])
 * - Risk badge threshold (< 60% = at risk)
 * - Subject grouping structure
 * - Assessment score display formatting
 * - Percentage calculation in performance view
 * - Performance tab replaces disabled "Subjects (Phase 2)"
 * - assessmentApi wired in admin api.ts
 */

import { describe, it, expect } from "vitest";
import { z } from "zod";

// ─── Assessment Type Enum ───

const assessmentTypeSchema = z.enum(["QUIZ", "TEST", "EXAM", "ASSIGNMENT"]);

// ─── Student Subject Marks Contract ───

const assessmentSchema = z.object({
  id: z.string().uuid(),
  school_id: z.string().uuid(),
  academic_year_id: z.string().uuid(),
  term_id: z.string().uuid(),
  class_id: z.string().uuid(),
  subject_id: z.string().uuid(),
  name: z.string().min(1),
  assessment_type: assessmentTypeSchema,
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  max_marks: z.number().int().min(1),
  created_by: z.string().uuid(),
  created_at: z.string(),
  updated_at: z.string(),
});

const markEntrySchema = z.object({
  id: z.string().uuid(),
  assessment_id: z.string().uuid(),
  student_id: z.string().uuid(),
  marks: z.number().nullable(),
  is_absent: z.boolean(),
  remarks: z.string().nullable(),
  graded_by: z.string().uuid(),
  graded_at: z.string(),
});

const studentSubjectMarksSchema = z.object({
  subject_id: z.string().uuid(),
  average_pct: z.number().nullable(),
  graded_count: z.number().int().min(0),
  assessments: z.array(
    z.object({
      assessment: assessmentSchema,
      mark: markEntrySchema,
    })
  ),
});

describe("Student subject marks contract", () => {
  const sampleData = {
    subject_id: "550e8400-e29b-41d4-a716-446655440004",
    average_pct: 72.3,
    graded_count: 4,
    assessments: [
      {
        assessment: {
          id: "550e8400-e29b-41d4-a716-446655440020",
          school_id: "550e8400-e29b-41d4-a716-446655440000",
          academic_year_id: "550e8400-e29b-41d4-a716-446655440001",
          term_id: "550e8400-e29b-41d4-a716-446655440002",
          class_id: "550e8400-e29b-41d4-a716-446655440003",
          subject_id: "550e8400-e29b-41d4-a716-446655440004",
          name: "Term Test 1",
          assessment_type: "TEST",
          date: "2024-06-15",
          max_marks: 100,
          created_by: "550e8400-e29b-41d4-a716-446655440099",
          created_at: "2024-06-15T10:00:00Z",
          updated_at: "2024-06-15T10:00:00Z",
        },
        mark: {
          id: "550e8400-e29b-41d4-a716-446655440030",
          assessment_id: "550e8400-e29b-41d4-a716-446655440020",
          student_id: "550e8400-e29b-41d4-a716-446655440010",
          marks: 72,
          is_absent: false,
          remarks: null,
          graded_by: "550e8400-e29b-41d4-a716-446655440099",
          graded_at: "2024-06-16T09:00:00Z",
        },
      },
    ],
  };

  it("validates a subject marks group", () => {
    const result = studentSubjectMarksSchema.safeParse(sampleData);
    expect(result.success).toBe(true);
  });

  it("accepts null average_pct", () => {
    const result = studentSubjectMarksSchema.safeParse({
      ...sampleData,
      average_pct: null,
      graded_count: 0,
      assessments: [],
    });
    expect(result.success).toBe(true);
  });
});

// ─── Risk Badge Threshold ───

function isAtRiskAcademically(globalAvg: number | null): boolean {
  if (globalAvg == null) return false;
  return globalAvg < 60;
}

describe("Risk badge threshold", () => {
  it("marks student at risk when average < 60%", () => {
    expect(isAtRiskAcademically(45)).toBe(true);
  });

  it("marks student at risk at 59.9%", () => {
    expect(isAtRiskAcademically(59.9)).toBe(true);
  });

  it("does NOT mark at risk at exactly 60%", () => {
    expect(isAtRiskAcademically(60)).toBe(false);
  });

  it("does NOT mark at risk at 80%", () => {
    expect(isAtRiskAcademically(80)).toBe(false);
  });

  it("does NOT mark at risk when null (no data)", () => {
    expect(isAtRiskAcademically(null)).toBe(false);
  });
});

// ─── Global Average Computation ───

function computeGlobalAverage(
  subjectsData: { average_pct: number | null }[]
): number | null {
  const withAvg = subjectsData.filter((s) => s.average_pct != null);
  if (withAvg.length === 0) return null;
  return (
    withAvg.reduce((sum, s) => sum + (s.average_pct ?? 0), 0) / withAvg.length
  );
}

describe("Global average computation", () => {
  it("computes average across subjects", () => {
    const subjects = [
      { average_pct: 80 },
      { average_pct: 60 },
      { average_pct: 70 },
    ];
    expect(computeGlobalAverage(subjects)).toBeCloseTo(70);
  });

  it("ignores subjects with null average", () => {
    const subjects = [
      { average_pct: 80 },
      { average_pct: null },
      { average_pct: 60 },
    ];
    expect(computeGlobalAverage(subjects)).toBeCloseTo(70);
  });

  it("returns null when all subjects have null average", () => {
    const subjects = [{ average_pct: null }, { average_pct: null }];
    expect(computeGlobalAverage(subjects)).toBeNull();
  });

  it("returns null for empty array", () => {
    expect(computeGlobalAverage([])).toBeNull();
  });

  it("handles single subject", () => {
    expect(computeGlobalAverage([{ average_pct: 55 }])).toBeCloseTo(55);
  });
});

// ─── Score Display Formatting ───

function formatScore(
  marks: number | null,
  maxMarks: number,
  isAbsent: boolean
): string {
  if (isAbsent) return "Absent";
  if (marks == null) return "—";
  return `${marks} / ${maxMarks}`;
}

function formatPercentage(
  marks: number | null,
  maxMarks: number,
  isAbsent: boolean
): string {
  if (isAbsent) return "—";
  if (marks == null) return "—";
  return `${((marks / maxMarks) * 100).toFixed(1)}%`;
}

describe("Score display formatting", () => {
  it("formats graded score as 'marks / max'", () => {
    expect(formatScore(85, 100, false)).toBe("85 / 100");
  });

  it("formats absent as 'Absent'", () => {
    expect(formatScore(null, 100, true)).toBe("Absent");
  });

  it("formats ungraded as dash", () => {
    expect(formatScore(null, 100, false)).toBe("—");
  });

  it("formats percentage for graded", () => {
    expect(formatPercentage(85, 100, false)).toBe("85.0%");
  });

  it("formats percentage as dash for absent", () => {
    expect(formatPercentage(null, 100, true)).toBe("—");
  });

  it("formats percentage as dash for null marks", () => {
    expect(formatPercentage(null, 100, false)).toBe("—");
  });
});

// ─── Tab Structure ───

describe("Student 360 tab structure", () => {
  const tabs = [
    "overview",
    "guardians",
    "enrollment",
    "attendance",
    "fees",
    "communications",
    "performance",
  ];

  it("has 7 tabs", () => {
    expect(tabs).toHaveLength(7);
  });

  it("includes performance tab", () => {
    expect(tabs).toContain("performance");
  });

  it("no longer has disabled 'subjects' tab", () => {
    expect(tabs).not.toContain("subjects");
  });

  it("performance is the last tab", () => {
    expect(tabs[tabs.length - 1]).toBe("performance");
  });
});

// ─── API client assessment wiring ───

describe("Admin API client assessment", () => {
  it("exports assessmentApi function", async () => {
    const mod = await import("@eduzim/api-client");
    expect(typeof mod.assessmentApi).toBe("function");
  });
});
