/**
 * FriendlyError — universal error display
 * ========================================
 * Used by every surface that talks to a backend. Renders:
 *   • Clear icon + title + plain-language body
 *   • Suggested fix line ("what should I do now?")
 *   • Retry button (only when retryable)
 *   • Collapsible "Technical details" disclosure (status, request_id, raw)
 *
 * Variants:
 *   inline  — full-width banner inside a section (default)
 *   card    — standalone empty-state-style card
 *   toast   — compact horizontal banner for the top of the screen
 *
 * Theming: uses semantic tokens only so it adapts to joyful / focus /
 * sovereign without code changes.
 */
"use client";

import * as React from "react";
import { cn } from "../lib/utils";
import {
  classifyError,
  ERROR_CATALOG,
  type FriendlyErrorCode,
  type FriendlyErrorEntry,
} from "../lib/error-catalog";

function stringifyRaw(raw: unknown): string {
  if (raw === null || raw === undefined) return "";
  if (typeof raw === "string") return raw;
  if (raw instanceof Error) return raw.message;
  if (typeof raw === "object") {
    try {
      return JSON.stringify(raw, null, 2);
    } catch {
      return String(raw);
    }
  }
  return String(raw);
}

export interface FriendlyErrorProps {
  /**
   * Either provide an explicit `code`, or pass the raw `error` object and
   * let `classifyError` figure it out.
   */
  code?: FriendlyErrorCode;
  error?: unknown;
  /** Override the catalog text per usage site. */
  override?: Partial<FriendlyErrorEntry>;
  /** Called when the user taps Retry. If absent, retry button is hidden. */
  onRetry?: () => void;
  /** Optional secondary action, e.g. "View payments" link. */
  secondaryAction?: React.ReactNode;
  /** Raw technical info to expose under "Show technical details". */
  technical?: {
    status?: number;
    requestId?: string;
    service?: string;
    raw?: unknown;
  };
  variant?: "inline" | "card" | "toast";
  className?: string;
}

export function FriendlyError({
  code,
  error,
  override,
  onRetry,
  secondaryAction,
  technical,
  variant = "inline",
  className,
}: FriendlyErrorProps) {
  const resolvedCode: FriendlyErrorCode =
    code ?? (error !== undefined ? classifyError(error) : "UNKNOWN");
  const base = ERROR_CATALOG[resolvedCode];
  const entry = { ...base, ...override };
  const [showTech, setShowTech] = React.useState(false);

  const container =
    variant === "card"
      ? "rounded-2xl border border-border bg-card p-6 shadow-card"
      : variant === "toast"
        ? "rounded-lg border border-border bg-card px-4 py-3"
        : "rounded-lg border border-border bg-card p-4";

  const iconSize = variant === "card" ? "h-10 w-10" : "h-6 w-6";

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(container, "flex gap-3", className)}
    >
      <div className={cn("shrink-0", iconSize)} aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-full w-full text-destructive"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="13" />
          <line x1="12" y1="16" x2="12" y2="16.01" />
        </svg>
      </div>

      <div className="min-w-0 flex-1">
        <p className="font-semibold text-foreground">{entry.title}</p>
        {entry.body && (
          <p className="mt-1 text-sm text-muted-foreground">{entry.body}</p>
        )}
        {entry.fix && (
          <p className="mt-2 text-sm font-medium text-foreground">
            <span aria-hidden="true">→ </span>
            {entry.fix}
          </p>
        )}

        {(onRetry && entry.retryable) || secondaryAction ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {onRetry && entry.retryable ? (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
              >
                {/* refresh icon */}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <polyline points="23 4 23 10 17 10" />
                  <polyline points="1 20 1 14 7 14" />
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                Retry
              </button>
            ) : null}
            {secondaryAction}
          </div>
        ) : null}

        {technical &&
        (technical.status ||
          technical.requestId ||
          technical.service ||
          technical.raw) ? (
          <details
            className="mt-3 group"
            onToggle={(e) =>
              setShowTech((e.currentTarget as HTMLDetailsElement).open)
            }
          >
            <summary className="cursor-pointer select-none text-xs font-medium text-muted-foreground underline-offset-2 hover:underline">
              {showTech ? "Hide" : "Show"} technical details
            </summary>
            <dl className="mt-2 space-y-1 rounded-md bg-muted/40 p-3 text-xs font-mono text-muted-foreground">
              {technical.service ? (
                <div className="flex gap-2">
                  <dt className="shrink-0 w-24 text-muted-foreground/70">
                    Service
                  </dt>
                  <dd className="break-all">{technical.service}</dd>
                </div>
              ) : null}
              {technical.status !== undefined ? (
                <div className="flex gap-2">
                  <dt className="shrink-0 w-24 text-muted-foreground/70">
                    Status
                  </dt>
                  <dd>{technical.status}</dd>
                </div>
              ) : null}
              {technical.requestId ? (
                <div className="flex gap-2">
                  <dt className="shrink-0 w-24 text-muted-foreground/70">
                    Request ID
                  </dt>
                  <dd className="break-all">{technical.requestId}</dd>
                </div>
              ) : null}
              {technical.raw ? (
                <div className="flex gap-2">
                  <dt className="shrink-0 w-24 text-muted-foreground/70">
                    Message
                  </dt>
                  <dd className="break-all whitespace-pre-wrap">
                    {stringifyRaw(technical.raw)}
                  </dd>
                </div>
              ) : null}
            </dl>
          </details>
        ) : null}
      </div>
    </div>
  );
}
