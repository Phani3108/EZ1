/**
 * Phase 18c — Ministry-distributed templates catalog.
 *
 * Provisioner / EduZimOps view: list every NationalHomeworkTemplate +
 * NationalLessonPlanTemplate, with publish + archive controls.
 * Schools can adopt published rows from /templates/national in admin-web.
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  nationalTemplatesApi,
  type NationalTemplateRow,
} from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription, Badge,
} from "@eduzim/ui";

type Kind = "homework" | "lesson-plan";

export default function MinistryTemplatesPage() {
  const [kind, setKind] = useState<Kind>("homework");
  const [rows, setRows] = useState<NationalTemplateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = kind === "homework"
        ? await nationalTemplatesApi.ministryListHomework(includeArchived)
        : await nationalTemplatesApi.ministryListLessonPlan(includeArchived);
      setRows(r.data);
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, [kind, includeArchived]);

  const handlePublish = async (id: string) => {
    if (kind === "homework") {
      await nationalTemplatesApi.ministryPublishHomework(id);
    } else {
      await nationalTemplatesApi.ministryPublishLessonPlan(id);
    }
    reload();
  };
  const handleArchive = async (id: string) => {
    if (kind === "homework") {
      await nationalTemplatesApi.ministryArchiveHomework(id);
    } else {
      await nationalTemplatesApi.ministryArchiveLessonPlan(id);
    }
    reload();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Ministry templates</h1>
          <p className="text-sm text-muted-foreground">
            Distribute canonical homework + lesson-plan patterns to every
            school. Published rows show in each school's "Adopt national
            template" picker.
          </p>
        </div>
        <Button>
          <Link href={`/ministry/templates/new?kind=${kind}`}>+ New template</Link>
        </Button>
      </div>

      <div className="flex items-center gap-3 text-sm">
        <div className="flex rounded-md border">
          <button
            onClick={() => setKind("homework")}
            className={"px-3 py-1.5 " + (kind === "homework" ? "bg-primary text-primary-foreground" : "")}
          >
            Homework
          </button>
          <button
            onClick={() => setKind("lesson-plan")}
            className={"px-3 py-1.5 border-l " + (kind === "lesson-plan" ? "bg-primary text-primary-foreground" : "")}
          >
            Lesson plans
          </button>
        </div>
        <label className="ml-4 inline-flex items-center gap-2 text-muted-foreground">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
          />
          Show archived
        </label>
      </div>

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
            No templates yet. Click "New template" to publish your first.
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
                  {t.archived_at ? (
                    <Badge variant="outline" className="border-red-500 text-red-700">archived</Badge>
                  ) : t.published_at ? (
                    <Badge>published</Badge>
                  ) : (
                    <Badge variant="outline">draft</Badge>
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
                <div className="flex justify-end gap-2">
                  {!t.published_at && !t.archived_at && (
                    <button
                      onClick={() => handlePublish(t.id)}
                      className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      Publish
                    </button>
                  )}
                  {!t.archived_at && (
                    <button
                      onClick={() => handleArchive(t.id)}
                      className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                    >
                      Archive
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
