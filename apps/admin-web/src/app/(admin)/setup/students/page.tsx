/**
 * Phase 15b — Setup wizard: students step.
 *
 * Drag-drop CSV upload + dry-run preview → commit. After commit:
 * surfaces auto-detected parent invites with "Send all" CTA.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useSetup } from "../setup-context";
import { onboardingApi, type InviteRow } from "@/lib/onboarding-api";
import { api } from "@/lib/api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, BulkUpload, Alert, AlertTitle, AlertDescription,
  InvitationStatusPill,
} from "@eduzim/ui";

interface ImportResult {
  total: number;
  created: number;
  skipped: number;
  errors: Array<{ row?: number; error: string; field?: string }>;
}

export default function StudentsSetup() {
  const { refresh } = useSetup();
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState<ImportResult | null>(null);
  const [commit, setCommit] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parentInvites, setParentInvites] = useState<InviteRow[]>([]);

  const loadInvites = () => {
    onboardingApi
      .listInviteRequests({ role: "Parent" })
      .then((r) => setParentInvites(r.data))
      .catch(() => {});
  };

  useEffect(loadInvites, []);

  const runImport = async (dry: boolean) => {
    if (!csvFile) return;
    setBusy(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", csvFile);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const url = `${base}/api/v1/students/import?dry_run=${dry}`;
      const r = await fetch(url, {
        method: "POST",
        body: fd,
        credentials: "include",
      });
      const j = await r.json();
      if (!r.ok) {
        setError(j?.error?.message ?? "Upload failed");
      } else {
        if (dry) setDryRun(j.data as ImportResult);
        else {
          setCommit(j.data as ImportResult);
          setDryRun(null);
          refresh();
          loadInvites();
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Import students</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-muted-foreground">
            Upload a CSV with your students. Include parent contact info to
            auto-queue parent activation invites.{" "}
            <a
              href="/api/v1/templates/students.csv"
              className="text-primary hover:underline"
            >
              Download example
            </a>
            .
          </div>
          <BulkUpload
            accept=".csv"
            onUpload={(r) => { setCsvFile(r.file); setDryRun(null); setCommit(null); }}
            hint="Drop or pick a .csv with your students."
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
              {busy ? "Importing…" : "Import"}
            </Button>
          </div>

          {dryRun && (
            <Alert>
              <AlertTitle>Dry run</AlertTitle>
              <AlertDescription>
                {dryRun.created} would be created · {dryRun.skipped} skipped
                {dryRun.errors.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-xs">
                    {dryRun.errors.slice(0, 5).map((e, i) => (
                      <li key={i}>
                        Row {e.row ?? "?"}: {e.error}
                        {e.field ? ` (${e.field})` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </AlertDescription>
            </Alert>
          )}
          {commit && (
            <Alert>
              <AlertTitle>Imported</AlertTitle>
              <AlertDescription>
                {commit.created} student(s) created · {commit.skipped} skipped
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Parent invites queued from your imports
          </CardTitle>
        </CardHeader>
        <CardContent>
          {parentInvites.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No parent invites queued yet. Add parent_phone or parent_email
              to your CSV rows, then re-upload.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">Parent</th>
                    <th className="py-2 pr-4">Contact</th>
                    <th className="py-2 pr-4">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {parentInvites.map((p) => (
                    <tr key={p.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{p.full_name}</td>
                      <td className="py-2 pr-4 text-xs">
                        {p.contact_phone || p.contact_email || "—"}
                      </td>
                      <td className="py-2 pr-4">
                        <InvitationStatusPill
                          status={
                            p.request_status === "dispatched"
                              ? "sent"
                              : p.request_status === "failed"
                                ? "failed"
                                : "queued"
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
