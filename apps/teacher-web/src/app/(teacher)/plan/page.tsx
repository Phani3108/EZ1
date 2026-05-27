/**
 * Plan page — Phase 11d (T-010, T-005, T-013, T-012).
 *
 * Single landing surface for the teacher's planning tools:
 *
 *   - Period schedule (T-010): displays the school's period schedule.
 *     Read-only here (admin manages elsewhere).
 *   - Lesson plans (T-005): list + quick-create. Templates and per-class
 *     instances live in the same list with a filter chip.
 *   - Formative assessments (T-013): list active polls / exit tickets /
 *     quizzes for the teacher's classes. Quick-create panel.
 *   - Exam seat plans (T-012): the link is here for discoverability,
 *     but the seat-plan editor itself is admin-side (the teacher uses
 *     the print-out at the door).
 *
 * Why one page: each sub-feature on its own would be three lines of
 * UI today. The full editor pages will land in Phase 11g when the
 * teacher cohort has piloted these workflows.
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle, Button, Input,
} from "@eduzim/ui";
import {
  Clock, BookText, Vote, LayoutGrid, Plus,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher } from "@/lib/api";
import type { TeacherClass } from "@eduzim/api-client";


// ─── Minimal types (kept inline so the api-client doesn't need a
//     dozen new exports for what is currently a list-screen MVP). ───

interface SchoolPeriod {
  id: string;
  period_number: number;
  name: string;
  start_time: string | null;
  end_time: string | null;
}

interface LessonPlan {
  id: string;
  title: string;
  is_template: boolean;
  class_id: string | null;
  scheduled_date: string | null;
  scheduled_period_number: number | null;
  objectives: string | null;
  archived_at: string | null;
}

interface Formative {
  id: string;
  title: string;
  formative_kind: string;
  prompt: string;
  class_id: string;
  created_at: string;
  closed_at: string | null;
  response_count: number;
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


export default function PlanPage() {
  const t = useTranslations("plan");
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

      <PeriodsSection />
      <LessonPlansSection classes={classes ?? []} />
      <FormativesSection classes={classes ?? []} />
      <SeatPlansHint />
    </div>
  );
}


// ─── Periods (T-010) ───────────────────────────────────────────────


function PeriodsSection() {
  const t = useTranslations("plan");
  const { data: periods, isLoading } = useApiQuery<SchoolPeriod[]>(
    () => fetchJson<SchoolPeriod[]>("/api/v1/periods"),
    [],
  );

  return (
    <Card data-testid="plan-periods-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-4 w-4" /> {t("periods.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (periods?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">{t("periods.empty")}</p>
        ) : (
          <ul className="divide-y">
            {periods?.map((p) => (
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
  );
}


// ─── Lesson plans (T-005) ──────────────────────────────────────────


function LessonPlansSection({ classes }: { classes: TeacherClass[] }) {
  const t = useTranslations("plan");
  const [templatesOnly, setTemplatesOnly] = useState(false);
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const { data: plans, isLoading } = useApiQuery<LessonPlan[]>(
    () =>
      fetchJson<LessonPlan[]>(
        `/api/v1/lesson-plans${templatesOnly ? "?templates_only=true" : ""}`,
      ),
    [templatesOnly, refresh],
  );

  return (
    <Card data-testid="plan-lesson-plans-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookText className="h-4 w-4" /> {t("lessonPlans.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTemplatesOnly((v) => !v)}
            className={`text-xs rounded-full px-3 py-1 border ${
              templatesOnly
                ? "bg-primary text-primary-foreground border-primary"
                : "border-muted-foreground/30 text-muted-foreground"
            }`}
            data-testid="plan-templates-toggle"
          >
            {t("lessonPlans.templatesOnly")}
          </button>
          <Button
            type="button"
            size="sm"
            onClick={() => setCreating(true)}
            data-testid="plan-lesson-plan-create-button"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            {t("lessonPlans.create")}
          </Button>
        </div>

        {creating && (
          <NewLessonPlanForm
            classes={classes}
            onDone={() => {
              setCreating(false);
              setRefresh((n) => n + 1);
            }}
            onCancel={() => setCreating(false)}
          />
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (plans?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("lessonPlans.empty")}
          </p>
        ) : (
          <ul className="space-y-2">
            {plans?.map((p) => (
              <li
                key={p.id}
                className="border rounded-md p-3 text-sm"
                data-testid={`plan-lesson-plan-${p.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{p.title}</span>
                  {p.is_template ? (
                    <span className="text-xs rounded-full bg-muted px-2 py-0.5">
                      {t("lessonPlans.templateBadge")}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {p.scheduled_date ?? "—"}
                    </span>
                  )}
                </div>
                {p.objectives && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {p.objectives}
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


function NewLessonPlanForm({
  classes,
  onDone,
  onCancel,
}: {
  classes: TeacherClass[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("plan");
  const [title, setTitle] = useState("");
  const [classId, setClassId] = useState("");
  const [objectives, setObjectives] = useState("");
  const [sending, setSending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || sending) return;
    setSending(true);
    try {
      const baseUrl =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const { getAccessToken } = await import("@eduzim/auth");
      const tok = getAccessToken();
      await fetch(`${baseUrl}/api/v1/lesson-plans`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          title: title.trim(),
          class_id: classId || undefined,
          objectives: objectives.trim() || undefined,
        }),
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
      data-testid="plan-lesson-plan-form"
    >
      <Input
        value={title}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setTitle(e.target.value)
        }
        placeholder={t("lessonPlans.titlePlaceholder")}
        required
      />
      <select
        value={classId}
        onChange={(e) => setClassId(e.target.value)}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background"
      >
        <option value="">{t("lessonPlans.makeTemplate")}</option>
        {classes.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} — {c.section}
          </option>
        ))}
      </select>
      <textarea
        value={objectives}
        onChange={(e) => setObjectives(e.target.value)}
        placeholder={t("lessonPlans.objectivesPlaceholder")}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={sending}>
          {sending ? t("loading") : t("lessonPlans.save")}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}


// ─── Formatives (T-013) ────────────────────────────────────────────


function FormativesSection({ classes }: { classes: TeacherClass[] }) {
  const t = useTranslations("plan");
  const firstClass = classes[0]?.id ?? "";
  const [classId, setClassId] = useState(firstClass);
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);

  React.useEffect(() => {
    if (!classId && firstClass) setClassId(firstClass);
  }, [firstClass, classId]);

  const { data: formatives, isLoading } = useApiQuery<Formative[]>(
    () =>
      classId
        ? fetchJson<Formative[]>(
            `/api/v1/formative-assessments?class_id=${classId}`,
          )
        : Promise.resolve({ data: [] as Formative[] }),
    [classId, refresh],
  );

  return (
    <Card data-testid="plan-formatives-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Vote className="h-4 w-4" /> {t("formatives.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm bg-background"
            data-testid="plan-formatives-class-select"
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
            onClick={() => setCreating(true)}
            disabled={!classId}
            data-testid="plan-formative-create-button"
          >
            <Plus className="h-3.5 w-3.5 mr-1" /> {t("formatives.create")}
          </Button>
        </div>

        {creating && classId && (
          <NewFormativeForm
            classId={classId}
            onDone={() => {
              setCreating(false);
              setRefresh((n) => n + 1);
            }}
            onCancel={() => setCreating(false)}
          />
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (formatives?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("formatives.empty")}
          </p>
        ) : (
          <ul className="space-y-2">
            {formatives?.map((f) => (
              <li
                key={f.id}
                className="border rounded-md p-3 text-sm"
                data-testid={`plan-formative-${f.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{f.title}</span>
                  <span className="text-xs rounded-full bg-muted px-2 py-0.5">
                    {f.formative_kind}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {f.prompt}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {t("formatives.responses", { n: f.response_count })}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


function NewFormativeForm({
  classId,
  onDone,
  onCancel,
}: {
  classId: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("plan");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"poll" | "exit_ticket" | "quiz">("exit_ticket");
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !prompt.trim() || sending) return;
    setSending(true);
    try {
      const baseUrl =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const { getAccessToken } = await import("@eduzim/auth");
      const tok = getAccessToken();
      await fetch(`${baseUrl}/api/v1/formative-assessments`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        body: JSON.stringify({
          class_id: classId,
          title: title.trim(),
          formative_kind: kind,
          prompt: prompt.trim(),
        }),
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
      data-testid="plan-formative-form"
    >
      <Input
        value={title}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setTitle(e.target.value)
        }
        placeholder={t("formatives.titlePlaceholder")}
        required
      />
      <select
        value={kind}
        onChange={(e) =>
          setKind(e.target.value as "poll" | "exit_ticket" | "quiz")
        }
        className="w-full rounded-md border px-3 py-2 text-sm bg-background"
      >
        <option value="exit_ticket">{t("formatives.kindExitTicket")}</option>
        <option value="poll">{t("formatives.kindPoll")}</option>
        <option value="quiz">{t("formatives.kindQuiz")}</option>
      </select>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={t("formatives.promptPlaceholder")}
        className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
        required
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={sending}>
          {sending ? t("loading") : t("formatives.save")}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}


// ─── Seat plans hint (T-012) ──────────────────────────────────────


function SeatPlansHint() {
  const t = useTranslations("plan");
  return (
    <Card data-testid="plan-seat-plans-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <LayoutGrid className="h-4 w-4" /> {t("seatPlans.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{t("seatPlans.hint")}</p>
      </CardContent>
    </Card>
  );
}
