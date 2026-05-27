"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type PtrRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistryResourcesPage() {
  const [rows, setRows] = useState<PtrRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ministryApi
      .ptr("district")
      .then((r) => setRows(r.data as PtrRow[]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Resources · PTR</h1>
        <p className="text-sm text-muted-foreground">
          Pupil:Teacher ratio by district. Device count + electricity
          coverage are pending — see ADR 020.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By district</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">District</th>
                    <th className="py-2 pr-4 text-right">Students</th>
                    <th className="py-2 pr-4 text-right">Teachers</th>
                    <th className="py-2 pr-4 text-right">PTR</th>
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
                        {r.active_students.toLocaleString()}
                      </td>
                      <td className="py-2 pr-4 text-right">{r.teachers}</td>
                      <td className="py-2 pr-4 text-right">
                        {r.ptr == null ? "—" : r.ptr.toFixed(1)}
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
