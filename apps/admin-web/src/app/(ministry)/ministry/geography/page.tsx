"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type GeographyRow } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent } from "@eduzim/ui";

export default function MinistryGeographyPage() {
  const [geo, setGeo] = useState<GeographyRow | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ministryApi
      .geography()
      .then((r) => setGeo(r.data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-48 animate-pulse rounded bg-muted" />;
  if (!geo) return null;

  // Group districts by province.
  const byProvince = new Map<string, typeof geo.districts>();
  for (const d of geo.districts) {
    if (!byProvince.has(d.province_code)) byProvince.set(d.province_code, []);
    byProvince.get(d.province_code)!.push(d);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Geography reference</h1>
        <p className="text-sm text-muted-foreground">
          Zimbabwean provinces + districts (MoPSE codes).
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {geo.provinces.map((p) => (
          <Card key={p.code}>
            <CardHeader>
              <CardTitle className="text-base">
                {p.name} ({p.code})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="text-xs text-muted-foreground">
                Capital: {p.capital} · Region: {p.region}
              </div>
              <ul className="space-y-1 text-sm">
                {(byProvince.get(p.code) ?? []).map((d) => (
                  <li
                    key={d.code}
                    className="flex justify-between border-b pb-1 last:border-0"
                  >
                    <span>{d.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {d.code}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
