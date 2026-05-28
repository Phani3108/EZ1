/**
 * Phase 15b — Setup wizard: school profile step.
 *
 * Lightweight pointer page. The full school-edit form lives at
 * /schools/[id]; this step ensures the admin has named the school
 * and set up at least one term.
 */
"use client";

import React from "react";
import { useSetup } from "../setup-context";
import { Card, CardHeader, CardTitle, CardContent, LinkButton, ChecklistItem } from "@eduzim/ui";

export default function SchoolProfileSetup() {
  const { status } = useSetup();
  if (!status) return null;

  const profileCheck = status.checklist.find((c) => c.step === "school_profile");
  const evidence = profileCheck?.evidence as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">School profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-muted-foreground">
            Confirm the school's name, address, term dates, and basic
            metadata before importing students.
          </div>
          <ChecklistItem
            status={profileCheck?.status ?? "unknown"}
            label="School profile complete"
            evidence={
              evidence
                ? `Name: ${evidence.name ?? "—"} · ${evidence.term_count ?? 0} term(s)`
                : "—"
            }
          />
          <LinkButton href="/schools">Edit school details →</LinkButton>
        </CardContent>
      </Card>
    </div>
  );
}
