/**
 * FlagHeader — sovereign theme
 * Page-level header with a Zimbabwe flag-stripe rule above the title row.
 * Used by admin-web and ministry-web to set the "country-first" tone.
 *
 * Visual: thin 4-stripe gradient bar (green / yellow / red / black),
 * then a row with optional coat-of-arms slot + title + actions.
 */
import React from "react";
import { cn } from "../../lib/utils";

export interface FlagHeaderProps {
  title: string;
  subtitle?: string;
  emblem?: React.ReactNode;
  actions?: React.ReactNode;
  /** Use "thick" for top-of-page hero headers, "thin" inline section heads. */
  stripe?: "thin" | "thick";
  className?: string;
}

export function FlagHeader({
  title,
  subtitle,
  emblem,
  actions,
  stripe = "thick",
  className,
}: FlagHeaderProps) {
  return (
    <header
      className={cn("w-full border-b border-border bg-card", className)}
      role="banner"
    >
      <div
        aria-hidden="true"
        className={cn(
          "w-full",
          stripe === "thick" ? "h-2" : "h-1",
        )}
        style={{ background: "var(--zim-flag-gradient)" }}
      />
      <div className="flex items-center gap-4 px-6 py-4 lg:px-8">
        {emblem ? (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center">
            {emblem}
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {subtitle ? (
            <p className="truncate text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}
