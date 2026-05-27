/**
 * Student schedule — Phase 12g / S-003.
 *
 * Pulls the school's period schedule (Phase 11d /periods) plus the
 * student's enrolled class info. Shown only to the Student role.
 * Parents who navigate here see an explanation card instead — the
 * canonical parent view lives on /home.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { Calendar, Clock } from "lucide-react";


interface SchoolPeriod {
  id: string;
  period_number: number;
  name: string;
  start_time: string | null;
  end_time: string | null;
}

interface StudentProfile {
  id: string;
  student_code: string;
  first_name: string;
  last_name: string;
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


export default function StudentSchedulePage() {
  const t = useTranslations("student");
  const { user } = useAuth();
  const isStudent = (user?.roles ?? []).some(
    (r) => typeof r === "string" && r.toLowerCase() === "student",
  );

  const [periods, setPeriods] = React.useState<SchoolPeriod[]>([]);
  const [me, setMe] = React.useState<StudentProfile | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!isStudent) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const [p, mm] = await Promise.all([
          fetchJson<SchoolPeriod[]>("/api/v1/periods"),
          fetchJson<StudentProfile>("/api/v1/students/me"),
        ]);
        setPeriods(p.data);
        setMe(mm.data);
      } catch {
        /* swallow — UI shows empty state */
      } finally {
        setLoading(false);
      }
    })();
  }, [isStudent]);

  if (!isStudent) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">
              {t("studentOnlyHint")}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          {t("schedule.title")}
        </h1>
        {me && (
          <p className="text-sm text-muted-foreground mt-1">
            {me.first_name} {me.last_name} · {me.student_code}
          </p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="h-4 w-4" /> {t("schedule.periodsTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">{t("loading")}</p>
          ) : periods.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("schedule.empty")}
            </p>
          ) : (
            <ul className="divide-y">
              {periods.map((p) => (
                <li key={p.id} className="py-2 flex items-center justify-between">
                  <span className="font-medium">
                    {p.period_number}. {p.name}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {p.start_time} — {p.end_time}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
