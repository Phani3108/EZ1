/**
 * Class Detail page — 10B-1C2.
 * Tabs: Roster, Attendance, Announcements
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
  BookOpen,
  Users,
  ClipboardCheck,
  Megaphone,
  GraduationCap,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher, student, comm } from "@/lib/api";
import type {
  TeacherClass,
  Enrollment,
  Student as StudentType,
  Announcement,
} from "@eduzim/api-client";
import { RosterTab } from "./roster-tab";
import { AttendanceTab } from "./attendance-tab";
import { AssessmentsTab } from "./assessments-tab";

export default function ClassDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const classId = params.id as string;
  const t = useTranslations("classes");

  const defaultTab = searchParams.get("tab") || "roster";
  const defaultDate = searchParams.get("date") || new Date().toISOString().slice(0, 10);

  // Fetch class info from teacher's classes
  const { data: classes } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    []
  );

  const classInfo = useMemo(
    () => classes?.find((c) => c.id === classId) ?? null,
    [classes, classId]
  );

  // Fetch enrollments for roster
  const { data: enrollments, isLoading: enrollmentsLoading } =
    useApiQuery<Enrollment[]>(
      () => student.getEnrollmentsByClass(classId),
      [classId]
    );

  // Fetch students for names
  const { data: students } = useApiQuery<StudentType[]>(
    () => student.list(),
    []
  );

  const studentMap = useMemo(() => {
    const map = new Map<string, StudentType>();
    students?.forEach((s) => map.set(s.id, s));
    return map;
  }, [students]);

  // Roster students — join enrollments + student data
  const rosterStudents = useMemo(() => {
    if (!enrollments) return [];
    return enrollments
      .map((e) => {
        const s = studentMap.get(e.student_id);
        return s ? { enrollment: e, student: s } : null;
      })
      .filter(Boolean) as { enrollment: Enrollment; student: StudentType }[];
  }, [enrollments, studentMap]);

  // Announcements for this class
  const { data: announcements, isLoading: announcementsLoading } =
    useApiQuery<Announcement[]>(
      () => comm.getFeed({ limit: "20", class_id: classId }),
      [classId]
    );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/classes"
          className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {classInfo ? classInfo.name : t("classDetail")}
          </h1>
          {classInfo && (
            <p className="text-sm text-muted-foreground">
              {t("section", { section: classInfo.section })}
              {classInfo.capacity
                ? ` · ${t("capacity", { count: String(classInfo.capacity) })}`
                : ""}
            </p>
          )}
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <BookOpen className="h-5 w-5 text-primary" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={defaultTab}>
        <TabsList className="w-full grid grid-cols-4">
          <TabsTrigger value="roster" className="flex items-center gap-1.5">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">{t("roster")}</span>
          </TabsTrigger>
          <TabsTrigger value="attendance" className="flex items-center gap-1.5">
            <ClipboardCheck className="h-4 w-4" />
            <span className="hidden sm:inline">{t("attendance")}</span>
          </TabsTrigger>
          <TabsTrigger value="assessments" className="flex items-center gap-1.5">
            <GraduationCap className="h-4 w-4" />
            <span className="hidden sm:inline">{t("assessments")}</span>
          </TabsTrigger>
          <TabsTrigger
            value="announcements"
            className="flex items-center gap-1.5"
          >
            <Megaphone className="h-4 w-4" />
            <span className="hidden sm:inline">{t("announcements")}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="roster">
          <RosterTab
            rosterStudents={rosterStudents}
            isLoading={enrollmentsLoading}
            classId={classId}
          />
        </TabsContent>

        <TabsContent value="attendance">
          <AttendanceTab
            classId={classId}
            rosterStudents={rosterStudents}
            defaultDate={defaultDate}
          />
        </TabsContent>

        <TabsContent value="assessments">
          <AssessmentsTab
            classId={classId}
            rosterStudents={rosterStudents}
            academicYearId={classInfo?.academic_year_id}
          />
        </TabsContent>

        <TabsContent value="announcements">
          <div className="space-y-2">
            {announcementsLoading ? (
              <Card className="animate-pulse">
                <CardContent className="p-4">
                  <div className="h-4 w-48 bg-muted rounded mb-2" />
                  <div className="h-3 w-32 bg-muted rounded" />
                </CardContent>
              </Card>
            ) : announcements && announcements.length > 0 ? (
              announcements.map((a) => (
                <Card key={a.id}>
                  <CardContent className="flex items-start gap-3 p-4">
                    <Megaphone className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{a.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {a.body}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(a.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent className="p-6 text-center text-sm text-muted-foreground">
                  {t("noAnnouncements")}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
