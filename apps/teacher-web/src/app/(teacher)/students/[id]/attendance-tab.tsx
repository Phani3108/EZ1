/**
 * Attendance Tab — Student attendance trend (last 30/90 days).
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { ClipboardCheck } from "lucide-react";
import type { AttendanceStudentTrend } from "@eduzim/api-client";

interface StudentAttendanceTabProps {
  trend: AttendanceStudentTrend | null | undefined;
  isLoading: boolean;
}

export function StudentAttendanceTab({
  trend,
  isLoading,
}: StudentAttendanceTabProps) {
  const t = useTranslations("students");

  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <CardContent className="p-6 space-y-4">
          <div className="h-5 w-40 bg-muted rounded" />
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-muted rounded" />
            ))}
          </div>
          <div className="h-32 bg-muted rounded" />
        </CardContent>
      </Card>
    );
  }

  if (!trend || (!trend.total_days && trend.total_days !== 0)) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <ClipboardCheck className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            {t("noAttendanceData")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const rate = trend.total_days > 0
    ? Math.round((trend.present / trend.total_days) * 100)
    : 0;

  const stats = [
    {
      label: t("present"),
      value: trend.present,
      color: "text-green-600 bg-green-50",
    },
    {
      label: t("absent"),
      value: trend.absent,
      color: "text-red-600 bg-red-50",
    },
    {
      label: t("late"),
      value: trend.late,
      color: "text-amber-600 bg-amber-50",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Attendance Rate Card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">
              {t("attendanceRate")}
            </h3>
            <span className="text-xs text-muted-foreground">
              {t("last90Days")}
            </span>
          </div>
          <div className="flex items-end gap-2 mb-4">
            <span className="text-4xl font-bold">{rate}%</span>
            <span className="text-sm text-muted-foreground mb-1">
              ({trend.present}/{trend.total_days} {t("days")})
            </span>
          </div>
          {/* Progress bar */}
          <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${rate}%` }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className={`p-4 text-center ${s.color} rounded-lg`}>
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-xs font-medium mt-1">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Daily breakdown */}
      {trend.days && trend.days.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">
              {t("recentDays")}
            </h3>
            <div className="flex flex-wrap gap-1">
              {trend.days.slice(-30).map((d, idx) => (
                <div
                  key={idx}
                  title={`${d.date}: ${d.status}`}
                  className={`h-6 w-6 rounded text-[10px] flex items-center justify-center font-medium ${
                    d.status === "P"
                      ? "bg-green-100 text-green-700"
                      : d.status === "A"
                        ? "bg-red-100 text-red-700"
                        : d.status === "L"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-muted text-muted-foreground"
                  }`}
                >
                  {d.status}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
