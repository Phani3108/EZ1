/**
 * Phase 15b — Setup wizard: review teacher-submitted drafts.
 *
 * Admins approve / reject each draft. Approve creates the real Student
 * row + spawns a ParentDraft (auto-invited).
 */
"use client";

import React, { useEffect, useState } from "react";
import { useSetup } from "../setup-context";
import { onboardingApi, type StudentDraftRow } from "@/lib/onboarding-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription, Input,
} from "@eduzim/ui";

export default function DraftsSetup() {
  const { refresh } = useSetup();
  const [drafts, setDrafts] = useState<StudentDraftRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const load = () => {
    onboardingApi
      .listStudentDrafts("pending")
      .then((r) => setDrafts(r.data))
      .catch(() => {});
  };
  useEffect(load, []);

  const handleApprove = async (id: string, code: string) => {
    setError(null);
    try {
      await onboardingApi.approveStudentDraft(id, { student_code: code });
      load();
      refresh();
    } catch (e: any) {
      setError(e?.error?.message ?? String(e));
    }
  };

  const handleReject = async (id: string) => {
    if (!reason.trim()) return;
    setError(null);
    try {
      await onboardingApi.rejectStudentDraft(id, reason.trim());
      setRejecting(null);
      setReason("");
      load();
      refresh();
    } catch (e: any) {
      setError(e?.error?.message ?? String(e));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pending student drafts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm text-muted-foreground">
          Teachers submitted these on the fly. Approve to publish them into
          the live roster.
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Action failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {drafts.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            No pending drafts.
          </div>
        ) : (
          <ul className="divide-y border rounded-md">
            {drafts.map((d) => (
              <li key={d.id} className="p-3 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">
                      {d.first_name} {d.last_name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Submitted{" "}
                      {d.submitted_at
                        ? new Date(d.submitted_at).toLocaleString()
                        : "—"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Student code"
                      defaultValue={d.student_code ?? ""}
                      onBlur={(e) => {
                        // No-op; we read value at approve time.
                      }}
                      id={`code-${d.id}`}
                      className="w-32"
                    />
                    <Button
                      size="sm"
                      onClick={() => {
                        const el = document.getElementById(
                          `code-${d.id}`,
                        ) as HTMLInputElement | null;
                        handleApprove(d.id, el?.value || "");
                      }}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setRejecting(d.id);
                        setReason("");
                      }}
                    >
                      Reject
                    </Button>
                  </div>
                </div>
                {rejecting === d.id && (
                  <div className="flex items-center gap-2">
                    <Input
                      autoFocus
                      placeholder="Reason"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleReject(d.id)}
                    >
                      Confirm reject
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setRejecting(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
