/**
 * SectionCard — elevated card for grouping related content within a page.
 * Uses the design system card shadow and radius.
 */

import React from "react";
import { cn } from "../lib/utils";

interface SectionCardProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  padding?: "default" | "compact" | "none";
  action?: React.ReactNode;
}

export function SectionCard({
  title,
  description,
  children,
  className,
  padding = "default",
  action,
}: SectionCardProps) {
  const padClass =
    padding === "default" ? "p-6" : padding === "compact" ? "p-4" : "";

  return (
    <div
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-card",
        className
      )}
    >
      {(title || action) && (
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            {title && (
              <h3 className="text-[15px] font-semibold leading-none">
                {title}
              </h3>
            )}
            {description && (
              <p className="mt-1 text-[13px] text-muted-foreground">
                {description}
              </p>
            )}
          </div>
          {action}
        </div>
      )}
      <div className={padClass}>{children}</div>
    </div>
  );
}
