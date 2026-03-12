/**
 * Parent Attendance — 30-day attendance view per child.
 */

"use client";

import React, { useState, useMemo } from "react";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { CalendarCheck, Loader2, AlertCircle, ChevronDown } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { student, attendance } from "@/lib/api";
import type { Student } from "@eduzim/api-client";

const STATUS_STYLES: Record<string, string> = {
  P: "bg-green-500 text-white",
  A: "bg-red-500 text-white",
  L: "bg-yellow-400 text-gray-900",
};
const STATUS_LABELS: Record<string, string> = {
  P: "Present", A: "Absent", L: "Late",
};

export default function ParentAttendancePage() {
  const { user } = useAuth();

  const { data: children, isLoading: loadingChildren } = useApiQuery<Student[]>(
    () => student.getMyChildren(),
    [],
  );

  const [selectedChildId, setSelectedChildId] = useState<string>("");

  // Auto-select first child
  const childId = selectedChildId || children?.[0]?.id || "";

  const { data: trend, isLoading: loadingTrend, error } = useApiQuery<import("@eduzim/api-client").AttendanceStudentTrend>(
    () => {
      if (!childId) return Promise.resolve({ data: (null as unknown) as import("@eduzim/api-client").AttendanceStudentTrend });
      return attendance.studentTrend({ student_id: childId });
    },
    [childId],
  );

  const days = trend?.days ?? [];
  const presentCount = days.filter((d: any) => d.status === "P").length;
  const absentCount = days.filter((d: any) => d.status === "A").length;
  const lateCount = days.filter((d: any) => d.status === "L").length;
  const rate = days.length > 0 ? Math.round((presentCount / days.length) * 100) : 0;

  const child = useMemo(() => (children ?? []).find((c) => c.id === childId), [children, childId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <CalendarCheck className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Attendance</h1>
          <p className="text-sm text-muted-foreground">Last 30 school days</p>
        </div>
      </div>

      {/* Child selector */}
      {children && children.length > 1 && (
        <div className="relative inline-block">
          <select
            value={childId}
            onChange={(e) => setSelectedChildId(e.target.value)}
            className="appearance-none rounded-lg border border-input bg-background pl-3 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            {children.map((c) => (
              <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message}</span>
        </div>
      )}

      {(loadingChildren || loadingTrend) && (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {!loadingTrend && trend && (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Attendance Rate", value: `${rate}%`, color: rate >= 80 ? "text-green-600" : "text-red-600" },
              { label: "Present", value: presentCount, color: "text-green-600" },
              { label: "Absent", value: absentCount, color: "text-red-600" },
              { label: "Late", value: lateCount, color: "text-yellow-600" },
            ].map((s) => (
              <Card key={s.label}>
                <CardContent className="p-4 text-center">
                  <p className={`text-2xl font-bold ${s.color}`}>{String(s.value)}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Calendar grid */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {child ? `${child.first_name} ${child.last_name}` : "Child"} — Daily Record
              </CardTitle>
            </CardHeader>
            <CardContent>
              {days.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No attendance records found.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {days.map((d: any) => (
                    <div
                      key={d.date}
                      title={`${d.date} — ${STATUS_LABELS[d.status] ?? d.status}`}
                      className={`flex h-9 w-9 flex-col items-center justify-center rounded text-[10px] font-semibold ${STATUS_STYLES[d.status] ?? "bg-muted text-muted-foreground"}`}
                    >
                      <span>{new Date(d.date + "T00:00:00").getDate()}</span>
                      <span className="opacity-70">{d.status}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-green-500 inline-block" />Present</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-red-500 inline-block" />Absent</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-yellow-400 inline-block" />Late</span>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

