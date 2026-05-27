/**
 * Phase 15b — Setup wizard: teachers step.
 *
 * CSV upload (delegates to /api/v1/bulk/teachers) + queue view.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useSetup } from "../setup-context";
import { onboardingApi, type InviteRow } from "@/lib/onboarding-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, BulkUpload, Alert, AlertTitle, AlertDescription,
  InvitationStatusPill,
} from "@eduzim/ui";

interface ImportResult {
  total: number;
  queued: number;
  skipped: number;
  errors: Array<{ row?: number; field?: string; error: string }>;
}

export default function TeachersSetup() {
  const { refresh } = useSetup();
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState<ImportResult | null>(null);
  const [commit, setCommit] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [teacherInvites, setTeacherInvites] = useState<InviteRow[]>([]);

  const loadInvites = () => {
    onboardingApi
      .listInviteRequests({ role: "Teacher" })
      .then((r) => setTeacherInvites(r.data))
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
      const url = `${base}/api/v1/bulk/teachers?dry_run=${dry}`;
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
          <CardTitle className="text-base">Invite teachers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-muted-foreground">
            Upload a CSV with one row per teacher (first_name, last_name,
            email, optional phone, optional class_codes).{" "}
            <a
              href="/api/v1/templates/teachers.csv"
              className="text-primary hover:underline"
            >
              Download example
            </a>
            .
          </div>
          <BulkUpload
            accept=".csv"
            onUpload={(r) => { setCsvFile(r.file); setDryRun(null); setCommit(null); }}
            hint="Drop or pick a .csv with your teachers."
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
              {busy ? "Importing…" : "Queue invites"}
            </Button>
          </div>
          {dryRun && (
            <Alert>
              <AlertTitle>Dry run</AlertTitle>
              <AlertDescription>
                {dryRun.queued} teacher(s) would be queued · {dryRun.skipped} skipped
              </AlertDescription>
            </Alert>
          )}
          {commit && (
            <Alert>
              <AlertTitle>Queued</AlertTitle>
              <AlertDescription>
                {commit.queued} teacher invite(s) queued · {commit.skipped} skipped
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Teacher invite queue</CardTitle>
        </CardHeader>
        <CardContent>
          {teacherInvites.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No teacher invites yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Email</th>
                    <th className="py-2 pr-4">Class codes</th>
                    <th className="py-2 pr-4">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {teacherInvites.map((t) => (
                    <tr key={t.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{t.full_name}</td>
                      <td className="py-2 pr-4 text-xs">{t.contact_email}</td>
                      <td className="py-2 pr-4 text-xs">{t.extra ?? "—"}</td>
                      <td className="py-2 pr-4">
                        <InvitationStatusPill
                          status={
                            t.request_status === "dispatched"
                              ? "sent"
                              : t.request_status === "failed"
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
