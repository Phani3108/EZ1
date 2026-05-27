"use client";

import React, { useEffect, useState } from "react";
import {
  ministryApi,
  type EnrolmentProvinceRow,
  type EnrolmentDistrictRow,
} from "@/lib/ministry-api";
import { Card, CardHeader, CardTitle, CardContent, BarChart } from "@eduzim/ui";

export default function MinistryEnrolmentPage() {
  const [provinces, setProvinces] = useState<EnrolmentProvinceRow[]>([]);
  const [districts, setDistricts] = useState<EnrolmentDistrictRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      ministryApi.enrolmentProvince(),
      ministryApi.enrolmentDistrict(),
    ])
      .then(([p, d]) => {
        setProvinces(p.data);
        setDistricts(d.data);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Enrolment</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By province</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-48 animate-pulse rounded bg-muted" />
          ) : (
            <BarChart
              data={provinces.map((p) => ({
                province: p.province_code ?? "(none)",
                students: p.students,
                schools: p.schools,
              }))}
              xKey="province"
              series={[
                { key: "students", label: "Active students" },
                { key: "schools", label: "Schools" },
              ]}
              height={280}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">By district</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4">District</th>
                  <th className="py-2 pr-4">Province</th>
                  <th className="py-2 pr-4 text-right">Schools</th>
                  <th className="py-2 pr-4 text-right">Students</th>
                </tr>
              </thead>
              <tbody>
                {districts.map((d) => (
                  <tr
                    key={d.district_code ?? "(none)"}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-4 font-mono text-xs">
                      {d.district_code ?? "(unassigned)"}
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs">
                      {d.province_code ?? "—"}
                    </td>
                    <td className="py-2 pr-4 text-right">{d.schools}</td>
                    <td className="py-2 pr-4 text-right">{d.students}</td>
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
