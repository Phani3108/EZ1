/**
 * StatCard — compact metric card for dashboards and summaries.
 * Supports icon, label, value, and optional trend indicator.
 */

import React from "react";
import { cn } from "../lib/utils";
import { type LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: { value: string; positive?: boolean };
  className?: string;
}

export function StatCard({ label, value, icon: Icon, trend, className }: StatCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4 shadow-card",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </div>
      <p className="mt-2 text-2xl font-bold tracking-tight">{value}</p>
      {trend && (
        <p
          className={cn(
            "mt-1 text-[12px]",
            trend.positive ? "text-emerald-600" : "text-red-600"
          )}
        >
          {trend.value}
        </p>
      )}
    </div>
  );
}
