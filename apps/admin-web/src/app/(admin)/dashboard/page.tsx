/**
 * Admin Dashboard — overview cards from reporting-service.
 */

"use client";

import React, { useEffect, useState } from "react";
import { reports } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { ApiError, type DashboardData } from "@eduzim/api-client";
import { Users, GraduationCap, ClipboardCheck, DollarSign, Megaphone, AlertTriangle } from "lucide-react";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reports
      .dashboard()
      .then(({ data }) => setData(data))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-20 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Card>
          <CardContent className="flex items-center gap-3 p-6 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {error}
          </CardContent>
        </Card>
      </div>
    );
  }

  const stats = [
    { title: "Total Students", value: data?.total_students ?? 0, icon: Users, color: "text-blue-600" },
    { title: "Total Classes", value: data?.total_classes ?? 0, icon: GraduationCap, color: "text-indigo-600" },
    { title: "Attendance Rate", value: `${((data?.attendance_rate ?? 0) * 100).toFixed(1)}%`, icon: ClipboardCheck, color: "text-green-600" },
    { title: "Total Revenue", value: `$${(data?.total_revenue ?? 0).toLocaleString()}`, icon: DollarSign, color: "text-emerald-600" },
    { title: "Outstanding", value: `$${(data?.total_outstanding ?? 0).toLocaleString()}`, icon: DollarSign, color: "text-orange-600" },
    { title: "Announcements", value: data?.announcements_count ?? 0, icon: Megaphone, color: "text-purple-600" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-5 w-5 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
