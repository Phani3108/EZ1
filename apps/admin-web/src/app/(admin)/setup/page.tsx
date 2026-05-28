/**
 * Phase 15b — Setup landing.
 *
 * Shows the readiness bar + the full checklist + a "Continue setup"
 * CTA pointing at the next non-green step.
 */
"use client";

import React from "react";
import { useSetup } from "./setup-context";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, LinkButton, ReadinessBar, ChecklistItem,
} from "@eduzim/ui";

const STEP_HREF: Record<string, string> = {
  school_profile: "/setup/school",
  classes: "/setup/classes-subjects",
  subjects: "/setup/classes-subjects",
  teachers: "/setup/teachers",
  students: "/setup/students",
  parents_invited: "/setup/parents",
  first_attendance: "/setup/go-live",
};

function _evidenceText(step: string, evidence: Record<string, unknown>): string {
  const v = (k: string) => (evidence as any)[k];
  switch (step) {
    case "school_profile":
      return v("name") ? `${v("name")} · ${v("term_count") ?? 0} terms` : "—";
    case "classes":
      return `${v("count") ?? 0} class(es)`;
    case "subjects":
      return `${v("count") ?? 0} subject(s)`;
    case "teachers":
      return `${v("assigned") ?? 0} assigned · ${v("invited") ?? 0} invited`;
    case "students":
      return `${v("count") ?? 0} student(s)`;
    case "parents_invited":
      return `${v("dispatched") ?? 0} of ${v("invited") ?? 0} invitations dispatched`;
    case "first_attendance":
      return v("count") ? `${v("count")} records` : "Not yet taken";
    default:
      return "";
  }
}

export default function SetupLanding() {
  const { status } = useSetup();
  if (!status) return null;

  const nextStep = status.checklist.find((c) => c.status !== "green");

  return (
    <div className="space-y-6">
      <ReadinessBar
        statuses={status.checklist.map((c) => c.status)}
        label="Overall setup progress"
      />

      {status.school_is_live ? (
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
              . Parents and teachers can now log in.
            </div>
          </CardContent>
        </Card>
      ) : nextStep ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Next up</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-2 text-sm text-muted-foreground">
              {nextStep.label} — {nextStep.status === "amber" ? "in progress" : "not started"}.
            </div>
            <LinkButton href={STEP_HREF[nextStep.step] ?? "/setup/school"}>
              Continue with {nextStep.label}
            </LinkButton>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">All set</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-2 text-sm text-muted-foreground">
              Every check is green. You're ready to go live.
            </div>
            <LinkButton href="/setup/go-live">Go live →</LinkButton>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Setup checklist</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {status.checklist.map((c) => (
              <ChecklistItem
                key={c.step}
                status={c.status}
                label={c.label}
                evidence={_evidenceText(c.step, c.evidence)}
                href={STEP_HREF[c.step] ?? "#"}
                actionLabel="Open"
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
