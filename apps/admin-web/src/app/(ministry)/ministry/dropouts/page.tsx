/**
 * Ministry — Drop-out heatmap by district.
 *
 * Uses the lazy-loaded ECharts Heatmap (DEC-011 / ADR 011) so the
 * ECharts bundle is only fetched when the user navigates here.
 */

"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  ministryApi,
  type DropoutScopeRow,
} from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent, BarChart } from "@eduzim/ui";

export default function MinistryDropoutsPage() {
  const [rows, setRows] = useState<DropoutScopeRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ministryApi
      .dropouts("district")
      .then((r) => setRows(r.data as DropoutScopeRow[]))
      .finally(() => setLoading(false));
  }, []);

  // Bar chart input: one bar per district with the dropout rate as %.
  // Sorted descending so the worst districts read first — visual cue
  // for the Ministry to focus interventions.
  const chartData = useMemo(
    () =>
      rows
        .filter((r) => r.district_code)
        .map((r) => ({
          district: r.district_code!,
          rate_pct: Math.round((r.dropout_rate ?? 0) * 1000) / 10,
        }))
        .sort((a, b) => b.rate_pct - a.rate_pct),
    [rows],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Drop-out heatmap</h1>
        <p className="text-sm text-muted-foreground">
          Inactive + transferred students as a share of (inactive +
          transferred + active). Graduated students excluded.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Drop-out rate (%) by district</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              Loading…
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              No district-tagged dropout data to display.
            </div>
          ) : (
            <BarChart
              data={chartData}
              xKey="district"
              series={[{ key: "rate_pct", label: "Drop-out rate (%)" }]}
              height={Math.max(280, chartData.length * 28)}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All districts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4">District</th>
                  <th className="py-2 pr-4 text-right">Active</th>
                  <th className="py-2 pr-4 text-right">Drop-outs</th>
                  <th className="py-2 pr-4 text-right">Rate</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.district_code ?? "(none)"}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-4 font-mono text-xs">
                      {r.district_code ?? "(unassigned)"}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {r.active.toLocaleString()}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {r.dropouts.toLocaleString()}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {r.dropout_rate == null
                        ? "—"
                        : `${(r.dropout_rate * 100).toFixed(1)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
