/**
 * Admin Dashboard — sovereign theme
 * ==================================
 * Ministry-grade overview. Each KPI uses MinistryStatCard with a flag-coloured
 * accent and an audit/source footnote so every number is defensible.
 * ProvinceMap surfaces national coverage when reporting-service provides
 * per-province rollups; renders neutral until then.
 */

"use client";

import React, { useEffect, useState } from "react";
import { reports } from "@/lib/api";
import {
  FlagHeader,
  MinistryStatCard,
  OfficialBadge,
  ProvinceMap,
} from "@eduzim/ui";
import { ApiError, type DashboardData } from "@eduzim/api-client";
import {
  Users,
  GraduationCap,
  ClipboardCheck,
  DollarSign,
  Megaphone,
  AlertTriangle,
} from "lucide-react";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reports
      .dashboard()
      .then(({ data }) => setData(data))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Failed to load dashboard"),
      )
      .finally(() => setLoading(false));
  }, []);

  const generatedAt = new Date().toLocaleString("en-ZW", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="space-y-6">
      <FlagHeader
        title="National Education Dashboard"
        subtitle={`Republic of Zimbabwe · MoPSE · Generated ${generatedAt}`}
        emblem={
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="/national/coat-of-arms.svg"
            alt="Zimbabwe coat of arms"
            className="h-10 w-10"
          />
        }
        actions={
          <>
            <OfficialBadge variant="mopse" label="MoPSE" />
            <OfficialBadge variant="vision2030" label="Vision 2030" />
          </>
        }
        stripe="thick"
        className="rounded-lg"
      />

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertTriangle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* KPI grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border bg-muted/40"
            />
          ))
        ) : (
          <>
            <MinistryStatCard
              label="Total Students"
              value={(data?.total_students ?? 0).toLocaleString()}
              icon={Users}
              accent="green"
              source="Source: student-service · live"
            />
            <MinistryStatCard
              label="Total Classes"
              value={(data?.total_classes ?? 0).toLocaleString()}
              icon={GraduationCap}
              accent="gold"
              source="Source: school-service · live"
            />
            <MinistryStatCard
              label="Attendance Rate"
              value={`${((data?.attendance_rate ?? 0) * 100).toFixed(1)}%`}
              icon={ClipboardCheck}
              accent="green"
              source="Source: attendance-service · last 30 days"
            />
            <MinistryStatCard
              label="Revenue (term)"
              value={`$${(data?.total_revenue ?? 0).toLocaleString()}`}
              icon={DollarSign}
              accent="green"
              source="Source: fees-service · current term"
            />
            <MinistryStatCard
              label="Outstanding Fees"
              value={`$${(data?.total_outstanding ?? 0).toLocaleString()}`}
              icon={DollarSign}
              accent="red"
              source="Source: fees-service · live"
            />
            <MinistryStatCard
              label="Announcements"
              value={(data?.announcements_count ?? 0).toLocaleString()}
              icon={Megaphone}
              accent="black"
              source="Source: communication-service · 30-day rolling"
            />
          </>
        )}
      </div>

      {/* National coverage map */}
      <section className="rounded-lg border bg-card p-6 shadow-card zim-watermark">
        <h2 className="text-lg font-semibold tracking-tight">
          Provincial Coverage
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Distribution of schools across Zimbabwe's 10 provinces. Click a
          province for the detailed view.
        </p>
        <div className="mt-4">
          <ProvinceMap ariaLabel="Schools by province (placeholder data)" />
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          Source: school-service · provincial rollup pending API release.
        </p>
      </section>
    </div>
  );
}
