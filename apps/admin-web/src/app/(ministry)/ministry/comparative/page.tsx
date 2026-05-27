"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type ComparativeRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistryComparativePage() {
  const [rows, setRows] = useState<ComparativeRow[]>([]);
  const [anonymize, setAnonymize] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    ministryApi
      .comparative({ anonymize })
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, [anonymize]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Comparative view</h1>
          <p className="text-sm text-muted-foreground">
            School-by-school side-by-side. Toggle anonymise to share
            externally without publishing names.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={anonymize}
            onChange={(e) => setAnonymize(e.target.checked)}
          />
          <span>Anonymise school names</span>
        </label>
      </div>

      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">School</th>
                    <th className="py-2 pr-4">District</th>
                    <th className="py-2 pr-4 text-right">Active</th>
                    <th className="py-2 pr-4 text-right">Dropouts</th>
                    <th className="py-2 pr-4 text-right">Teachers</th>
                    <th className="py-2 pr-4 text-right">PTR</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr
                      key={r.school_id ?? `pseudo-${i}`}
                      className="border-b last:border-0"
                    >
                      <td className="py-2 pr-4 font-medium">{r.label}</td>
                      <td className="py-2 pr-4 font-mono text-xs">
                        {r.district_code ?? "—"}
                      </td>
                      <td className="py-2 pr-4 text-right">
                        {r.active_students.toLocaleString()}
                      </td>
                      <td className="py-2 pr-4 text-right">{r.dropouts}</td>
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
