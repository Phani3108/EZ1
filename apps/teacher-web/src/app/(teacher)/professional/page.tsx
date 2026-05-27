/**
 * Professional Development page — Phase 11f (T-018, T-019).
 *
 * Two teacher self-service surfaces consolidated here:
 *   - CPD records: workshops / courses / conferences a teacher
 *     attended. Self-recorded; admin can review the aggregate.
 *   - Self-evaluation: per-term reflection form. The questionnaire
 *     keys are school-configurable; this page renders a baseline
 *     three-question form. The school can swap questions in a
 *     follow-up without a schema change.
 *
 * T-016 (co-teacher) and T-017 (HoD) are admin actions and don't
 * appear here — they belong on admin-web.
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle, Button, Input,
} from "@eduzim/ui";
import { Award, ClipboardList, Plus } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";


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


interface CpdRecord {
  id: string; title: string; provider: string | null;
  category: string; completed_on: string | null;
  hours: number;
}

interface SelfEval {
  id: string; term_id: string;
  responses: Record<string, unknown>;
  overall_reflection: string | null;
  submitted_at: string | null;
}


export default function ProfessionalPage() {
  const t = useTranslations("professional");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>

      <CpdSection />
      <SelfEvalSection />
    </div>
  );
}


function CpdSection() {
  const t = useTranslations("professional");
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const { data: records, isLoading } = useApiQuery<CpdRecord[]>(
    () => fetchJson<CpdRecord[]>("/api/v1/cpd"),
    [refresh],
  );

  const totalHours = (records ?? []).reduce(
    (acc, r) => acc + (r.hours ?? 0),
    0,
  );

  return (
    <Card data-testid="cpd-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Award className="h-4 w-4" /> {t("cpd.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-sm text-muted-foreground">
            {t("cpd.totalHours", { hours: totalHours })}
          </span>
          <Button
            size="sm"
            onClick={() => setCreating((v) => !v)}
            data-testid="cpd-toggle-form"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            {creating ? t("cancel") : t("cpd.add")}
          </Button>
        </div>

        {creating && (
          <NewCpdForm
            onDone={() => {
              setCreating(false);
              setRefresh((n) => n + 1);
            }}
          />
        )}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : (records?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">{t("cpd.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {records?.map((r) => (
              <li
                key={r.id}
                className="border rounded-md p-3 text-sm"
                data-testid={`cpd-${r.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{r.title}</span>
                  <span className="text-xs rounded-full bg-muted px-2 py-0.5">
                    {r.category}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {r.provider ? `${r.provider} · ` : ""}
                  {r.completed_on ?? ""} · {r.hours}h
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


function NewCpdForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("professional");
  const [title, setTitle] = useState("");
  const [provider, setProvider] = useState("");
  const [category, setCategory] = useState("workshop");
  const [hours, setHours] = useState("1");
  const [completedOn, setCompletedOn] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [sending, setSending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || sending) return;
    setSending(true);
    try {
      await postJson("/api/v1/cpd", {
        title: title.trim(),
        provider: provider.trim() || undefined,
        category,
        completed_on: completedOn,
        hours: Number(hours) || 0,
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
      data-testid="cpd-form"
    >
      <Input
        value={title}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setTitle(e.target.value)
        }
        placeholder={t("cpd.titlePlaceholder")}
        required
      />
      <Input
        value={provider}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          setProvider(e.target.value)
        }
        placeholder={t("cpd.providerPlaceholder")}
      />
      <div className="grid grid-cols-3 gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        >
          {["workshop", "course", "conference", "webinar", "other"].map(
            (c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ),
          )}
        </select>
        <input
          type="date"
          value={completedOn}
          onChange={(e) => setCompletedOn(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        />
        <Input
          type="number"
          value={hours}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setHours(e.target.value)
          }
          placeholder={t("cpd.hoursPlaceholder")}
        />
      </div>
      <Button type="submit" size="sm" disabled={sending}>
        {sending ? t("loading") : t("cpd.save")}
      </Button>
    </form>
  );
}


// ─── Self-evaluation (T-019) ──────────────────────────────────────


function SelfEvalSection() {
  const t = useTranslations("professional");
  const [termId, setTermId] = useState("");
  const [strengths, setStrengths] = useState("");
  const [growthAreas, setGrowthAreas] = useState("");
  const [planForNext, setPlanForNext] = useState("");
  const [reflection, setReflection] = useState("");
  const [sending, setSending] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!termId.trim() || sending) return;
    setSending(true);
    try {
      const r = await postJson("/api/v1/self-evaluations", {
        term_id: termId.trim(),
        responses: {
          strengths,
          growth_areas: growthAreas,
          plan_for_next_term: planForNext,
        },
        overall_reflection: reflection,
      });
      if (r.ok) {
        const body = await r.json();
        setSavedAt(body.data.submitted_at);
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <Card data-testid="self-eval-section">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ClipboardList className="h-4 w-4" /> {t("selfEval.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={submit}
          className="space-y-3"
          data-testid="self-eval-form"
        >
          <Input
            value={termId}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setTermId(e.target.value)
            }
            placeholder={t("selfEval.termIdPlaceholder")}
            required
          />
          <div>
            <label className="text-sm font-medium block mb-1">
              {t("selfEval.strengths")}
            </label>
            <textarea
              value={strengths}
              onChange={(e) => setStrengths(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">
              {t("selfEval.growthAreas")}
            </label>
            <textarea
              value={growthAreas}
              onChange={(e) => setGrowthAreas(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">
              {t("selfEval.planForNext")}
            </label>
            <textarea
              value={planForNext}
              onChange={(e) => setPlanForNext(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">
              {t("selfEval.overallReflection")}
            </label>
            <textarea
              value={reflection}
              onChange={(e) => setReflection(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
            />
          </div>
          <Button type="submit" size="sm" disabled={sending}>
            {sending ? t("loading") : t("selfEval.save")}
          </Button>
          {savedAt && (
            <span className="text-xs text-green-700 ml-2">
              {t("selfEval.savedAt", { ts: new Date(savedAt).toLocaleString() })}
            </span>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
