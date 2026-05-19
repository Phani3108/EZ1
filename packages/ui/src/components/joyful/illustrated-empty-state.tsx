/**
 * IllustratedEmptyState — joyful theme
 * Friendly empty / error / offline state for parent + student screens.
 * Always pair the illustration with text + an action.
 */
import React from "react";
import { cn } from "../../lib/utils";

export interface IllustratedEmptyStateProps {
  title: string;
  message?: string;
  illustration?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function IllustratedEmptyState({
  title,
  message,
  illustration,
  action,
  className,
}: IllustratedEmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center",
        className,
      )}
      role="status"
    >
      {illustration ? (
        <div aria-hidden="true" className="h-32 w-32">
          {illustration}
        </div>
      ) : null}
      <div>
        <h3 className="text-xl font-extrabold tracking-tight text-foreground">
          {title}
        </h3>
        {message ? (
          <p className="mt-1 text-sm text-foreground/70">{message}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
