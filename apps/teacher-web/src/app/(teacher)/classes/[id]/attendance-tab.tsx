/**
 * Attendance Tab — 10B-1C3 + 10B-4A offline queue.
 * Date picker, status grid per student, bulk submit via offline queue.
 * Loads existing records from GET /attendance/daily/records.
 * Device ID: "teacher-web:<user_id>"
 */

"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, Button } from "@eduzim/ui";
import {
  ClipboardCheck,
  Check,
  X,
  Clock,
  Save,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { attendance } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useSync } from "@/lib/sync-provider";
import type {
  Enrollment,
  Student,
  AttendanceDailyRecord,
  AttendanceSyncEvent,
} from "@eduzim/api-client";

type StatusValue = "P" | "A" | "L";

interface AttendanceTabProps {
  classId: string;
  rosterStudents: { enrollment: Enrollment; student: Student }[];
  defaultDate: string;
}

export function AttendanceTab({
  classId,
  rosterStudents,
  defaultDate,
}: AttendanceTabProps) {
  const t = useTranslations("classes");
  const { user } = useAuth();
  const [selectedDate, setSelectedDate] = useState(defaultDate);
  const [statuses, setStatuses] = useState<Record<string, StatusValue>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<"success" | "error" | null>(
    null
  );

  // Fetch existing attendance records for this date+class
  const {
    data: existingRecords,
    isLoading: recordsLoading,
    refetch: refetchRecords,
  } = useApiQuery<AttendanceDailyRecord[]>(
    () =>
      attendance.dailyRecords({
        date: selectedDate,
        class_id: classId,
      }),
    [selectedDate, classId]
  );

  // Merge existing records into status map when they load
  useEffect(() => {
    const initial: Record<string, StatusValue> = {};

    // First set all roster students to P (default)
    rosterStudents.forEach(({ student }) => {
      initial[student.id] = "P";
    });

    // Then overlay existing records
    if (existingRecords) {
      existingRecords.forEach((r) => {
        if (r.status === "P" || r.status === "A" || r.status === "L") {
          initial[r.student_id] = r.status as StatusValue;
        }
      });
    }

    setStatuses(initial);
    setIsDirty(false);
    setSaveResult(null);
  }, [existingRecords, rosterStudents]);

  const setStatus = useCallback(
    (studentId: string, status: StatusValue) => {
      setStatuses((prev) => ({ ...prev, [studentId]: status }));
      setIsDirty(true);
      setSaveResult(null);
    },
    []
  );

  const markAll = useCallback(
    (status: StatusValue) => {
      const updated: Record<string, StatusValue> = {};
      rosterStudents.forEach(({ student }) => {
        updated[student.id] = status;
      });
      setStatuses(updated);
      setIsDirty(true);
      setSaveResult(null);
    },
    [rosterStudents]
  );

  // Summary counts
  const summary = useMemo(() => {
    const values = Object.values(statuses);
    return {
      P: values.filter((v) => v === "P").length,
      A: values.filter((v) => v === "A").length,
      L: values.filter((v) => v === "L").length,
      total: values.length,
    };
  }, [statuses]);

  const { enqueueOffline, online } = useSync();

  // Bulk save via offline queue → /attendance/sync
  const handleSave = async () => {
    if (!user || rosterStudents.length === 0) return;
    setIsSaving(true);
    setSaveResult(null);

    const now = new Date().toISOString();
    const deviceId = `teacher-web:${user.id}`;
    const syncBatchId = `tw-${classId}-${selectedDate}-${Date.now()}`;

    const events: AttendanceSyncEvent[] = rosterStudents.map(({ student }) => ({
      client_event_id: `${student.id}-${selectedDate}-${Date.now()}`,
      class_id: classId,
      student_id: student.id,
      date: selectedDate,
      status: statuses[student.id] || "P",
      last_modified_at: now,
    }));

    const payload = {
      device_id: deviceId,
      sync_batch_id: syncBatchId,
      generated_at: now,
      events,
    };

    try {
      await enqueueOffline({
        type: "ATTENDANCE",
        schoolId: "",
        userId: user.id,
        deviceId,
        payload,
        syncBatchId,
      });
      setSaveResult("success");
      setIsDirty(false);
      // If online, refetch to confirm server state
      if (online) {
        setTimeout(() => refetchRecords(), 1500);
      }
    } catch {
      setSaveResult("error");
    } finally {
      setIsSaving(false);
    }
  };

  if (rosterStudents.length === 0 && !recordsLoading) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <ClipboardCheck className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">{t("noStudents")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Date picker + summary */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
          max={new Date().toISOString().slice(0, 10)}
        />
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-green-600">
            <Check className="h-3.5 w-3.5" /> {summary.P}
          </span>
          <span className="flex items-center gap-1 text-red-600">
            <X className="h-3.5 w-3.5" /> {summary.A}
          </span>
          <span className="flex items-center gap-1 text-yellow-600">
            <Clock className="h-3.5 w-3.5" /> {summary.L}
          </span>
        </div>
      </div>

      {/* Mark all buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={() => markAll("P")}
        >
          {t("markAll")} {t("present")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={() => markAll("A")}
        >
          {t("markAll")} {t("absent")}
        </Button>
      </div>

      {/* Student grid */}
      {recordsLoading ? (
        <Card className="animate-pulse">
          <CardContent className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded" />
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      #
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      {t("studentName")}
                    </th>
                    <th className="px-4 py-3 text-center font-medium text-muted-foreground w-32">
                      {t("present")}
                    </th>
                    <th className="px-4 py-3 text-center font-medium text-muted-foreground w-32">
                      {t("absent")}
                    </th>
                    <th className="px-4 py-3 text-center font-medium text-muted-foreground w-32">
                      {t("late")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rosterStudents.map(({ student }, idx) => {
                    const status = statuses[student.id] || "P";
                    return (
                      <tr
                        key={student.id}
                        className="border-b last:border-0 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3 text-muted-foreground">
                          {idx + 1}
                        </td>
                        <td className="px-4 py-3 font-medium">
                          {student.first_name} {student.last_name}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <StatusButton
                            active={status === "P"}
                            color="green"
                            onClick={() => setStatus(student.id, "P")}
                          >
                            <Check className="h-4 w-4" />
                          </StatusButton>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <StatusButton
                            active={status === "A"}
                            color="red"
                            onClick={() => setStatus(student.id, "A")}
                          >
                            <X className="h-4 w-4" />
                          </StatusButton>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <StatusButton
                            active={status === "L"}
                            color="yellow"
                            onClick={() => setStatus(student.id, "L")}
                          >
                            <Clock className="h-4 w-4" />
                          </StatusButton>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Save bar */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleSave}
          disabled={isSaving || !isDirty || rosterStudents.length === 0}
          className="flex items-center gap-2"
        >
          <Save className="h-4 w-4" />
          {isSaving ? t("saving") : t("saveAttendance")}
        </Button>
        {saveResult === "success" && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <CheckCircle className="h-4 w-4" />
            {online ? t("saved") : "Queued for sync"}
          </span>
        )}
        {saveResult === "error" && (
          <span className="flex items-center gap-1 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" />
            {t("saveFailed")}
          </span>
        )}
      </div>
    </div>
  );
}

/* ─── Status toggle button ─── */
function StatusButton({
  active,
  color,
  onClick,
  children,
}: {
  active: boolean;
  color: "green" | "red" | "yellow";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const colorMap = {
    green: active
      ? "bg-green-100 text-green-700 border-green-300"
      : "text-muted-foreground hover:bg-green-50",
    red: active
      ? "bg-red-100 text-red-700 border-red-300"
      : "text-muted-foreground hover:bg-red-50",
    yellow: active
      ? "bg-yellow-100 text-yellow-700 border-yellow-300"
      : "text-muted-foreground hover:bg-yellow-50",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors ${colorMap[color]}`}
    >
      {children}
    </button>
  );
}
