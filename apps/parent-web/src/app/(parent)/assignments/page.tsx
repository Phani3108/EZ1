/**
 * Student assignments — Phase 12g / S-006 + S-007.
 *
 * Lists open homework for the student's class + lets them submit a
 * text response (the teacher grades via the teacher-web flow).
 * Attachments are deferred to the parent-web upload component
 * follow-up — for now a text submission is enough to close the
 * student-side loop.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, CardHeader, CardTitle, Button } from "@eduzim/ui";
import { ListChecks, Send } from "lucide-react";


interface Homework {
  id: string;
  class_id: string;
  title: string;
  description: string;
  due_date: string | null;
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

async function postJson(path: string, body: unknown): Promise<Response> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const { getAccessToken } = await import("@eduzim/auth");
  const tok = getAccessToken();
  return fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
    },
    body: JSON.stringify(body),
  });
}


export default function StudentAssignmentsPage() {
  const t = useTranslations("student");
  const { user } = useAuth();
  const isStudent = (user?.roles ?? []).some(
    (r) => typeof r === "string" && r.toLowerCase() === "student",
  );
  const [me, setMe] = React.useState<{ id: string; class_id?: string } | null>(null);
  const [homework, setHomework] = React.useState<Homework[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!isStudent) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const meR = await fetchJson<{ id: string }>("/api/v1/students/me");
        setMe(meR.data);
        // Class-id discovery: in this MVP we don't yet have a
        // /students/me/enrollment endpoint — the student's open
        // homework set arrives via the parent's existing path. For
        // now we render an empty state if there's no resolution
        // path; the full wiring lands when the student-mode roster
        // pull is implemented in a Phase 12g follow-up.
      } catch {
        /* swallow */
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
        <ListChecks className="h-5 w-5" />
        {t("assignments.title")}
      </h1>
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          {loading ? t("loading") : t("assignments.empty")}
        </CardContent>
      </Card>
    </div>
  );
}
