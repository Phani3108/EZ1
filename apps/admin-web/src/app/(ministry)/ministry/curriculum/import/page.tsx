/**
 * Phase 17c — Ministry National Curriculum bulk-upload UI.
 *
 * Drag-drop a CSV; calls POST /api/v1/ministry/bulk/national-curriculum
 * with `dry_run=true` first to show a preview, then `dry_run=false`
 * on confirm. Provisioner / EduZimOps only — the gateway enforces
 * `school:create`.
 */
"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@eduzim/auth";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, LinkButton, BulkUpload, Alert, AlertTitle, AlertDescription,
} from "@eduzim/ui";

interface ImportResult {
  total_rows: number;
  subjects_created: number;
  units_created: number;
  units_updated: number;
  topics_created: number;
  topics_updated: number;
  skipped: number;
  errors: Array<{ row?: number; error: string }>;
}

export default function MinistryCurriculumImportPage() {
  const { hasPermission } = useAuth();
  const canImport = hasPermission("school:create");

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState<ImportResult | null>(null);
  const [commit, setCommit] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runImport = async (dry: boolean) => {
    if (!csvFile) return;
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", csvFile);
    try {
      const base =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const url = `${base}/api/v1/ministry/bulk/national-curriculum?dry_run=${dry}`;
      const r = await fetch(url, {
        method: "POST",
        body: fd,
        credentials: "include",
      });
      const j = await r.json();
      if (!r.ok) {
        setError(j?.error?.message ?? "Upload failed");
      } else {
        if (dry) {
          setDryRun(j.data as ImportResult);
        } else {
          setCommit(j.data as ImportResult);
          setDryRun(null);
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!canImport) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          You need the <code>school:create</code> permission to import
          national curriculum data. Ask EduZim Operations or your
          Ministry+Provisioner contact.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Import National Curriculum (CSV)</h1>
        <p className="text-sm text-muted-foreground">
          Bulk-create or update ZIMSEC subjects, units, and topics from
          a single CSV. Idempotent — re-running with the same file is
          safe.{" "}
          <Link
            href="/api/v1/templates/national-curriculum.csv"
            className="text-primary hover:underline"
          >
            Download example template
          </Link>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">1. Upload</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <BulkUpload
            accept=".csv"
            onUpload={(r) => {
              setCsvFile(r.file);
              setDryRun(null);
              setCommit(null);
            }}
            hint="Drop or pick a .csv with subject_code, unit_code, topic_code, … columns."
          />
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Upload failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => runImport(true)}
              disabled={!csvFile || busy}
            >
              {busy ? "Validating…" : "Validate (dry run)"}
            </Button>
            <Button
              onClick={() => runImport(false)}
              disabled={!csvFile || busy}
            >
              {busy ? "Importing…" : "Commit"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {dryRun && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">2. Dry-run preview</CardTitle>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertTitle>
                {dryRun.subjects_created} subject(s) ·{" "}
                {dryRun.units_created} new unit(s) ·{" "}
                {dryRun.topics_created} new topic(s) would be written
              </AlertTitle>
              <AlertDescription>
                Total rows: {dryRun.total_rows}. Skipped:{" "}
                {dryRun.skipped}.
                {dryRun.errors.length > 0 && (
                  <ul className="mt-2 list-disc pl-5 text-xs">
                    {dryRun.errors.slice(0, 5).map((e, i) => (
                      <li key={i}>
                        Row {e.row ?? "?"}: {e.error}
                      </li>
                    ))}
                    {dryRun.errors.length > 5 && (
                      <li>… and {dryRun.errors.length - 5} more</li>
                    )}
                  </ul>
                )}
              </AlertDescription>
            </Alert>
            <p className="mt-3 text-xs text-muted-foreground">
              Click "Commit" above to actually write the rows. New
              subjects land in draft state — publish them separately
              from the curriculum overview.
            </p>
          </CardContent>
        </Card>
      )}

      {commit && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Imported</CardTitle>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertTitle>Saved</AlertTitle>
              <AlertDescription>
                {commit.subjects_created} subject(s) created ·{" "}
                {commit.units_created + commit.units_updated} unit(s)
                created/updated ·{" "}
                {commit.topics_created + commit.topics_updated} topic(s)
                created/updated.
              </AlertDescription>
            </Alert>
            <div className="mt-3">
              <LinkButton variant="outline" href="/ministry/curriculum">
                Back to curriculum overview
              </LinkButton>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
