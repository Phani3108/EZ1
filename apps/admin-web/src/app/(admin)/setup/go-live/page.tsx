/**
 * Phase 15b — Setup wizard: Go Live.
 *
 * Big green button. Disabled until every checklist item is green.
 * Flips School.is_live + audit-logs the moment.
 */
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useSetup } from "../setup-context";
import { onboardingApi } from "@/lib/onboarding-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription, ReadinessBar, ChecklistItem,
} from "@eduzim/ui";

export default function GoLiveSetup() {
  const { status, refresh } = useSetup();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!status) return null;

  const handleGoLive = async () => {
    setBusy(true);
    setError(null);
    try {
      await onboardingApi.goLive();
      refresh();
      router.push("/setup");
    } catch (e: any) {
      setError(e?.error?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  if (status.school_is_live) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">School is live 🎉</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground">
            Went live at{" "}
            {status.went_live_at
              ? new Date(status.went_live_at).toLocaleString()
              : "—"}
            .
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <ReadinessBar
        statuses={status.checklist.map((c) => c.status)}
        label="Pre-flight check"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Checklist</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {status.checklist.map((c) => (
            <ChecklistItem
              key={c.step}
              status={c.status}
              label={c.label}
            />
          ))}
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not go live</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="text-sm text-muted-foreground">
            Going live opens the school to parents and teachers. Until you
            click this, parent and teacher logins still work but they see a
            "School is still being set up" banner.
          </div>
          <Button
            size="lg"
            disabled={!status.go_live_eligible || busy}
            onClick={handleGoLive}
          >
            {busy ? "Going live…" : "Go live"}
          </Button>
          {!status.go_live_eligible && (
            <div className="text-xs text-amber-700">
              Still blocked on:{" "}
              {status.go_live_blockers.join(", ")}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
