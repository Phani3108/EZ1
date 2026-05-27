"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type ComplianceRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistryCompliancePage() {
  const [rows, setRows] = useState<ComplianceRow[]>([]);
  const [period, setPeriod] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    ministryApi
      .compliance(period || undefined)
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, [period]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Compliance dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Which schools have submitted which Ministry reports.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Period</span>
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g. 2026-Q1"
            className="rounded border bg-background px-2 py-1 text-sm"
          />
        </label>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Submission status</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : rows.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No submissions found for this filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">School</th>
                    <th className="py-2 pr-4">Template</th>
                    <th className="py-2 pr-4 text-right">Draft</th>
                    <th className="py-2 pr-4 text-right">Submitted</th>
                    <th className="py-2 pr-4 text-right">Accepted</th>
                    <th className="py-2 pr-4 text-right">Rejected</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={`${r.school_id}-${r.template_id}`}
                      className="border-b last:border-0"
                    >
                      <td className="py-2 pr-4 font-mono text-xs">
                        {r.school_id.slice(0, 8)}…
                      </td>
                      <td className="py-2 pr-4">
                        <div className="font-medium">{r.template_title}</div>
                        <div className="text-xs text-muted-foreground">
                          {r.template_code}
                        </div>
                      </td>
                      <td className="py-2 pr-4 text-right">{r.draft}</td>
                      <td className="py-2 pr-4 text-right">{r.submitted}</td>
                      <td className="py-2 pr-4 text-right">{r.accepted}</td>
                      <td className="py-2 pr-4 text-right">{r.rejected}</td>
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
