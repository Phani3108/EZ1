/**
 * Phase 16g — Adopt a ZIMSEC subject.
 *
 * Lists every published NationalSubject; HoD/SchoolAdmin clicks
 * "Adopt" → the entire unit + topic tree clones into the school.
 * Idempotent: re-adopting is a no-op.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { curriculumApi, type NationalSubjectRow } from "@/lib/curriculum-api";
import { Card, CardHeader, CardTitle, CardContent, Button, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

export default function AdoptSubjectPage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<NationalSubjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [adopting, setAdopting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    curriculumApi
      .listNationalSubjects({ published_only: true })
      .then((r) => setSubjects(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  }, []);

  const handleAdopt = async (subj: NationalSubjectRow) => {
    setAdopting(subj.id);
    setError(null);
    setSuccess(null);
    try {
      const r = await curriculumApi.adoptSubject({
        national_subject_id: subj.id,
      });
      const d = r.data;
      if (d.idempotent) {
        setSuccess(
          `${subj.name} is already adopted at your school.`,
        );
      } else {
        setSuccess(
          `Adopted "${subj.name}" with ${d.units_cloned} units and ${d.topics_cloned} topics.`,
        );
        setTimeout(() => router.push("/curriculum"), 1200);
      }
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setAdopting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Adopt a ZIMSEC subject</h1>
        <p className="text-sm text-muted-foreground">
          Pick a published national curriculum subject. The whole
          unit + topic tree clones into your school's curriculum.
          You can edit topics afterwards.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not adopt</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert>
          <AlertTitle>Done</AlertTitle>
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : subjects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No published ZIMSEC subjects yet. Ask EduZim Operations
            to publish the syllabus (or import from CSV via the
            Ministry curriculum page).
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {subjects.map((s) => (
            <Card key={s.id}>
              <CardHeader>
                <CardTitle className="text-base">{s.name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="text-xs font-mono text-muted-foreground">
                  {s.country} · {s.code}
                </div>
                {s.description && (
                  <p className="text-sm text-muted-foreground">
                    {s.description}
                  </p>
                )}
                <Button
                  size="sm"
                  onClick={() => handleAdopt(s)}
                  disabled={adopting === s.id}
                >
                  {adopting === s.id ? "Adopting…" : "Adopt this subject"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
