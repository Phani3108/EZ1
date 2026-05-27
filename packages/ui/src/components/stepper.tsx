/**
 * Phase 15b — Stepper
 *
 * Vertical list of wizard steps. Each step has a status (green/amber/red)
 * and is click-to-navigate. Designed for the (admin)/setup/** wizard
 * but reusable wherever a step-by-step flow is needed.
 */
"use client";

import * as React from "react";
import { cn } from "../lib/utils";
import type { ChecklistStatus } from "./checklist-item";

export interface StepperStep {
  id: string;
  label: string;
  status: ChecklistStatus;
  href: string;
  /** Optional short subline e.g. "5 invited, 0 activated". */
  subline?: string;
}

export interface StepperProps {
  steps: StepperStep[];
  /** id of the currently-active step. */
  activeId?: string;
  className?: string;
}

const STATUS_COLOR: Record<ChecklistStatus, string> = {
  green: "bg-green-500 border-green-600",
  amber: "bg-amber-500 border-amber-600",
  red: "bg-red-500 border-red-600",
  unknown: "bg-muted border-muted-foreground/30",
};

export function Stepper({ steps, activeId, className }: StepperProps) {
  return (
    <ol className={cn("space-y-1", className)}>
      {steps.map((step, idx) => {
        const isActive = step.id === activeId;
        return (
          <li key={step.id}>
            <a
              href={step.href}
              aria-current={isActive ? "step" : undefined}
              className={cn(
                "flex items-start gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 flex items-center justify-center text-[10px] font-bold text-white",
                  STATUS_COLOR[step.status],
                )}
              >
                {step.status === "green" ? "✓" : (idx + 1)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block leading-tight">{step.label}</span>
                {step.subline && (
                  <span className="block text-xs text-muted-foreground mt-0.5">
                    {step.subline}
                  </span>
                )}
              </span>
            </a>
          </li>
        );
      })}
    </ol>
  );
}
