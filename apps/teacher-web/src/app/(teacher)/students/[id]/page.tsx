/**
 * Student Detail page — 10B-1E.
 * Tabs: Overview, Attendance, Announcements (no Fees)
 * Access control: teacher must be assigned to a class the student is enrolled in.
 */

"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Card,
  CardContent,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@eduzim/ui";
import {
  ArrowLeft,
  UserCircle,
  ClipboardCheck,
  Megaphone,
  ShieldAlert,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher, student, attendance, comm, reports } from "@/lib/api";
import type {
  TeacherClass,
  Student as StudentType,
  Enrollment,
  AttendanceStudentTrend,
  Announcement,
  DropoutStudentDetail,
} from "@eduzim/api-client";
import { OverviewTab } from "./overview-tab";
import { StudentAttendanceTab } from "./attendance-tab";
import { StudentAnnouncementsTab } from "./announcements-tab";

export default function StudentDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const studentId = params.id as string;
  const classId = searchParams.get("classId") || "";
  const t = useTranslations("students");
  const tc = useTranslations("common");

  const defaultTab = searchParams.get("tab") || "overview";

  // Fetch teacher's classes for authorization
  const { data: classes } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    []
  );

  // Fetch student info
  const { data: studentData, isLoading: studentLoading } =
    useApiQuery<StudentType>(() => student.get(studentId), [studentId]);

  // Fetch student enrollments
  const { data: enrollments } = useApiQuery<Enrollment[]>(
    () => student.getStudentEnrollments(studentId),
    [studentId]
  );

  // Authorization: check if classId is in teacher's classes
  const isAuthorized = useMemo(() => {
    if (!classes || !classId) return false;
    return classes.some((c) => c.id === classId);
  }, [classes, classId]);

  // Also verify student is in a class the teacher owns (from enrollment data)
  const studentClassIds = useMemo(() => {
    if (!enrollments) return new Set<string>();
    return new Set(enrollments.map((e) => e.class_id));
  }, [enrollments]);

  const teacherClassIds = useMemo(() => {
    if (!classes) return new Set<string>();
    return new Set(classes.map((c) => c.id));
  }, [classes]);

  const hasOverlap = useMemo(() => {
    for (const cid of studentClassIds) {
      if (teacherClassIds.has(cid)) return true;
    }
    return false;
  }, [studentClassIds, teacherClassIds]);

  const authorized = isAuthorized || hasOverlap;

  // Back link — go to class detail roster if classId provided
  const backHref = classId ? `/classes/${classId}?tab=roster` : "/classes";

  // Attendance trend (last 90 days)
  const today = new Date().toISOString().slice(0, 10);
  const ninetyDaysAgo = new Date(Date.now() - 90 * 86400000)
    .toISOString()
    .slice(0, 10);

  const { data: trend, isLoading: trendLoading } =
    useApiQuery<AttendanceStudentTrend>(
      () =>
        authorized
          ? attendance.studentTrend({
            student_id: studentId,
            from: ninetyDaysAgo,
            to: today,
          })
          : Promise.resolve({ data: null as unknown as AttendanceStudentTrend }),
      [studentId, authorized]
    );

  // Announcements for the student's class
  const { data: announcements, isLoading: announcementsLoading } =
    useApiQuery<Announcement[]>(
      () =>
        authorized && classId
          ? comm.getFeed({ limit: "20", class_id: classId })
          : Promise.resolve({ data: [] as Announcement[] }),
      [classId, authorized]
    );

  // Dropout risk detail (attendance signals only — fee signals hidden in UI)
  const { data: riskDetail } = useApiQuery<DropoutStudentDetail>(
    () =>
      authorized
        ? reports.dropoutStudentDetail(studentId)
        : Promise.resolve({ data: null as unknown as DropoutStudentDetail }),
    [studentId, authorized]
  );

  // Unauthorized state
  if (classes && !authorized && !studentLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-3">
          <Link
            href="/classes"
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("unauthorized")}
          </h1>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center gap-3 p-8">
            <ShieldAlert className="h-12 w-12 text-destructive" />
            <p className="text-sm text-muted-foreground text-center">
              {t("unauthorizedMessage")}
            </p>
            <Link
              href="/classes"
              className="mt-2 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
            >
              {tc("back")}
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href={backHref}
          className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {studentLoading
              ? t("loading")
              : studentData
                ? `${studentData.first_name} ${studentData.last_name}`
                : t("studentNotFound")}
          </h1>
          {studentData && (
            <p className="text-sm text-muted-foreground">
              {studentData.student_code
                ? `${t("admissionNo")}: ${studentData.student_code}`
                : ""}
            </p>
          )}
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <UserCircle className="h-5 w-5 text-primary" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={defaultTab}>
        <TabsList className="w-full grid grid-cols-3">
          <TabsTrigger value="overview" className="flex items-center gap-1.5">
            <UserCircle className="h-4 w-4" />
            <span className="hidden sm:inline">{t("overview")}</span>
          </TabsTrigger>
          <TabsTrigger value="attendance" className="flex items-center gap-1.5">
            <ClipboardCheck className="h-4 w-4" />
            <span className="hidden sm:inline">{t("attendance")}</span>
          </TabsTrigger>
          <TabsTrigger
            value="announcements"
            className="flex items-center gap-1.5"
          >
            <Megaphone className="h-4 w-4" />
            <span className="hidden sm:inline">{t("announcements")}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab student={studentData} isLoading={studentLoading} riskDetail={riskDetail} />
        </TabsContent>

        <TabsContent value="attendance">
          <StudentAttendanceTab trend={trend} isLoading={trendLoading} />
        </TabsContent>

        <TabsContent value="announcements">
          <StudentAnnouncementsTab
            announcements={announcements}
            isLoading={announcementsLoading}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
