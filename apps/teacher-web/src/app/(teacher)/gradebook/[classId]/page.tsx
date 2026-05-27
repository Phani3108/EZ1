/**
 * Class Gradebook — Phase 11c / T-015.
 *
 * Matrix view: students × assessments. The grid is sparse on the
 * server (rows only for students who have at least one mark), so we
 * merge with the roster to render an empty cell where a student
 * hasn't been graded yet. Average column on the right.
 */

"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { ArrowLeft } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { useCachedApiQuery } from "@/hooks/use-cached-api-query";
import { teacher, student, assessment } from "@/lib/api";
import type {
  TeacherClass,
  Enrollment,
  Student as StudentType,
  Term,
  ClassGradebook,
} from "@eduzim/api-client";

export default function ClassGradebookPage() {
  const params = useParams();
  const classId = params.classId as string;
  const t = useTranslations("gradebook");

  const [termId, setTermId] = useState<string>("");

  // Class info (for header) + terms (for the picker)
  const { data: classes } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    [],
  );
  const classInfo = useMemo(
    () => classes?.find((c) => c.id === classId) ?? null,
    [classes, classId],
  );

  // Roster — same hook used by the attendance tab, cached so offline
  // users still see student names.
  const { data: enrollments } = useCachedApiQuery<Enrollment[]>(
    () => student.getEnrollmentsByClass(classId),
    { cacheKey: `roster:enrollments:${classId}` },
    [classId],
  );
  const { data: students } = useCachedApiQuery<StudentType[]>(
    () => student.list(),
    { cacheKey: "roster:students:list" },
    [],
  );

  const studentLookup = useMemo(() => {
    const m = new Map<string, StudentType>();
    students?.forEach((s) => m.set(s.id, s));
    return m;
  }, [students]);

  // Gradebook itself
  const { data: gradebook, isLoading } = useApiQuery<ClassGradebook>(
    () =>
      assessment.classGradebook(
        classId,
        termId ? { term_id: termId } : {},
      ),
    [classId, termId],
  );

  const rowById = useMemo(() => {
    const m = new Map(gradebook?.rows.map((r) => [r.student_id, r]) ?? []);
    return m;
  }, [gradebook]);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/gradebook"
          className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {classInfo ? `${classInfo.name} · ${classInfo.section}` : t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("description")}</p>
        </div>
      </div>

      {/* Term filter (free text for now — a full term picker comes with T-010 calendar) */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium" htmlFor="term-filter">
          {t("termFilterLabel")}
        </label>
        <input
          id="term-filter"
          value={termId}
          onChange={(e) => setTermId(e.target.value)}
          placeholder={t("termFilterPlaceholder")}
          className="rounded-md border px-3 py-2 text-sm bg-background w-72"
          data-testid="gradebook-term-filter"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              {t("loading")}
            </div>
          ) : (gradebook?.assessments.length ?? 0) === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {t("noAssessments")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="gradebook-table">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground sticky left-0 bg-muted/50 z-10">
                      {t("studentColumn")}
                    </th>
                    {gradebook?.assessments.map((a) => (
                      <th
                        key={a.id}
                        className="px-3 py-3 text-center font-medium text-muted-foreground whitespace-nowrap"
                      >
                        <div className="text-xs">{a.name}</div>
                        <div className="text-xs text-muted-foreground/70">
                          /{a.max_marks}
                        </div>
                      </th>
                    ))}
                    <th className="px-3 py-3 text-right font-medium text-muted-foreground">
                      {t("averageColumn")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {enrollments?.map((e) => {
                    const s = studentLookup.get(e.student_id);
                    const row = rowById.get(e.student_id);
                    return (
                      <tr
                        key={e.id}
                        className="border-b last:border-0"
                        data-testid={`gradebook-row-${e.student_id}`}
                      >
                        <td className="px-4 py-2 font-medium sticky left-0 bg-background">
                          {s ? `${s.first_name} ${s.last_name}` : e.student_id}
                        </td>
                        {gradebook?.assessments.map((a) => {
                          const cell = row?.marks[a.id];
                          if (!cell) {
                            return (
                              <td
                                key={a.id}
                                className="px-3 py-2 text-center text-muted-foreground"
                              >
                                —
                              </td>
                            );
                          }
                          if (cell.is_absent) {
                            return (
                              <td
                                key={a.id}
                                className="px-3 py-2 text-center text-yellow-700"
                              >
                                {t("absentShort")}
                              </td>
                            );
                          }
                          return (
                            <td
                              key={a.id}
                              className="px-3 py-2 text-center"
                            >
                              {cell.marks ?? "—"}
                            </td>
                          );
                        })}
                        <td className="px-3 py-2 text-right font-medium">
                          {row?.average_pct != null
                            ? `${row.average_pct}%`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
