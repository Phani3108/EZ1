/**
 * Phase 18c — New national template form.
 *
 * Provisioner / EduZimOps form for creating either a
 * NationalHomeworkTemplate or NationalLessonPlanTemplate. Created in
 * draft state — the catalog page handles publish.
 */
"use client";

import React, { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { nationalTemplatesApi } from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription,
} from "@eduzim/ui";

type Kind = "homework" | "lesson-plan";

export default function NewNationalTemplatePage() {
  const router = useRouter();
  const sp = useSearchParams();
  const initialKind = (sp?.get("kind") as Kind | null) ?? "homework";

  const [kind, setKind] = useState<Kind>(initialKind);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [topicCodes, setTopicCodes] = useState("");
  const [gradeLevels, setGradeLevels] = useState("");

  // Homework-only
  const [description, setDescription] = useState("");
  const [defaultDueDays, setDefaultDueDays] = useState<string>("");

  // Lesson-plan-only
  const [objectives, setObjectives] = useState("");
  const [activities, setActivities] = useState("");
  const [resources, setResources] = useState("");
  const [suggestedPeriod, setSuggestedPeriod] = useState<string>("");

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const parseList = (s: string) =>
    s.split(",").map((p) => p.trim()).filter(Boolean);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const common = {
        code: code.trim(),
        title: title.trim(),
        subject_code: subjectCode.trim() || undefined,
        topic_codes: parseList(topicCodes),
        grade_levels: parseList(gradeLevels),
      };
      if (kind === "homework") {
        await nationalTemplatesApi.ministryCreateHomework({
          ...common,
          description: description.trim(),
          default_due_days: defaultDueDays ? Number(defaultDueDays) : undefined,
        });
      } else {
        await nationalTemplatesApi.ministryCreateLessonPlan({
          ...common,
          objectives: objectives.trim() || undefined,
          activities: activities.trim() || undefined,
          resources: resources.trim() || undefined,
          suggested_period_number: suggestedPeriod ? Number(suggestedPeriod) : undefined,
        });
      }
      router.push("/ministry/templates");
    } catch (e: any) {
      setError(e?.detail ?? String(e));
      setBusy(false);
    }
  };

  const canSubmit =
    code.trim().length > 0 &&
    title.trim().length > 0 &&
    (kind === "lesson-plan" || description.trim().length > 0);

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">New Ministry template</h1>
      <p className="text-sm text-muted-foreground">
        Schools see only published rows. Save as draft now; publish later
        from the catalog.
      </p>

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
          Lesson plan
        </button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not save</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Code (unique)" required>
            <input className="input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="HW-001" />
          </Field>
          <Field label="Title" required>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>

          {kind === "homework" ? (
            <>
              <Field label="Description / instructions" required>
                <textarea
                  className="input min-h-[120px]"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </Field>
              <Field label="Default due window (days)">
                <input
                  type="number" className="input"
                  value={defaultDueDays}
                  onChange={(e) => setDefaultDueDays(e.target.value)}
                />
              </Field>
            </>
          ) : (
            <>
              <Field label="Objectives">
                <textarea className="input min-h-[80px]" value={objectives} onChange={(e) => setObjectives(e.target.value)} />
              </Field>
              <Field label="Activities">
                <textarea className="input min-h-[80px]" value={activities} onChange={(e) => setActivities(e.target.value)} />
              </Field>
              <Field label="Resources">
                <textarea className="input min-h-[80px]" value={resources} onChange={(e) => setResources(e.target.value)} />
              </Field>
              <Field label="Suggested period number">
                <input type="number" className="input" value={suggestedPeriod} onChange={(e) => setSuggestedPeriod(e.target.value)} />
              </Field>
            </>
          )}

          <Field label="National subject code (e.g. MATH-F1)">
            <input className="input" value={subjectCode} onChange={(e) => setSubjectCode(e.target.value)} />
          </Field>
          <Field label="National topic codes (comma-separated)">
            <input className="input" value={topicCodes} onChange={(e) => setTopicCodes(e.target.value)} placeholder="T-1, T-2" />
          </Field>
          <Field label="Grade levels (comma-separated)">
            <input className="input" value={gradeLevels} onChange={(e) => setGradeLevels(e.target.value)} placeholder="Form 1, Form 2" />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => router.push("/ministry/templates")}>
              Cancel
            </Button>
            <button
              onClick={submit}
              disabled={!canSubmit || busy}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {busy ? "Saving..." : "Save draft"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label, children, required,
}: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">
        {label} {required && <span className="text-red-600">*</span>}
      </label>
      {children}
      <style jsx>{`
        :global(.input) {
          width: 100%;
          border: 1px solid hsl(var(--border));
          border-radius: 0.375rem;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          background: transparent;
        }
      `}</style>
    </div>
  );
}
