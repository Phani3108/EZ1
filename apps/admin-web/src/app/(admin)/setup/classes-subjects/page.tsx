/**
 * Phase 15b — Setup wizard: classes + subjects step.
 *
 * Pointer page. Full forms live under /academics; this step ensures
 * at least one class + one subject exist before teacher imports.
 */
"use client";

import React from "react";
import Link from "next/link";
import { useSetup } from "../setup-context";
import { Card, CardHeader, CardTitle, CardContent, Button, ChecklistItem } from "@eduzim/ui";

export default function ClassesSubjectsSetup() {
  const { status } = useSetup();
  if (!status) return null;

  const classes = status.checklist.find((c) => c.step === "classes");
  const subjects = status.checklist.find((c) => c.step === "subjects");

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Classes & subjects</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ChecklistItem
            status={classes?.status ?? "unknown"}
            label="Classes created"
            evidence={`${(classes?.evidence as any)?.count ?? 0} class(es)`}
          />
          <ChecklistItem
            status={subjects?.status ?? "unknown"}
            label="Subjects defined"
            evidence={`${(subjects?.evidence as any)?.count ?? 0} subject(s)`}
          />
          <div className="pt-2 flex gap-3">
            <Button>
              <Link href="/academics">Manage classes →</Link>
            </Button>
            <Button variant="outline">
              <Link href="/academics">Manage subjects →</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
