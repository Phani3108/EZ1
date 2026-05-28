/**
 * Phase 16g — Admin-web Curriculum overview.
 *
 * Same Subject-picker + tree view as the teacher-web side, plus an
 * "Adopt ZIMSEC subject" CTA in the header. HoD-driven curriculum
 * management.
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  curriculumApi,
  type SchoolSubject,
  type CurriculumTree,
} from "@/lib/curriculum-api";
import { Card, CardHeader, CardTitle, CardContent, Button, LinkButton, Alert, AlertTitle, AlertDescription, Badge } from "@eduzim/ui";

export default function CurriculumOverviewPage() {
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
        if (r.data.length > 0) setActiveSubjectId(r.data[0].id);
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

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Curriculum</h1>
          <p className="text-sm text-muted-foreground">
            Your school's subjects, units, topics. Adopt a ZIMSEC
            subject to seed the tree from the national reference, or
            create custom topics manually / via CSV.
          </p>
        </div>
        <div className="flex gap-2">
          <LinkButton variant="outline" href="/curriculum/coverage">
            Coverage
          </LinkButton>
          <LinkButton href="/curriculum/adopt">
            Adopt ZIMSEC subject
          </LinkButton>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="h-64 animate-pulse rounded bg-muted" />
      ) : subjects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No subjects yet. Adopt a ZIMSEC subject above to start.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <aside className="space-y-1">
            <div className="text-xs uppercase text-muted-foreground px-2 pb-1">
              Subjects ({subjects.length})
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
                <div className="flex items-center gap-2">
                  <span>{s.name}</span>
                  {s.is_stale && (
                    <Badge variant="outline" className="text-[10px] border-amber-500 text-amber-700">
                      stale
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {s.code}
                  {s.national_subject_id && (
                    <>
                      {" · ZIMSEC v"}{s.adopted_national_version ?? "?"}
                      {s.is_stale && s.national_current_version != null && (
                        <> (current v{s.national_current_version})</>
                      )}
                    </>
                  )}
                </div>
              </button>
            ))}
          </aside>

          <div className="min-w-0 space-y-4">
            {activeSubjectId && (() => {
              const active = subjects.find((s) => s.id === activeSubjectId);
              if (!active || !active.is_stale) return null;
              return (
                <Alert>
                  <AlertTitle>
                    A newer ZIMSEC version (v{active.national_current_version}) is available
                  </AlertTitle>
                  <AlertDescription className="flex items-center justify-between gap-3">
                    <span>
                      You adopted v{active.adopted_national_version}. Review what the upgrade
                      will change before pulling it in. Custom topics are always preserved.
                    </span>
                    <LinkButton href={`/curriculum/${active.id}/upgrade-preview`}>
                      Review upgrade
                    </LinkButton>
                  </AlertDescription>
                </Alert>
              );
            })()}
            {!tree ? (
              <div className="h-64 animate-pulse rounded bg-muted" />
            ) : tree.units.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-sm text-muted-foreground">
                  No units in this subject yet.
                </CardContent>
              </Card>
            ) : (
              tree.units.map((u) => (
                <Card key={u.id}>
                  <CardHeader>
                    <CardTitle className="text-base">
                      {u.name}{" "}
                      <span className="text-xs text-muted-foreground font-normal">
                        ({u.code})
                        {u.grade_level ? ` · ${u.grade_level}` : ""}
                      </span>
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
                            <div className="flex items-center justify-between">
                              <div>
                                <div className="text-sm font-medium">{t.name}</div>
                                <div className="text-xs text-muted-foreground">
                                  {t.code}
                                  {t.national_topic_id && " · ZIMSEC"}
                                </div>
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
