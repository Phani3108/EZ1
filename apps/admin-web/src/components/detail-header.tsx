/**
 * DetailHeader — consistent header for 360° detail pages (Student, Parent, Teacher).
 * Shows name, identifiers, status badge, and right-side actions.
 */

"use client";

import React from "react";
import { Badge, Button } from "@eduzim/ui";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

interface DetailHeaderProps {
  backHref: string;
  backLabel?: string;
  title: string;
  subtitle?: string;
  badges?: { label: string; variant?: "default" | "secondary" | "destructive" | "outline" }[];
  children?: React.ReactNode; // right-side actions
}

export function DetailHeader({
  backHref,
  backLabel = "Back",
  title,
  subtitle,
  badges,
  children,
}: DetailHeaderProps) {
  const router = useRouter();

  return (
    <div className="space-y-4">
      <button
        onClick={() => router.push(backHref)}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        {backLabel}
      </button>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && (
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
          {badges?.map((b, i) => (
            <Badge key={i} variant={b.variant}>
              {b.label}
            </Badge>
          ))}
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>
    </div>
  );
}
