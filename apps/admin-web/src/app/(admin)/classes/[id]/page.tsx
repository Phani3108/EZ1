/**
 * Classroom Roster — view students enrolled in a specific class.
 * Shows class details header + academic-year selector + enrolled students table.
 * Permission: student:read
 */

"use client";

import React, { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge, Button, Select,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { SchoolClass, Enrollment, Student, AcademicYear } from "@eduzim/api-client";
import { school, student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { DetailHeader } from "@/components/detail-header";
import { EmptyState } from "@/components/empty-state";
import { Users, GraduationCap, Calendar, Hash } from "lucide-react";

export default function ClassRosterPage() {
  const params = useParams<{ id: string }>();
  const classId = params.id;
  const t = useTranslations("roster");

  const [selectedYearId, setSelectedYearId] = useState<string>("");

  // Fetch class details
  const { data: classData, isLoading: classLoading, error: classError } = useApiQuery(
    () => school.getClass(classId),
    [classId],
  );

  // Fetch academic years
  const { data: years } = useApiQuery(() => school.listAcademicYears(), []);

  // Determine current year: is_current=true first, fallback to latest start_date
  const currentYear = useMemo(() => {
    if (!years || years.length === 0) return undefined;
    const cur = years.find((y: AcademicYear) => y.is_current);
    if (cur) return cur;
    return [...years].sort(
      (a: AcademicYear, b: AcademicYear) =>
        new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
    )[0];
  }, [years]);

  // Auto-select current year once loaded
  React.useEffect(() => {
    if (currentYear && !selectedYearId) {
      setSelectedYearId(currentYear.id);
    }
  }, [currentYear, selectedYearId]);

  // Fetch enrollments for this class (optionally filtered by year)
  const { data: enrollments, isLoading: enrollLoading, error: enrollError } = useApiQuery(
    () => studentApi.getEnrollmentsByClass(classId, selectedYearId || undefined),
    [classId, selectedYearId],
  );

  // Fetch all students to resolve names (could be optimised with a backend join later)
  const { data: students } = useApiQuery(() => studentApi.list(), []);

  const studentMap = useMemo(() => {
    const m = new Map<string, Student>();
    students?.forEach((s: Student) => m.set(s.id, s));
    return m;
  }, [students]);

  // Year selector options
  const yearOptions = useMemo(() => {
    if (!years) return [];
    return years.map((y: AcademicYear) => ({
      value: y.id,
      label: y.is_current ? `${y.name} (current)` : y.name,
    }));
  }, [years]);

  if (classLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (classError) {
    return (
      <div className="space-y-4">
        <DetailHeader backHref="/classes" backLabel="Classes" title="Class" />
        <ErrorAlert message={classError.message} requestId={classError.requestId} details={classError.details} />
      </div>
    );
  }

  if (!classData) return null;

  const enrolledCount = enrollments?.length || 0;

  return (
    <RouteGuard permissions={["student:read"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <DetailHeader
          backHref="/classes"
          backLabel="Classes"
          title={classData.name}
          subtitle={`${t("gradeLevel")}: ${classData.grade_level}`}
          badges={[{ label: "Active", variant: "default" as const }]}
        />

        {/* Stats row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardContent className="flex items-center gap-3 pt-6">
              <GraduationCap className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">{t("gradeLevel")}</p>
                <p className="text-2xl font-bold">{classData.grade_level}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 pt-6">
              <Users className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">{t("enrolled")}</p>
                <p className="text-2xl font-bold">{enrolledCount}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 pt-6">
              <Hash className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">{t("capacity")}</p>
                <p className="text-2xl font-bold">{classData.capacity || "—"}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Year selector + roster table */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t("title")}</h2>
            <div className="w-64">
              <Select
                options={yearOptions}
                placeholder={t("allYears")}
                value={selectedYearId}
                onChange={(e) => setSelectedYearId(e.target.value)}
              />
            </div>
          </div>

          {enrollError && (
            <ErrorAlert message={enrollError.message} requestId={enrollError.requestId} details={enrollError.details} />
          )}

          {enrollLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : !enrollments || enrollments.length === 0 ? (
            <EmptyState
              icon={Users}
              title={t("noStudents")}
              description={t("noStudentsDescription")}
            />
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("studentName")}</TableHead>
                    <TableHead>{t("admissionNumber")}</TableHead>
                    <TableHead>{t("status")}</TableHead>
                    <TableHead>{t("enrolledAt")}</TableHead>
                    <TableHead className="w-[100px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {enrollments.map((e: Enrollment) => {
                    const s = studentMap.get(e.student_id);
                    return (
                      <TableRow key={e.id}>
                        <TableCell className="font-medium">
                          <a
                            href={`/students/${e.student_id}`}
                            className="text-primary hover:underline"
                          >
                            {s ? `${s.first_name} ${s.last_name}` : e.student_id}
                          </a>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {s?.admission_number || "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={e.status === "active" ? "default" : "secondary"}>
                            {e.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {new Date(e.enrolled_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              window.location.href = `/students/${e.student_id}`;
                            }}
                          >
                            {t("viewStudent")}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>
    </RouteGuard>
  );
}
