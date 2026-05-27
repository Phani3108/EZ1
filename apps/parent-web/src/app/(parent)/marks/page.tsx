/**
 * Student marks — Phase 12g / S-005.
 *
 * Calls the existing `/assessments/students/{id}/marks` endpoint
 * with the student's own id (resolved via /students/me). Shows
 * subject-grouped marks + average.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { GraduationCap } from "lucide-react";


interface MarkEntry {
  assessment: {
    id: string; name: string; assessment_type: string;
    date: string | null; max_marks: number;
  };
  mark: {
    marks: number | null; is_absent: boolean; remarks: string | null;
  };
}

interface SubjectMarks {
  subject_id: string;
  assessments: MarkEntry[];
  average_pct: number | null;
  graded_count: number;
}


async function fetchJson<T>(path: string): Promise<{ data: T }> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const { getAccessToken } = await import("@eduzim/auth");
  const tok = getAccessToken();
  const res = await fetch(`${baseUrl}${path}`, {
    headers: tok ? { Authorization: `Bearer ${tok}` } : undefined,
  });
  if (!res.ok) throw new Error(`fetch failed: ${res.status}`);
  return res.json();
}


export default function StudentMarksPage() {
  const t = useTranslations("student");
  const { user } = useAuth();
  const isStudent = (user?.roles ?? []).some(
    (r) => typeof r === "string" && r.toLowerCase() === "student",
  );
  const [subjects, setSubjects] = React.useState<SubjectMarks[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!isStudent) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const me = await fetchJson<{ id: string }>("/api/v1/students/me");
        const r = await fetchJson<SubjectMarks[]>(
          `/api/v1/assessments/students/${me.data.id}/marks`,
        );
        setSubjects(r.data);
      } catch {
        /* empty state */
      } finally {
        setLoading(false);
      }
    })();
  }, [isStudent]);

  if (!isStudent) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            {t("studentOnlyHint")}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
        <GraduationCap className="h-5 w-5" />
        {t("marks.title")}
      </h1>

      {loading ? (
        <p className="text-sm text-muted-foreground">{t("loading")}</p>
      ) : subjects.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            {t("marks.empty")}
          </CardContent>
        </Card>
      ) : (
        subjects.map((s) => (
          <Card key={s.subject_id}>
            <CardHeader>
              <CardTitle className="text-base flex items-center justify-between">
                <span>
                  {t("marks.subjectN", { id: s.subject_id.slice(0, 8) })}
                </span>
                <span className="text-sm text-muted-foreground">
                  {s.average_pct != null
                    ? `${s.average_pct}% · ${s.graded_count}`
                    : "—"}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y">
                {s.assessments.map((entry) => (
                  <li
                    key={entry.assessment.id}
                    className="py-2 flex items-center justify-between text-sm"
                  >
                    <span>{entry.assessment.name}</span>
                    <span className="text-muted-foreground">
                      {entry.mark.is_absent
                        ? t("marks.absent")
                        : `${entry.mark.marks ?? "—"} / ${entry.assessment.max_marks}`}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
