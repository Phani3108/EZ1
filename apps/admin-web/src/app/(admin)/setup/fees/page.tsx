/**
 * Phase 15b — Setup wizard: fee structure step.
 *
 * CSV upload via /api/v1/bulk/fee-structures (finance service).
 */
"use client";

import React, { useState } from "react";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, BulkUpload, Alert, AlertTitle, AlertDescription,
} from "@eduzim/ui";

interface ImportResult {
  total_rows: number;
  structures_created: number;
  structures_updated: number;
  items_written: number;
  skipped: number;
  errors: any[];
}

export default function FeesSetup() {
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
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const url = `${base}/api/v1/bulk/fee-structures?dry_run=${dry}`;
      const r = await fetch(url, { method: "POST", body: fd, credentials: "include" });
      const j = await r.json();
      if (!r.ok) {
        setError(j?.error?.message ?? "Upload failed");
      } else {
        if (dry) setDryRun(j.data);
        else { setCommit(j.data); setDryRun(null); }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Fee structures</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm text-muted-foreground">
          Upload your fee structures as CSV. One row per line item.{" "}
          <a
            href="/api/v1/templates/fee-structures.csv"
            className="text-primary hover:underline"
          >
            Download example
          </a>
          .
        </div>
        <BulkUpload
          accept=".csv"
          onUpload={(r) => { setCsvFile(r.file); setDryRun(null); setCommit(null); }}
          hint="Drop or pick a .csv with your fee structures."
        />
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Upload failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => runImport(true)} disabled={!csvFile || busy}>
            {busy ? "Validating…" : "Validate (dry run)"}
          </Button>
          <Button onClick={() => runImport(false)} disabled={!csvFile || busy}>
            {busy ? "Importing…" : "Import"}
          </Button>
        </div>
        {dryRun && (
          <Alert>
            <AlertTitle>Dry run</AlertTitle>
            <AlertDescription>
              {dryRun.structures_created} structures · {dryRun.items_written} items
            </AlertDescription>
          </Alert>
        )}
        {commit && (
          <Alert>
            <AlertTitle>Imported</AlertTitle>
            <AlertDescription>
              {commit.structures_created + commit.structures_updated} structure(s)
              · {commit.items_written} item(s)
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
