/**
 * Phase 16f — Teacher-web Curriculum overview.
 *
 * Subject picker on the left; tree view of the chosen subject on the
 * right. Click a topic to drill into its resource list (Phase 16f
 * topic detail page).
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  curriculumApi,
  type SchoolSubject,
  type CurriculumTree,
} from "@/lib/curriculum-api";
import { Card, CardHeader, CardTitle, CardContent, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

export default function CurriculumPage() {
  const [subjects, setSubjects] = useState<SchoolSubject[]>([]);
  const [activeSubjectId, setActiveSubjectId] = useState<string | null>(null);
  const [tree, setTree] = useState<CurriculumTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    curriculumApi
      .listSubjects()
      .then((r) => {
        setSubjects(r.data);
        if (r.data.length > 0) {
          setActiveSubjectId(r.data[0].id);
        }
      })
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeSubjectId) return;
    setTree(null);
    curriculumApi
      .tree(activeSubjectId)
      .then((r) => setTree(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)));
  }, [activeSubjectId]);

  if (loading) {
    return <div className="h-64 animate-pulse rounded bg-muted" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Curriculum</h1>
        <p className="text-sm text-muted-foreground">
          Subjects, units, and topics for your school. Click a topic to
          see every lesson plan, homework, and assessment you've tagged
          to it.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {subjects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No subjects yet. Ask your school admin to adopt a ZIMSEC
            subject or create one from{" "}
            <Link href="/curriculum/adopt" className="text-primary hover:underline">
              the curriculum setup
            </Link>
            .
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <aside className="space-y-1">
            <div className="text-xs uppercase text-muted-foreground px-2 pb-1">
              Subjects
            </div>
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSubjectId(s.id)}
                className={
                  "w-full text-left text-sm rounded-md px-3 py-2 " +
                  (s.id === activeSubjectId
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground")
                }
              >
                <div>{s.name}</div>
                <div className="text-xs text-muted-foreground">{s.code}</div>
                {s.grade_levels.length > 0 && (
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {s.grade_levels.join(" · ")}
                  </div>
                )}
              </button>
            ))}
          </aside>

          <div className="min-w-0">
            {!tree ? (
              <div className="h-64 animate-pulse rounded bg-muted" />
            ) : tree.units.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-sm text-muted-foreground">
                  This subject has no units yet. Ask your school admin
                  to add some.
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {tree.units.map((u) => (
                  <Card key={u.id}>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center justify-between">
                        <span>
                          {u.name}{" "}
                          <span className="text-xs text-muted-foreground font-normal ml-1">
                            ({u.code})
                          </span>
                        </span>
                        {u.grade_level && (
                          <span className="text-xs text-muted-foreground font-normal">
                            {u.grade_level}
                          </span>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {(u.topics || []).length === 0 ? (
                        <div className="text-sm text-muted-foreground">
                          No topics in this unit.
                        </div>
                      ) : (
                        <ul className="divide-y">
                          {(u.topics || []).map((t) => (
                            <li key={t.id} className="py-2">
                              <Link
                                href={`/curriculum/${t.id}`}
                                className="block hover:bg-muted/50 -mx-2 px-2 py-1 rounded"
                              >
                                <div className="flex items-center justify-between">
                                  <div>
                                    <div className="text-sm font-medium">{t.name}</div>
                                    <div className="text-xs text-muted-foreground">
                                      {t.code}
                                      {t.national_topic_id && " · ZIMSEC"}
                                    </div>
                                  </div>
                                </div>
                                {t.learning_outcomes && (
                                  <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
                                    {t.learning_outcomes}
                                  </div>
                                )}
                                {(t.subtopics || []).length > 0 && (
                                  <ul className="mt-2 ml-4 space-y-1 border-l pl-3">
                                    {(t.subtopics || []).map((st) => (
                                      <li key={st.id}>
                                        <Link
                                          href={`/curriculum/${st.id}`}
                                          className="text-sm text-muted-foreground hover:text-primary"
                                        >
                                          ↳ {st.name}{" "}
                                          <span className="text-xs">({st.code})</span>
                                        </Link>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
