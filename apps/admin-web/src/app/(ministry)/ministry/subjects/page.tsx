"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type PassRateRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistrySubjectsPage() {
  const [rows, setRows] = useState<PassRateRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ministryApi
      .passRate("province")
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Subject pass-rate by region</h1>
        <p className="text-sm text-muted-foreground">
          A mark passes at ≥ 50% of max marks. Absent students excluded.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Province × subject</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : rows.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No marks data yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">Province</th>
                    <th className="py-2 pr-4">Subject</th>
                    <th className="py-2 pr-4 text-right">Graded</th>
                    <th className="py-2 pr-4 text-right">Passes</th>
                    <th className="py-2 pr-4 text-right">Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={`${r.province_code}-${r.subject_id}`}
                      className="border-b last:border-0"
                    >
                      <td className="py-2 pr-4 font-mono text-xs">
                        {r.province_code ?? "(unassigned)"}
                      </td>
                      <td className="py-2 pr-4">{r.subject_name}</td>
                      <td className="py-2 pr-4 text-right">{r.graded}</td>
                      <td className="py-2 pr-4 text-right">{r.passes}</td>
                      <td className="py-2 pr-4 text-right">
                        {r.pass_rate == null
                          ? "—"
                          : `${(r.pass_rate * 100).toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
