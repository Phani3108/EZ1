/**
 * Student-life page — Phase 11e (T-004, T-006, T-003).
 *
 * Three teacher-facing surfaces consolidated on one page:
 *   - Incidents: quick log of behaviour / discipline events.
 *   - Substitute grants: shows the active grants involving the
 *     teacher (either as the absentee or the substitute). Issuing
 *     grants is admin-only — the form is admin-only too.
 *   - Homework: list + quick-assign.
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle, Button, Input,
} from "@eduzim/ui";
import {
  AlertOctagon, UserCheck, BookOpenCheck, Plus,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher } from "@/lib/api";
import { useAuth } from "@eduzim/auth";
import type { TeacherClass } from "@eduzim/api-client";


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


interface Incident {
  id: string; student_id: string; severity: string;
  category: string; summary: string;
  occurred_at: string | null;
  parent_notified_at: string | null;
  resolved_at: string | null;
}

interface SubstituteGrant {
  id: string;
  absent_teacher_user_id: string;
  grantee_user_id: string;
  starts_at: string | null;
  ends_at: string | null;
  reason: string | null;
}

interface Homework {
  id: string; title: string; description: string;
  due_date: string | null; class_id: string;
}


export default function StudentLifePage() {
  const t = useTranslations("studentLife");
  const { data: classes } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    [],
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>

      <IncidentsSection classes={classes ?? []} />
      <SubstituteSection />
      <HomeworkSection classes={classes ?? []} />
    </div>
  );
}


// ─── Incidents (T-004) ─────────────────────────────────────────────


function IncidentsSection({ classes }: { classes: TeacherClass[] }) {
  const t = useTranslations("studentLife");
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const { data: incidents, isLoading } = useApiQuery<Incident[]>(
    () => fetchJson<Incident[]>("/api/v1/incidents"),
    [refresh],
  );

  return (
    <Card data-testid="incidents-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertOctagon className="h-4 w-4" /> {t("incidents.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          type="button"
          size="sm"
          onClick={() => setCreating((v) => !v)}
          data-testid="incidents-toggle-form"
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          {creating ? t("cancel") : t("incidents.create")}
        </Button>

        {creating && (
          <NewIncidentForm
            classes={classes}
            onDone={() => {
              setCreating(false);
              setRefresh((n) => n + 1);
            }}
          />
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (incidents?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">{t("incidents.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {incidents?.map((i) => (
              <li
                key={i.id}
                className="border rounded-md p-3 text-sm"
                data-testid={`incident-${i.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{i.summary}</span>
                  <span
                    className={`text-xs rounded-full px-2 py-0.5 ${
                      i.severity === "critical"
                        ? "bg-red-100 text-red-700"
                        : i.severity === "serious"
                        ? "bg-orange-100 text-orange-700"
                        : i.severity === "moderate"
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {i.severity}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {i.category} ·{" "}
                  {i.occurred_at
                    ? new Date(i.occurred_at).toLocaleString()
                    : "—"}
                </p>
                {i.resolved_at && (
                  <p className="text-xs text-green-700 mt-1">
                    {t("incidents.resolvedAt", {
                      ts: new Date(i.resolved_at).toLocaleDateString(),
                    })}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


function NewIncidentForm({
  classes,
  onDone,
}: {
  classes: TeacherClass[];
  onDone: () => void;
}) {
  const t = useTranslations("studentLife");
  const [studentId, setStudentId] = useState("");
  const [classId, setClassId] = useState("");
  const [severity, setSeverity] = useState("minor");
  const [category, setCategory] = useState("other");
  const [summary, setSummary] = useState("");
  const [sending, setSending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId.trim() || !summary.trim() || sending) return;
    setSending(true);
    try {
      await postJson("/api/v1/incidents", {
        student_id: studentId.trim(),
        class_id: classId || undefined,
        severity, category,
        summary: summary.trim(),
      });
      onDone();
    } finally {
      setSending(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="border rounded-md p-3 space-y-2 bg-muted/20"
      data-testid="incident-form"
    >
      <Input
        value={studentId}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setStudentId(e.target.value)
        }
        placeholder={t("incidents.studentIdPlaceholder")}
        required
      />
      <select
        value={classId}
        onChange={(e) => setClassId(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background"
      >
        <option value="">{t("incidents.classOptional")}</option>
        {classes.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} — {c.section}
          </option>
        ))}
      </select>
      <div className="grid grid-cols-2 gap-2">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        >
          <option value="minor">{t("incidents.severityMinor")}</option>
          <option value="moderate">{t("incidents.severityModerate")}</option>
          <option value="serious">{t("incidents.severitySerious")}</option>
          <option value="critical">{t("incidents.severityCritical")}</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        >
          {[
            "bullying", "late", "uniform", "disruption", "absence",
            "academic_dishonesty", "fighting", "other",
          ].map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <textarea
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder={t("incidents.summaryPlaceholder")}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
        required
      />
      <Button type="submit" size="sm" disabled={sending}>
        {sending ? t("loading") : t("incidents.save")}
      </Button>
    </form>
  );
}


// ─── Substitute grants (T-006) ────────────────────────────────────


function SubstituteSection() {
  const t = useTranslations("studentLife");
  const { user } = useAuth();
  const { data: grants, isLoading } = useApiQuery<SubstituteGrant[]>(
    () =>
      user
        ? fetchJson<SubstituteGrant[]>(
            `/api/v1/substitute-grants?grantee_user_id=${user.id}`,
          )
        : Promise.resolve({ data: [] as SubstituteGrant[] }),
    [user?.id],
  );

  return (
    <Card data-testid="substitute-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <UserCheck className="h-4 w-4" /> {t("substitute.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground mb-3">
          {t("substitute.hint")}
        </p>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (grants?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("substitute.empty")}
          </p>
        ) : (
          <ul className="space-y-2">
            {grants?.map((g) => (
              <li key={g.id} className="border rounded-md p-3 text-sm">
                <p className="font-medium">
                  {t("substitute.covering", {
                    teacher: g.absent_teacher_user_id.slice(0, 8),
                  })}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {g.starts_at
                    ? new Date(g.starts_at).toLocaleString()
                    : "—"}
                  {" → "}
                  {g.ends_at ? new Date(g.ends_at).toLocaleString() : "—"}
                </p>
                {g.reason && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {g.reason}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Homework (T-003) ─────────────────────────────────────────────


function HomeworkSection({ classes }: { classes: TeacherClass[] }) {
  const t = useTranslations("studentLife");
  const firstClass = classes[0]?.id ?? "";
  const [classId, setClassId] = useState(firstClass);
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);

  React.useEffect(() => {
    if (!classId && firstClass) setClassId(firstClass);
  }, [firstClass, classId]);

  const { data: homework, isLoading } = useApiQuery<Homework[]>(
    () =>
      classId
        ? fetchJson<Homework[]>(`/api/v1/homework?class_id=${classId}`)
        : Promise.resolve({ data: [] as Homework[] }),
    [classId, refresh],
  );

  return (
    <Card data-testid="homework-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpenCheck className="h-4 w-4" /> {t("homework.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm bg-background"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} — {c.section}
              </option>
            ))}
          </select>
          <Button
            type="button"
            size="sm"
            onClick={() => setCreating((v) => !v)}
            disabled={!classId}
            data-testid="homework-toggle-form"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            {creating ? t("cancel") : t("homework.assign")}
          </Button>
        </div>

        {creating && classId && (
          <AssignHomeworkForm
            classId={classId}
            onDone={() => {
              setCreating(false);
              setRefresh((n) => n + 1);
            }}
          />
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (homework?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">{t("homework.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {homework?.map((h) => (
              <li
                key={h.id}
                className="border rounded-md p-3 text-sm"
                data-testid={`homework-${h.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{h.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {h.due_date ? `${t("homework.due")} ${h.due_date}` : "—"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {h.description}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


function AssignHomeworkForm({
  classId,
  onDone,
}: {
  classId: string;
  onDone: () => void;
}) {
  const t = useTranslations("studentLife");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState(
    new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
  );
  const [sending, setSending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim() || sending) return;
    setSending(true);
    try {
      await postJson("/api/v1/homework", {
        class_id: classId,
        title: title.trim(),
        description: description.trim(),
        due_date: dueDate,
      });
      onDone();
    } finally {
      setSending(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="border rounded-md p-3 space-y-2 bg-muted/20"
      data-testid="homework-form"
    >
      <Input
        value={title}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setTitle(e.target.value)
        }
        placeholder={t("homework.titlePlaceholder")}
        required
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder={t("homework.descriptionPlaceholder")}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
        required
      />
      <input
        type="date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
        className="rounded-md border px-3 py-2 text-sm bg-background"
        required
      />
      <Button type="submit" size="sm" disabled={sending}>
        {sending ? t("loading") : t("homework.save")}
      </Button>
    </form>
  );
}
