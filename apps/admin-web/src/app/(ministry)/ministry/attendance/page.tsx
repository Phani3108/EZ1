"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type AttendanceScopeRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent, BarChart } from "@eduzim/ui";

export default function MinistryAttendancePage() {
  const [provRows, setProvRows] = useState<AttendanceScopeRow[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    ministryApi
      .attendance("province", days)
      .then((r) => setProvRows(r.data as AttendanceScopeRow[]))
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Attendance</h1>
          <p className="text-sm text-muted-foreground">
            Present / (present + absent + late). Past {days} days.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Window (days)</span>
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="rounded border bg-background px-2 py-1"
          >
            {[7, 14, 30, 60, 90, 180, 365].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By province</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : (
            <BarChart
              data={provRows.map((r) => ({
                province: r.province_code ?? "(none)",
                rate_pct: r.rate == null ? 0 : Math.round(r.rate * 1000) / 10,
              }))}
              xKey="province"
              series={[{ key: "rate_pct", label: "Attendance rate (%)" }]}
              height={280}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
