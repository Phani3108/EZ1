/**
 * Assessments Tab — 10B-3C + 10B-4A offline queue.
 * List assessments, create new via Sheet, click row → marks grid.
 * Percentage auto-calculated: marks / max_marks × 100.
 */

"use client";

import React, { useState, useMemo, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Label,
  Select,
  Badge,
  Sheet,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
} from "@eduzim/ui";
import {
  GraduationCap,
  Plus,
  FileText,
  Save,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";
import { assessment, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useSync } from "@/lib/sync-provider";
import type {
  Assessment,
  AssessmentDetail,
  Term,
  Subject,
  Enrollment,
  Student,
  CreateAssessmentRequest,
} from "@eduzim/api-client";

// ─── Types ───

interface AssessmentsTabProps {
  classId: string;
  rosterStudents: { enrollment: Enrollment; student: Student }[];
  /** academic_year_id from this class's TeacherClass */
  academicYearId?: string;
}

type AssessmentType = "QUIZ" | "TEST" | "EXAM" | "ASSIGNMENT";

// ─── Main Component ───

export function AssessmentsTab({
  classId,
  rosterStudents,
  academicYearId,
}: AssessmentsTabProps) {
  const t = useTranslations("assessments");
  const { user } = useAuth();

  // State
  const [selectedTermId, setSelectedTermId] = useState<string>("");
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [createOpen, setCreateOpen] = useState(false);
  const [activeAssessmentId, setActiveAssessmentId] = useState<string | null>(
    null
  );

  // ─── Data Fetching ───

  const { data: terms } = useApiQuery<Term[]>(
    () => school.listTerms(academicYearId ? { academic_year_id: academicYearId } : undefined),
    [academicYearId]
  );

  const { data: subjects } = useApiQuery<Subject[]>(
    () => school.listSubjects(),
    []
  );

  // auto-select current term
  useEffect(() => {
    if (terms && terms.length > 0 && !selectedTermId) {
      const current = terms.find((t) => t.is_current);
      setSelectedTermId(current?.id ?? terms[0].id);
    }
  }, [terms, selectedTermId]);

  // Fetch assessments for class+term
  const {
    data: assessments,
    isLoading: assessmentsLoading,
    refetch: refetchAssessments,
  } = useApiQuery<Assessment[]>(
    () =>
      selectedTermId
        ? assessment.list({
          class_id: classId,
          term_id: selectedTermId,
          ...(selectedSubjectId ? { subject_id: selectedSubjectId } : {}),
        })
        : Promise.resolve({ data: [] }),
    [classId, selectedTermId, selectedSubjectId]
  );

  // Subject lookup
  const subjectMap = useMemo(() => {
    const m = new Map<string, Subject>();
    subjects?.forEach((s) => m.set(s.id, s));
    return m;
  }, [subjects]);

  // Term lookup
  const termMap = useMemo(() => {
    const m = new Map<string, Term>();
    terms?.forEach((t) => m.set(t.id, t));
    return m;
  }, [terms]);

  // Type label helper
  const typeLabel = useCallback(
    (type: AssessmentType) => {
      const map: Record<AssessmentType, string> = {
        QUIZ: t("typeQuiz"),
        TEST: t("typeTest"),
        EXAM: t("typeExam"),
        ASSIGNMENT: t("typeAssignment"),
      };
      return map[type] ?? type;
    },
    [t]
  );

  // Variant for badges
  const typeVariant = (type: AssessmentType) => {
    const map: Record<AssessmentType, "default" | "secondary" | "destructive" | "outline"> = {
      EXAM: "default",
      TEST: "secondary",
      QUIZ: "outline",
      ASSIGNMENT: "outline",
    };
    return map[type] ?? "outline";
  };

  // If marks grid is active, show it instead
  if (activeAssessmentId) {
    return (
      <MarksGrid
        assessmentId={activeAssessmentId}
        rosterStudents={rosterStudents}
        onBack={() => {
          setActiveAssessmentId(null);
          refetchAssessments();
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* ─── Filters ─── */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs">{t("term")}</Label>
          <Select
            value={selectedTermId}
            onChange={(e) => setSelectedTermId(e.target.value)}
            options={terms?.map((term) => ({ value: term.id, label: term.name })) ?? []}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">{t("filterSubject")}</Label>
          <Select
            value={selectedSubjectId}
            onChange={(e) => setSelectedSubjectId(e.target.value)}
            options={[
              { value: "", label: t("allSubjects") },
              ...(subjects?.map((s) => ({ value: s.id, label: s.name })) ?? [])
            ]}
          />
        </div>
        <Button
          className="flex items-center gap-1.5"
          onClick={() => setCreateOpen(true)}
        >
          <Plus className="h-4 w-4" />
          {t("createAssessment")}
        </Button>
      </div>

      {/* ─── Assessment List ─── */}
      {assessmentsLoading ? (
        <Card className="animate-pulse">
          <CardContent className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded" />
            ))}
          </CardContent>
        </Card>
      ) : assessments && assessments.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      {t("date")}
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      {t("name")}
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      {t("type")}
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      {t("subject")}
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                      {t("maxMarks")}
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground" />
                  </tr>
                </thead>
                <tbody>
                  {assessments.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b last:border-0 hover:bg-muted/30 cursor-pointer"
                      onClick={() => setActiveAssessmentId(a.id)}
                    >
                      <td className="px-4 py-3 text-muted-foreground">
                        {new Date(a.date).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 font-medium">{a.name}</td>
                      <td className="px-4 py-3">
                        <Badge variant={typeVariant(a.assessment_type)}>
                          {typeLabel(a.assessment_type)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {subjectMap.get(a.subject_id)?.name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {a.max_marks}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveAssessmentId(a.id);
                          }}
                        >
                          {t("enterMarks")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-6 text-center">
            <GraduationCap className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              {t("noAssessments")}
            </p>
          </CardContent>
        </Card>
      )}

      {/* ─── Create Assessment Sheet ─── */}
      <CreateAssessmentSheet
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        classId={classId}
        academicYearId={academicYearId}
        terms={terms ?? []}
        subjects={subjects ?? []}
        selectedTermId={selectedTermId}
        onCreated={() => {
          setCreateOpen(false);
          refetchAssessments();
        }}
      />
    </div>
  );
}

// ─── Create Assessment Sheet ───

interface CreateSheetProps {
  open: boolean;
  onClose: () => void;
  classId: string;
  academicYearId?: string;
  terms: Term[];
  subjects: Subject[];
  selectedTermId: string;
  onCreated: () => void;
}

function CreateAssessmentSheet({
  open,
  onClose,
  classId,
  academicYearId,
  terms,
  subjects,
  selectedTermId,
  onCreated,
}: CreateSheetProps) {
  const t = useTranslations("assessments");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [assessmentType, setAssessmentType] = useState<AssessmentType>("TEST");
  const [termId, setTermId] = useState(selectedTermId);
  const [subjectId, setSubjectId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [maxMarks, setMaxMarks] = useState("100");

  // Reset when opening
  useEffect(() => {
    if (open) {
      setName("");
      setAssessmentType("TEST");
      setTermId(selectedTermId);
      setSubjectId(subjects[0]?.id ?? "");
      setDate(new Date().toISOString().slice(0, 10));
      setMaxMarks("100");
      setError(null);
    }
  }, [open, selectedTermId, subjects]);

  const validate = (): string | null => {
    if (!name.trim()) return t("nameRequired");
    if (Number(maxMarks) < 1 || isNaN(Number(maxMarks)))
      return t("maxMarksMin");
    return null;
  };

  const handleSubmit = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const payload: CreateAssessmentRequest = {
        academic_year_id: academicYearId ?? "",
        term_id: termId,
        class_id: classId,
        subject_id: subjectId,
        name: name.trim(),
        assessment_type: assessmentType,
        date,
        max_marks: Number(maxMarks),
      };
      await assessment.create(payload);
      onCreated();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create assessment"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Sheet open={open} onClose={onClose}>
      <SheetHeader>
        <SheetTitle>{t("createAssessment")}</SheetTitle>
        <SheetDescription>{t("createDescription")}</SheetDescription>
      </SheetHeader>
      <SheetBody className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-1.5">
          <Label>{t("name")}</Label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("namePlaceholder")}
            className="w-full rounded-md border px-3 py-2 text-sm bg-background"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>{t("type")}</Label>
            <Select
              value={assessmentType}
              onChange={(e) =>
                setAssessmentType(e.target.value as AssessmentType)
              }
              options={[
                { value: "QUIZ", label: t("typeQuiz") },
                { value: "TEST", label: t("typeTest") },
                { value: "EXAM", label: t("typeExam") },
                { value: "ASSIGNMENT", label: t("typeAssignment") },
              ]}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("subject")}</Label>
            <Select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              options={subjects.map((s) => ({ value: s.id, label: s.name }))}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>{t("term")}</Label>
            <Select
              value={termId}
              onChange={(e) => setTermId(e.target.value)}
              options={terms.map((term) => ({ value: term.id, label: term.name }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("date")}</Label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label>{t("maxMarks")}</Label>
          <input
            type="number"
            min="1"
            value={maxMarks}
            onChange={(e) => setMaxMarks(e.target.value)}
            placeholder={t("maxMarksPlaceholder")}
            className="w-full rounded-md border px-3 py-2 text-sm bg-background"
          />
        </div>
      </SheetBody>
      <SheetFooter>
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? t("creating") : t("createAssessment")}
        </Button>
      </SheetFooter>
    </Sheet>
  );
}

// ─── Marks Grid ───

interface MarksGridProps {
  assessmentId: string;
  rosterStudents: { enrollment: Enrollment; student: Student }[];
  onBack: () => void;
}

function MarksGrid({ assessmentId, rosterStudents, onBack }: MarksGridProps) {
  const t = useTranslations("assessments");

  // Fetch assessment detail (includes existing marks)
  const {
    data: detail,
    isLoading,
    refetch,
  } = useApiQuery<AssessmentDetail>(
    () => assessment.get(assessmentId),
    [assessmentId]
  );

  // Local marks state: studentId → { marks, is_absent, remarks }
  const [marksState, setMarksState] = useState<
    Record<string, { marks: string; isAbsent: boolean; remarks: string }>
  >({});
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Merge existing marks when detail loads
  useEffect(() => {
    if (!detail) return;
    const initial: Record<
      string,
      { marks: string; isAbsent: boolean; remarks: string }
    > = {};

    // Default all roster students to empty
    rosterStudents.forEach(({ student }) => {
      initial[student.id] = { marks: "", isAbsent: false, remarks: "" };
    });

    // Overlay existing marks
    detail.marks?.forEach((m) => {
      initial[m.student_id] = {
        marks: m.marks != null ? String(m.marks) : "",
        isAbsent: m.is_absent,
        remarks: m.remarks ?? "",
      };
    });

    setMarksState(initial);
    setIsDirty(false);
    setSaveResult(null);
  }, [detail, rosterStudents]);

  const setStudentMark = useCallback(
    (
      studentId: string,
      field: "marks" | "isAbsent" | "remarks",
      value: string | boolean
    ) => {
      setMarksState((prev) => ({
        ...prev,
        [studentId]: { ...prev[studentId], [field]: value },
      }));
      setIsDirty(true);
      setSaveResult(null);
    },
    []
  );

  const maxMarks = detail?.max_marks ?? 100;

  // Calculate percentage
  const pct = (marks: string): string => {
    const n = Number(marks);
    if (isNaN(n) || marks === "") return "—";
    return ((n / maxMarks) * 100).toFixed(1) + "%";
  };

  // Calculate class average
  const classAverage = useMemo(() => {
    const entries = Object.values(marksState).filter(
      (m) => !m.isAbsent && m.marks !== "" && !isNaN(Number(m.marks))
    );
    if (entries.length === 0) return null;
    const total = entries.reduce((sum, m) => sum + Number(m.marks), 0);
    return ((total / entries.length / maxMarks) * 100).toFixed(1);
  }, [marksState, maxMarks]);

  const { enqueueOffline, online } = useSync();

  // Save marks via offline queue
  const handleSave = async () => {
    setIsSaving(true);
    setSaveResult(null);

    const marks = rosterStudents.map(({ student }) => {
      const m = marksState[student.id];
      return {
        student_id: student.id,
        marks: m?.isAbsent ? null : m?.marks !== "" ? Number(m?.marks) : null,
        is_absent: m?.isAbsent ?? false,
        remarks: m?.remarks || undefined,
      };
    });

    try {
      await enqueueOffline({
        type: "MARKS",
        schoolId: "",
        userId: "",
        deviceId: `teacher-web:marks`,
        payload: { assessmentId, marks },
        syncBatchId: `marks-${assessmentId}-${Date.now()}`,
      });
      setSaveResult({
        type: "success",
        message: online ? t("marksSaved") : "Queued for sync",
      });
      setIsDirty(false);
      if (online) {
        setTimeout(() => refetch(), 1500);
      }
    } catch {
      setSaveResult({ type: "error", message: t("marksSaveFailed") });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading || !detail) {
    return (
      <Card className="animate-pulse">
        <CardContent className="p-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted rounded" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <h3 className="text-lg font-semibold">{detail.name}</h3>
          <p className="text-xs text-muted-foreground">
            {t("maxMarks")}: {detail.max_marks}
            {classAverage != null && (
              <>
                {" "}
                · {t("average")}: {classAverage}%
              </>
            )}
          </p>
        </div>
      </div>

      {/* Grid */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    #
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    Student
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-muted-foreground w-24">
                    {t("marks")} <span className="text-xs">/ {detail.max_marks}</span>
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-muted-foreground w-20">
                    {t("percentage")}
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-muted-foreground w-20">
                    {t("absent")}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t("remarks")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rosterStudents.map(({ student }, idx) => {
                  const m = marksState[student.id] ?? {
                    marks: "",
                    isAbsent: false,
                    remarks: "",
                  };
                  return (
                    <tr
                      key={student.id}
                      className="border-b last:border-0 hover:bg-muted/30"
                    >
                      <td className="px-4 py-2 text-muted-foreground">
                        {idx + 1}
                      </td>
                      <td className="px-4 py-2 font-medium">
                        {student.first_name} {student.last_name}
                        {student.admission_number && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({student.admission_number})
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <input
                          type="number"
                          min="0"
                          max={detail.max_marks}
                          value={m.marks}
                          disabled={m.isAbsent}
                          onChange={(e) =>
                            setStudentMark(student.id, "marks", e.target.value)
                          }
                          className="w-20 rounded-md border px-2 py-1 text-center text-sm bg-background disabled:opacity-50 disabled:bg-muted tabular-nums"
                        />
                      </td>
                      <td className="px-4 py-2 text-center tabular-nums text-muted-foreground">
                        {m.isAbsent ? "—" : pct(m.marks)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={m.isAbsent}
                          onChange={(e) =>
                            setStudentMark(
                              student.id,
                              "isAbsent",
                              e.target.checked
                            )
                          }
                          className="h-4 w-4 rounded border-gray-300"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={m.remarks}
                          onChange={(e) =>
                            setStudentMark(
                              student.id,
                              "remarks",
                              e.target.value
                            )
                          }
                          placeholder="..."
                          className="w-full rounded-md border px-2 py-1 text-sm bg-background"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Save bar */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleSave}
          disabled={isSaving || !isDirty || rosterStudents.length === 0}
          className="flex items-center gap-2"
        >
          <Save className="h-4 w-4" />
          {isSaving ? t("savingMarks") : t("saveMarks")}
        </Button>
        {saveResult?.type === "success" && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <CheckCircle className="h-4 w-4" />
            {saveResult.message}
          </span>
        )}
        {saveResult?.type === "error" && (
          <span className="flex items-center gap-1 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" />
            {saveResult.message}
          </span>
        )}
      </div>
    </div>
  );
}
