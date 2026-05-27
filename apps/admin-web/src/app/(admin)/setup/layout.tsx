/**
 * Phase 15b — Setup wizard layout.
 *
 * Two-pane shell: a vertical Stepper on the left (with green/amber/red
 * status pulled from the readiness API) and the active step's content
 * on the right.
 *
 * Live status is fetched once per layout mount via SWR-like polling.
 * (No SWR dependency — we use a tiny useEffect-based hook to keep the
 * admin-web dependency surface small.)
 */
"use client";

import React, { useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { onboardingApi, type OnboardingStatus } from "@/lib/onboarding-api";
import { Stepper, type StepperStep, type ChecklistStatus } from "@eduzim/ui";
import { SetupContext } from "./setup-context";

const WIZARD_STEPS: { step: string; label: string; href: string }[] = [
  { step: "school_profile", label: "School profile", href: "/setup/school" },
  { step: "classes", label: "Classes", href: "/setup/classes-subjects" },
  { step: "subjects", label: "Subjects", href: "/setup/classes-subjects" },
  { step: "teachers", label: "Teachers", href: "/setup/teachers" },
  { step: "students", label: "Students", href: "/setup/students" },
  { step: "parents_invited", label: "Parents", href: "/setup/parents" },
  { step: "first_attendance", label: "First attendance", href: "/setup/go-live" },
];

// Step IDs that share a page. The pathname → step lookup uses href.
const PATH_TO_STEP: Record<string, string> = {
  "/setup": "school_profile",
  "/setup/school": "school_profile",
  "/setup/classes-subjects": "classes",
  "/setup/teachers": "teachers",
  "/setup/students": "students",
  "/setup/parents": "parents_invited",
  "/setup/drafts": "students",
  "/setup/fees": "school_profile",
  "/setup/go-live": "first_attendance",
};

export default function SetupLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);

  const refresh = useCallback(() => {
    onboardingApi
      .status()
      .then((r) => setStatus(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15_000);
    return () => clearInterval(t);
  }, [refresh]);

  const stepStatuses = new Map<string, ChecklistStatus>(
    (status?.checklist ?? []).map((c) => [c.step, c.status]),
  );
  const stepEvidence = new Map<string, Record<string, unknown>>(
    (status?.checklist ?? []).map((c) => [c.step, c.evidence]),
  );

  const steps: StepperStep[] = WIZARD_STEPS.map((w) => ({
    id: w.step,
    label: w.label,
    href: w.href,
    status: (stepStatuses.get(w.step) ?? "unknown") as ChecklistStatus,
    subline: _sublineFor(w.step, stepEvidence.get(w.step) ?? {}),
  }));

  const activeId = PATH_TO_STEP[pathname] ?? "school_profile";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Setup your school</h1>
        <p className="text-sm text-muted-foreground">
          Step by step. We'll take you live once every check is green.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="lg:sticky lg:top-4 lg:self-start">
          <Stepper steps={steps} activeId={activeId} />
        </aside>
        <div className="min-w-0">
          {status && (
            <SetupContext.Provider value={{ status, refresh }}>
              {children}
            </SetupContext.Provider>
          )}
          {!status && (
            <div className="h-64 animate-pulse rounded-md bg-muted" />
          )}
        </div>
      </div>
    </div>
  );
}

function _sublineFor(step: string, evidence: Record<string, unknown>): string | undefined {
  const v = (k: string) => (evidence as any)[k];
  switch (step) {
    case "school_profile":
      if (v("term_count")) return `${v("term_count")} term(s)`;
      return undefined;
    case "classes":
      if (v("count") != null) return `${v("count")} class(es)`;
      return undefined;
    case "subjects":
      if (v("count") != null) return `${v("count")} subject(s)`;
      return undefined;
    case "teachers":
      if (v("assigned") != null) return `${v("assigned")} assigned · ${v("invited") ?? 0} invited`;
      return undefined;
    case "students":
      if (v("count") != null) return `${v("count")} student(s)`;
      return undefined;
    case "parents_invited":
      if (v("invited") != null) return `${v("dispatched") ?? 0} of ${v("invited")} dispatched`;
      return undefined;
    case "first_attendance":
      if (v("count") != null && (v("count") as number) > 0) return `${v("count")} records`;
      return undefined;
    default:
      return undefined;
  }
}

