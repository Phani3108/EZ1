"use client";

import React, { useEffect, useState } from "react";
import { ministryApi, type UnescoExport } from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent, Button } from "@eduzim/ui";

export default function MinistryExportsPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<UnescoExport | null>(null);
  const [loading, setLoading] = useState(false);

  const load = (y: number) => {
    setLoading(true);
    ministryApi
      .unesco(y)
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(year);
  }, []);

  const downloadJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eduzim-unesco-${data.reporting_year}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">UNESCO / UNICEF export</h1>
        <p className="text-sm text-muted-foreground">
          Canonical national snapshot in a stable, versioned schema —
          attach directly to international statistical returns.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Reporting year</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value, 10) || year)}
            className="w-32 rounded border bg-background px-2 py-1"
            min={2000}
            max={2100}
          />
          <Button onClick={() => load(year)} disabled={loading}>
            {loading ? "Generating…" : "Regenerate"}
          </Button>
          <Button
            variant="outline"
            onClick={downloadJson}
            disabled={loading || !data}
          >
            Download JSON
          </Button>
        </CardContent>
      </Card>

      {data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Preview · generated {new Date(data.generated_at).toLocaleString()}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[480px] overflow-auto rounded bg-muted/30 p-4 text-xs">
              {JSON.stringify(data, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
