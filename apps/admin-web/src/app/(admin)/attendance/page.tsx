/**
 * Attendance Daily Summary — date + class selector → stats + student records table.
 * v1: requires class selection (keeps API simple).
 * Permission: attendance:read
 */

"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { StatCard, Badge, Select } from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { SchoolClass, AttendanceDailySummary, AttendanceDailyRecord, Student } from "@eduzim/api-client";
import { school, attendance, student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { ClipboardCheck, Users, UserX, Clock } from "lucide-react";

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

export default function AttendanceDailyPage() {
  const t = useTranslations("attendance");

  // Controls
  const today = formatDate(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [selectedClassId, setSelectedClassId] = useState("");

  // Fetch classes
  const { data: classes } = useApiQuery(() => school.listClasses(), []);

  const classOptions = useMemo(() => {
    if (!classes) return [];
    return classes.map((c: SchoolClass) => ({
      value: c.id,
      label: `${c.name} (Grade ${c.grade_level})`,
    }));
  }, [classes]);

  // Fetch daily summary when class selected
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useApiQuery(
    () => {
      if (!selectedClassId) return Promise.resolve({ data: null as any });
      return attendance.dailySummary({
        date: selectedDate,
        class_id: selectedClassId,
      });
    },
    [selectedDate, selectedClassId],
  );

  // Fetch per-student records when class selected
  const { data: records, isLoading: recordsLoading, error: recordsError } = useApiQuery(
    () => {
      if (!selectedClassId) return Promise.resolve({ data: [] as AttendanceDailyRecord[] });
      return attendance.dailyRecords({
        date: selectedDate,
        class_id: selectedClassId,
      });
    },
    [selectedDate, selectedClassId],
  );

  // Fetch students to resolve names
  const { data: students } = useApiQuery(() => studentApi.list(), []);

  const studentMap = useMemo(() => {
    const m = new Map<string, Student>();
    students?.forEach((s: Student) => m.set(s.id, s));
    return m;
  }, [students]);

  const statusBadgeVariant = (status: string) => {
    switch (status) {
      case "P": return "default" as const;
      case "L": return "secondary" as const;
      case "A": return "destructive" as const;
      default: return "secondary" as const;
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case "P": return t("present");
      case "A": return t("absent");
      case "L": return t("late");
      default: return status;
    }
  };

  return (
    <RouteGuard permissions={["attendance:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <PageHeader title={t("dailyAttendance")} />

        {/* Controls row */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <label htmlFor="att-date" className="text-sm font-medium text-muted-foreground">
              {t("date")}
            </label>
            <input
              id="att-date"
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="block rounded-md border bg-background px-3 py-2 text-sm shadow-sm"
            />
          </div>
          <div className="w-64 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">
              {t("selectClass")}
            </label>
            <Select
              options={classOptions}
              placeholder={t("selectClass")}
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
            />
          </div>
        </div>

        {/* Stats */}
        {selectedClassId && summary && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label={t("present")}
              value={summary.P ?? 0}
              icon={Users}
            />
            <StatCard
              label={t("absent")}
              value={summary.A ?? 0}
              icon={UserX}
            />
            <StatCard
              label={t("late")}
              value={summary.L ?? 0}
              icon={Clock}
            />
            <StatCard
              label={t("attendanceRate")}
              value={`${summary.attendance_rate ?? 0}%`}
              icon={ClipboardCheck}
            />
          </div>
        )}

        {/* Errors */}
        {summaryError && (
          <ErrorAlert message={summaryError.message} requestId={summaryError.requestId} details={summaryError.details} />
        )}
        {recordsError && (
          <ErrorAlert message={recordsError.message} requestId={recordsError.requestId} details={recordsError.details} />
        )}

        {/* Content */}
        {!selectedClassId ? (
          <EmptyState
            icon={ClipboardCheck}
            title={t("noRecords")}
            description={t("selectClass")}
          />
        ) : summaryLoading || recordsLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : !records || records.length === 0 ? (
          <EmptyState
            icon={ClipboardCheck}
            title={t("noRecords")}
            description={t("noRecordsDescription")}
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("studentName")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                  <TableHead>{t("lastModified")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records.map((r: AttendanceDailyRecord) => {
                  const s = studentMap.get(r.student_id);
                  return (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">
                        <a
                          href={`/students/${r.student_id}`}
                          className="text-primary hover:underline"
                        >
                          {s ? `${s.first_name} ${s.last_name}` : r.student_id}
                        </a>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(r.status)}>
                          {statusLabel(r.status)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {r.last_modified_at
                          ? new Date(r.last_modified_at).toLocaleString()
                          : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
