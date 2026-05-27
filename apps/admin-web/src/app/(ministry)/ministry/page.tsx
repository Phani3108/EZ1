/**
 * Ministry overview — Phase 14e.
 *
 * Single-page national snapshot. Loads the UNESCO export endpoint
 * (M-011) which already aggregates every top-level metric we want to
 * surface on the landing page. One backend call → 6 KPI cards.
 */

"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type UnescoExport } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";
import { AlertCircle } from "lucide-react";

export default function MinistryOverview() {
  const [data, setData] = useState<UnescoExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const year = new Date().getFullYear();
    ministryApi
      .unesco(year)
      .then(({ data }) => setData(data))
      .catch((e) => setError(String(e?.detail ?? e?.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        Loading national snapshot…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <div className="font-medium">Could not load Ministry snapshot</div>
          <div>{error}</div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const formatPct = (v: number | null) =>
    v == null ? "—" : `${(v * 100).toFixed(1)}%`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">National Overview</h1>
        <p className="text-sm text-muted-foreground">
          Reporting year {data.reporting_year} · generated{" "}
          {new Date(data.generated_at).toLocaleString()}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Kpi
          label="Schools"
          value={data.schools.total.toLocaleString()}
          subline={`${data.schools.by_type.PRIMARY ?? 0} primary · ${
            data.schools.by_type.SECONDARY ?? 0
          } secondary · ${data.schools.by_type.COMBINED ?? 0} combined`}
        />
        <Kpi
          label="Active students"
          value={data.enrolment.total_active.toLocaleString()}
        />
        <Kpi
          label="Teachers"
          value={data.teachers.total.toLocaleString()}
          subline="Distinct teachers with class assignments"
        />
        <Kpi
          label="Attendance rate"
          value={formatPct(data.attendance.national_rate_trailing_30d)}
          subline="Trailing 30 days"
        />
        <Kpi
          label="Drop-outs"
          value={data.dropouts.national_count.toLocaleString()}
          subline={`Rate: ${formatPct(data.dropouts.national_rate)}`}
        />
        <Kpi
          label="Provinces with data"
          value={data.enrolment.by_province.length.toString()}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enrolment by province</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4">Province</th>
                  <th className="py-2 pr-4 text-right">Active students</th>
                </tr>
              </thead>
              <tbody>
                {data.enrolment.by_province.map((row) => (
                  <tr
                    key={row.province_code ?? "unknown"}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-4 font-mono text-xs">
                      {row.province_code ?? "(unassigned)"}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {row.active.toLocaleString()}
                    </td>
                  </tr>
                ))}
                {data.enrolment.by_province.length === 0 && (
                  <tr>
                    <td
                      colSpan={2}
                      className="py-6 text-center text-muted-foreground"
                    >
                      No province-tagged schools yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({
  label,
  value,
  subline,
}: {
  label: string;
  value: string;
  subline?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className="mt-1 text-3xl font-bold">{value}</div>
        {subline && (
          <div className="mt-1 text-xs text-muted-foreground">{subline}</div>
        )}
      </CardContent>
    </Card>
  );
}
