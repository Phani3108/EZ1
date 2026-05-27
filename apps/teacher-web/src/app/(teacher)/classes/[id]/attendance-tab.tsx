/**
 * Attendance Tab — 10B-1C3 + 10B-4A offline queue + Phase 11a (T-001).
 *
 * T-001 (bulk-mark polish): "Mark all present / absent" buttons exist as
 * a fast-path for the common homeroom case ("everyone showed up, save in
 * one click"). The previous implementation silently destroyed manual marks
 * if the teacher clicked the wrong button — they'd lose every individual
 * Absent they'd already entered with no recovery path. Phase 11a closes
 * that with an undo snapshot (`previousStatuses`) and an inline Undo
 * affordance that's visible for 10 seconds after each bulk op. The button
 * labels also now show the affected count ("Mark all 30 present") so the
 * blast radius is obvious before the click.
 *
 * Date picker, status grid per student, bulk submit via offline queue.
 * Loads existing records from GET /attendance/daily/records.
 * Device ID: "teacher-web:<user_id>"
 */

"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
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
  Undo2,
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
  // T-002 (Phase 11a). 0 = "Day" (the legacy / primary-school homeroom
  // mark). 1..8 = a specific period in the school's schedule. The
  // backend uses (school_id, student_id, date, period_number) as the
  // upsert key, so each period gets its own row. Existing primary-mode
  // schools leave this at 0 and behave exactly like pre-T-002.
  const [selectedPeriod, setSelectedPeriod] = useState<number>(0);
  const [statuses, setStatuses] = useState<Record<string, StatusValue>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<"success" | "error" | null>(
    null
  );

  // T-001 undo state: snapshot of `statuses` taken right before a bulk op.
  // Cleared after 10s via `undoTimeoutRef` (or immediately on user undo /
  // any subsequent edit). We keep the count of affected rows so the Undo
  // pill can show "Undo (30 changed)" — gives the teacher confidence the
  // recovery is real, not a no-op.
  const [undoSnapshot, setUndoSnapshot] = useState<{
    previous: Record<string, StatusValue>;
    affected: number;
    action: "present" | "absent";
  } | null>(null);
  const undoTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch existing attendance records for this date+class+period.
  // T-002: period_number scopes the fetch so the grid shows only the
  // selected period's marks. The default (period 0) is the legacy
  // daily/homeroom view — behaves exactly like before T-002.
  const {
    data: existingRecords,
    isLoading: recordsLoading,
    refetch: refetchRecords,
  } = useApiQuery<AttendanceDailyRecord[]>(
    () =>
      attendance.dailyRecords({
        date: selectedDate,
        class_id: classId,
        period_number: String(selectedPeriod),
      }),
    [selectedDate, classId, selectedPeriod]
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

  const clearUndo = useCallback(() => {
    if (undoTimeoutRef.current) {
      clearTimeout(undoTimeoutRef.current);
      undoTimeoutRef.current = null;
    }
    setUndoSnapshot(null);
  }, []);

  const setStatus = useCallback(
    (studentId: string, status: StatusValue) => {
      setStatuses((prev) => ({ ...prev, [studentId]: status }));
      setIsDirty(true);
      setSaveResult(null);
      // Any individual edit invalidates the bulk-undo snapshot — the user
      // is now diverging from the bulk-applied state, so "undo" wouldn't
      // restore something meaningful.
      clearUndo();
    },
    [clearUndo]
  );

  const markAll = useCallback(
    (status: StatusValue) => {
      // Snapshot the current statuses BEFORE overwriting so we can offer
      // an undo. Count how many rows would actually change — a teacher who
      // clicks "Mark all present" when everyone is already P sees affected=0
      // and the Undo pill won't appear (nothing to undo).
      const previous = { ...statuses };
      let affected = 0;
      const updated: Record<string, StatusValue> = {};
      rosterStudents.forEach(({ student }) => {
        const before = statuses[student.id] ?? "P";
        if (before !== status) affected += 1;
        updated[student.id] = status;
      });
      setStatuses(updated);
      setIsDirty(true);
      setSaveResult(null);

      // No-op bulk (everyone already in target state) — don't show undo.
      if (affected === 0) {
        clearUndo();
        return;
      }

      if (undoTimeoutRef.current) clearTimeout(undoTimeoutRef.current);
      setUndoSnapshot({
        previous,
        affected,
        action: status === "P" ? "present" : "absent",
      });
      undoTimeoutRef.current = setTimeout(() => {
        setUndoSnapshot(null);
        undoTimeoutRef.current = null;
      }, 10_000);
    },
    [rosterStudents, statuses, clearUndo]
  );

  const undoBulk = useCallback(() => {
    if (!undoSnapshot) return;
    setStatuses(undoSnapshot.previous);
    clearUndo();
    // Note: we leave `isDirty` as-is. If the user had unsaved changes
    // before the bulk op, those changes are now restored — still dirty.
    // If they didn't, the snapshot equals the loaded state — but we leave
    // dirty=true rather than try to deep-compare; worst case the user
    // saves an idempotent no-op batch (which the sync endpoint dedups).
  }, [undoSnapshot, clearUndo]);

  // Clean up the undo timer on unmount.
  useEffect(() => {
    return () => {
      if (undoTimeoutRef.current) clearTimeout(undoTimeoutRef.current);
    };
  }, []);

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
      // Client event id now includes the period so two periods don't
      // collide on the dedup index (the dedup is keyed by client_event_id
      // alone, not by the row's natural key).
      client_event_id: `${student.id}-${selectedDate}-p${selectedPeriod}-${Date.now()}`,
      class_id: classId,
      student_id: student.id,
      date: selectedDate,
      status: statuses[student.id] || "P",
      period_number: selectedPeriod,
      last_modified_at: now,
    }));

    const payload = {
      device_id: deviceId,
      sync_batch_id: syncBatchId,
      generated_at: now,
      events,
    };

    try {
      // BUG-005 fix: schoolId must come from the authenticated user, not "".
      // The offline sync handler tags each queued action with the school it
      // belongs to so cross-school replay is impossible. An empty string here
      // meant the sync engine had to reverse-infer school from elsewhere or
      // would tag everything as ""-school.
      await enqueueOffline({
        type: "ATTENDANCE",
        schoolId: user.school_id,
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
      {/* Date picker + period selector + summary */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm bg-background"
          max={new Date().toISOString().slice(0, 10)}
          data-testid="attendance-date-input"
        />
        {/* T-002 period selector. "Day" = 0 (legacy / homeroom — the
            default for primary schools and any school that hasn't opted
            in to per-period marking). Periods 1..8 cover a typical
            secondary-school timetable. */}
        <select
          value={String(selectedPeriod)}
          onChange={(e) => setSelectedPeriod(Number(e.target.value))}
          className="rounded-md border px-3 py-2 text-sm bg-background"
          data-testid="attendance-period-select"
          aria-label={t("periodLabel")}
        >
          <option value="0">{t("periodDay")}</option>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((p) => (
            <option key={p} value={String(p)}>
              {t("periodN", { n: p })}
            </option>
          ))}
        </select>
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

      {/* Mark all buttons — T-001. Labels include the affected count so
          the blast radius is visible before the click; undo affordance
          appears for 10s after a destructive op. */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={() => markAll("P")}
          data-testid="attendance-bulk-present"
        >
          <Check className="h-3.5 w-3.5 mr-1" />
          {t("markAllPresentN", { n: rosterStudents.length })}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={() => markAll("A")}
          data-testid="attendance-bulk-absent"
        >
          <X className="h-3.5 w-3.5 mr-1" />
          {t("markAllAbsentN", { n: rosterStudents.length })}
        </Button>
        {undoSnapshot && (
          <button
            type="button"
            onClick={undoBulk}
            data-testid="attendance-bulk-undo"
            className="inline-flex items-center gap-1 rounded-md border border-blue-300 bg-blue-50 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100 transition-colors"
          >
            <Undo2 className="h-3.5 w-3.5" />
            {t("undoBulkN", { n: undoSnapshot.affected })}
          </button>
        )}
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
