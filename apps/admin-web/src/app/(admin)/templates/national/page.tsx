/**
 * Phase 18c — Browse + adopt Ministry-distributed templates.
 *
 * HoD / SchoolAdmin lands here when they want a canonical template
 * from the Ministry catalog. Each card shows the template, an
 * "Adopt" button (or "Adopted" badge), and on-adopt summary of how
 * many topic codes resolved to local topics + any that did not (so
 * the HoD knows to patch them).
 */
"use client";

import React, { useEffect, useState } from "react";
import {
  nationalTemplatesApi,
  type NationalTemplateRow,
  type AdoptResult,
} from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Alert, AlertTitle, AlertDescription, Badge,
} from "@eduzim/ui";

type Kind = "homework" | "lesson-plan";

export default function BrowseNationalTemplatesPage() {
  const [kind, setKind] = useState<Kind>("homework");
  const [rows, setRows] = useState<NationalTemplateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adoptingId, setAdoptingId] = useState<string | null>(null);
  const [lastAdopt, setLastAdopt] = useState<AdoptResult | null>(null);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = kind === "homework"
        ? await nationalTemplatesApi.browseHomework()
        : await nationalTemplatesApi.browseLessonPlan();
      setRows(r.data);
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, [kind]);

  const handleAdopt = async (id: string) => {
    setAdoptingId(id);
    setLastAdopt(null);
    try {
      const r = kind === "homework"
        ? await nationalTemplatesApi.adoptHomework(id)
        : await nationalTemplatesApi.adoptLessonPlan(id);
      setLastAdopt(r.data);
      reload();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setAdoptingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">National templates catalog</h1>
        <p className="text-sm text-muted-foreground">
          Canonical homework + lesson-plan patterns published by the Ministry.
          Adopt brings the template into your school's library where any
          teacher can instantiate it into a class.
        </p>
      </div>

      <div className="flex rounded-md border w-fit">
        <button
          onClick={() => setKind("homework")}
          className={"px-3 py-1.5 text-sm " + (kind === "homework" ? "bg-primary text-primary-foreground" : "")}
        >
          Homework
        </button>
        <button
          onClick={() => setKind("lesson-plan")}
          className={"px-3 py-1.5 text-sm border-l " + (kind === "lesson-plan" ? "bg-primary text-primary-foreground" : "")}
        >
          Lesson plans
        </button>
      </div>

      {lastAdopt && (
        <Alert>
          <AlertTitle>
            {lastAdopt.idempotent ? "Already adopted" : "Adopted into your library"}
          </AlertTitle>
          <AlertDescription>
            {lastAdopt.topics_resolved} topic{lastAdopt.topics_resolved === 1 ? "" : "s"} resolved to your local curriculum.
            {lastAdopt.topics_unresolved > 0 && (
              <>
                {" "}{lastAdopt.topics_unresolved} unresolved
                {lastAdopt.unresolved_topic_codes && lastAdopt.unresolved_topic_codes.length > 0 && (
                  <> (<code className="text-xs">{lastAdopt.unresolved_topic_codes.join(", ")}</code>)</>
                )}
                {" "}— adopt the parent ZIMSEC subject first to resolve them.
              </>
            )}
            {lastAdopt.subject_resolved === false && (
              <> The template's subject code is not in your school's curriculum yet — the local template was created without a subject link.</>
            )}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="h-64 animate-pulse rounded bg-muted" />
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            The Ministry hasn't published any {kind === "homework" ? "homework" : "lesson plan"} templates yet.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {rows.map((t) => (
            <Card key={t.id}>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  {t.title}
                  <span className="text-xs text-muted-foreground font-normal">
                    {t.code}
                  </span>
                  {t.adopted_local_template_id && (
                    <Badge>adopted</Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {kind === "homework" ? (
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {t.description}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {t.objectives ?? "—"}
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                  {t.subject_code && (
                    <Badge variant="outline">{t.subject_code}</Badge>
                  )}
                  {(t.topic_codes || []).map((c) => (
                    <Badge key={c} variant="outline">{c}</Badge>
                  ))}
                  {(t.grade_levels || []).map((g) => (
                    <Badge key={g} variant="outline">{g}</Badge>
                  ))}
                </div>
                <div className="flex justify-end">
                  {t.adopted_local_template_id ? (
                    <span className="text-xs text-muted-foreground">
                      Already in your library
                    </span>
                  ) : (
                    <button
                      onClick={() => handleAdopt(t.id)}
                      disabled={adoptingId === t.id}
                      className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {adoptingId === t.id ? "Adopting..." : "Adopt"}
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
