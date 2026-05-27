/**
 * Phase 16f — Topic detail.
 *
 * Renders the cross-index resource list (lesson plans, homework,
 * assessments, formative assessments, questions) for one topic.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { curriculumApi, type TopicResources } from "@/lib/curriculum-api";
import { Card, CardHeader, CardTitle, CardContent, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

export default function TopicDetailPage() {
  const params = useParams<{ topicId: string }>();
  const topicId = params?.topicId ?? "";

  const [data, setData] = useState<TopicResources | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!topicId) return;
    curriculumApi
      .topicResources(topicId)
      .then((r) => setData(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  }, [topicId]);

  if (loading) {
    return <div className="h-64 animate-pulse rounded bg-muted" />;
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {data.topic.name}{" "}
          <span className="text-sm text-muted-foreground font-normal">
            ({data.topic.code})
          </span>
        </h1>
        <p className="text-sm text-muted-foreground">
          Everything in your school that's tagged to this topic.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-xs uppercase text-muted-foreground">Lesson plans</div>
            <div className="mt-1 text-3xl font-bold">{data.counts.lesson_plans}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-xs uppercase text-muted-foreground">Homework</div>
            <div className="mt-1 text-3xl font-bold">{data.counts.homeworks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-xs uppercase text-muted-foreground">Assessments</div>
            <div className="mt-1 text-3xl font-bold">{data.counts.assessments}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-xs uppercase text-muted-foreground">Formative</div>
            <div className="mt-1 text-3xl font-bold">{data.counts.formative_assessments}</div>
          </CardContent>
        </Card>
      </div>

      <ResourceSection title="Lesson plans" rows={data.lesson_plans.map((r) => ({
        id: r.id, primary: r.title,
        secondary: r.scheduled_date ? `Scheduled ${r.scheduled_date}` : "",
      }))} />
      <ResourceSection title="Homework" rows={data.homeworks.map((r) => ({
        id: r.id, primary: r.title,
        secondary: r.due_date ? `Due ${r.due_date}` : "",
      }))} />
      <ResourceSection title="Assessments" rows={data.assessments.map((r) => ({
        id: r.id, primary: r.name,
        secondary: `${r.assessment_type}${r.date ? " · " + r.date : ""}`,
      }))} />
      <ResourceSection title="Formative" rows={data.formative_assessments.map((r) => ({
        id: r.id, primary: r.title, secondary: r.formative_kind,
      }))} />
    </div>
  );
}

function ResourceSection({ title, rows }: { title: string; rows: Array<{ id: string; primary: string; secondary: string }> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <div className="py-2 text-sm text-muted-foreground">No items.</div>
        ) : (
          <ul className="divide-y">
            {rows.map((r) => (
              <li key={r.id} className="py-2 flex justify-between items-baseline">
                <span className="text-sm">{r.primary}</span>
                <span className="text-xs text-muted-foreground">{r.secondary}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
