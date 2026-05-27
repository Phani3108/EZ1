/**
 * Phase 18a — Curriculum upgrade preview.
 *
 * Shows the HoD exactly what the upcoming
 * `POST /curriculum/upgrade-subject` will do — which national units &
 * topics will be added, which existing local rows will be updated
 * (and on which fields), how many local custom rows will be left
 * untouched, and how many local-but-no-longer-in-national rows are
 * orphaned (preserved by us, may want manual archive).
 *
 * "Confirm upgrade" calls the existing POST endpoint and routes back
 * to `/curriculum`.
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  curriculumApi,
  type UpgradePreview,
} from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription, Badge,
} from "@eduzim/ui";

export default function CurriculumUpgradePreviewPage() {
  const params = useParams<{ subjectId: string }>();
  const router = useRouter();
  const subjectId = params?.subjectId;

  const [preview, setPreview] = useState<UpgradePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!subjectId) return;
    setLoading(true);
    curriculumApi
      .previewUpgrade(subjectId)
      .then((r) => setPreview(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  }, [subjectId]);

  const handleConfirm = async () => {
    if (!subjectId) return;
    setConfirming(true);
    try {
      await curriculumApi.upgradeSubject({ school_subject_id: subjectId });
      router.push("/curriculum");
    } catch (e: any) {
      setError(e?.detail ?? String(e));
      setConfirming(false);
    }
  };

  if (loading) {
    return <div className="h-64 animate-pulse rounded bg-muted" />;
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load preview</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!preview) return null;

  const totalChanges =
    preview.units_to_add.length +
    preview.units_to_update.length +
    preview.topics_to_add.length +
    preview.topics_to_update.length;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Curriculum upgrade preview</h1>
          <p className="text-sm text-muted-foreground">
            Review what the upgrade will change before committing. School-custom
            topics are always preserved.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Link href="/curriculum">Cancel</Link>
          </Button>
          {!preview.no_op && (
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {confirming ? "Upgrading..." : `Confirm upgrade (v${preview.from_version} → v${preview.to_version})`}
            </button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            Version
            <Badge variant="outline">v{preview.from_version}</Badge>
            <span className="text-muted-foreground">→</span>
            <Badge>v{preview.to_version}</Badge>
            {preview.no_op && (
              <span className="ml-2 text-xs text-muted-foreground">
                Already current — no changes pending.
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Counter label="Units to add" value={preview.units_to_add.length} />
          <Counter label="Units to update" value={preview.units_to_update.length} />
          <Counter label="Topics to add" value={preview.topics_to_add.length} />
          <Counter label="Topics to update" value={preview.topics_to_update.length} />
          <Counter
            label="Custom units preserved"
            value={preview.local_custom_units_preserved_count}
            muted
          />
          <Counter
            label="Custom topics preserved"
            value={preview.local_custom_topics_preserved_count}
            muted
          />
          <Counter
            label="Orphaned units (kept)"
            value={preview.local_nationally_orphaned_units_count}
            muted
          />
          <Counter
            label="Orphaned topics (kept)"
            value={preview.local_nationally_orphaned_topics_count}
            muted
          />
        </CardContent>
      </Card>

      {totalChanges === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Nothing to upgrade — local tree is in sync with national v{preview.to_version}.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <DiffList
            title="Units to add"
            empty="No new units in this version."
            items={preview.units_to_add.map((u) => ({
              key: u.national_unit_id,
              primary: u.name,
              secondary: `${u.code}${u.grade_level ? ` · ${u.grade_level}` : ""}`,
              tone: "add" as const,
            }))}
          />
          <DiffList
            title="Topics to add"
            empty="No new topics in this version."
            items={preview.topics_to_add.map((t) => ({
              key: t.national_topic_id,
              primary: t.name,
              secondary: t.code,
              tone: "add" as const,
            }))}
          />
          <DiffList
            title="Units to update"
            empty="No unit metadata has drifted."
            items={preview.units_to_update.map((u) => ({
              key: u.local_unit_id,
              primary: u.code,
              secondary: `Changed: ${u.changed_fields.join(", ")}`,
              tone: "update" as const,
            }))}
          />
          <DiffList
            title="Topics to update"
            empty="No topic metadata has drifted."
            items={preview.topics_to_update.map((t) => ({
              key: t.local_topic_id,
              primary: t.code,
              secondary: `Changed: ${t.changed_fields.join(", ")}`,
              tone: "update" as const,
            }))}
          />
        </div>
      )}

      {(preview.local_nationally_orphaned_units_count > 0 ||
        preview.local_nationally_orphaned_topics_count > 0) && (
        <Alert>
          <AlertTitle>Heads up — orphaned rows</AlertTitle>
          <AlertDescription>
            {preview.local_nationally_orphaned_units_count} unit(s) and{" "}
            {preview.local_nationally_orphaned_topics_count} topic(s) were on a
            previous national version but have been removed in v
            {preview.to_version}. They will be <strong>kept</strong> (no
            content is auto-deleted). Archive them manually if they are no
            longer relevant.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function Counter({
  label, value, muted,
}: { label: string; value: number; muted?: boolean }) {
  return (
    <div className={"rounded border p-3 " + (muted ? "bg-muted/30" : "")}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

interface DiffItem {
  key: string;
  primary: string;
  secondary: string;
  tone: "add" | "update";
}
function DiffList({
  title, empty, items,
}: { title: string; empty: string; items: DiffItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title} ({items.length})</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-xs text-muted-foreground">{empty}</div>
        ) : (
          <ul className="divide-y">
            {items.map((it) => (
              <li key={it.key} className="flex items-start justify-between py-2 gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{it.primary}</div>
                  <div className="text-xs text-muted-foreground truncate">{it.secondary}</div>
                </div>
                <Badge variant={it.tone === "add" ? "default" : "outline"}>
                  {it.tone === "add" ? "+ add" : "~ update"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
