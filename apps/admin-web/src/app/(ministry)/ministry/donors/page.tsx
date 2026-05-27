"use client";

import React, { useEffect, useState } from "react";
import {
  ministryApi,
  type DonorsNational,
  type DonorsScopeRow,
} from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistryDonorsPage() {
  const [national, setNational] = useState<DonorsNational | null>(null);
  const [provRows, setProvRows] = useState<DonorsScopeRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([ministryApi.donors("national"), ministryApi.donors("province")])
      .then(([n, p]) => {
        setNational(n.data as DonorsNational);
        setProvRows(p.data as DonorsScopeRow[]);
      })
      .finally(() => setLoading(false));
  }, []);

  const money = (n: number) =>
    `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Donor / NGO impact</h1>
        <p className="text-sm text-muted-foreground">
          From sponsor commitments tracked under each school. Sponsor
          names are not displayed here — only amounts and counts.
        </p>
      </div>

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-xs uppercase text-muted-foreground">
                  Sponsorships
                </div>
                <div className="mt-1 text-3xl font-bold">
                  {national?.sponsorships ?? 0}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-xs uppercase text-muted-foreground">
                  Committed
                </div>
                <div className="mt-1 text-3xl font-bold">
                  {money(national?.committed ?? 0)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-xs uppercase text-muted-foreground">
                  Received
                </div>
                <div className="mt-1 text-3xl font-bold">
                  {money(national?.received ?? 0)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-xs uppercase text-muted-foreground">
                  Fulfilment
                </div>
                <div className="mt-1 text-3xl font-bold">
                  {national?.fulfilment_rate == null
                    ? "—"
                    : `${(national.fulfilment_rate * 100).toFixed(1)}%`}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">By province</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 pr-4">Province</th>
                      <th className="py-2 pr-4 text-right">Sponsorships</th>
                      <th className="py-2 pr-4 text-right">Committed</th>
                      <th className="py-2 pr-4 text-right">Received</th>
                      <th className="py-2 pr-4 text-right">Fulfilment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {provRows.map((r) => (
                      <tr
                        key={r.province_code ?? "(none)"}
                        className="border-b last:border-0"
                      >
                        <td className="py-2 pr-4 font-mono text-xs">
                          {r.province_code ?? "(unassigned)"}
                        </td>
                        <td className="py-2 pr-4 text-right">
                          {r.sponsorships}
                        </td>
                        <td className="py-2 pr-4 text-right">
                          {money(r.committed)}
                        </td>
                        <td className="py-2 pr-4 text-right">
                          {money(r.received)}
                        </td>
                        <td className="py-2 pr-4 text-right">
                          {r.fulfilment_rate == null
                            ? "—"
                            : `${(r.fulfilment_rate * 100).toFixed(1)}%`}
                        </td>
                      </tr>
                    ))}
                    {provRows.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="py-6 text-center text-muted-foreground"
                        >
                          No sponsorships recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
