/**
 * Roster Tab — Read-only list of enrolled students with view link.
 */

"use client";

import React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent, ExportMenu } from "@eduzim/ui";
import { Users, Eye } from "lucide-react";
import type { Enrollment, Student } from "@eduzim/api-client";

interface RosterTabProps {
  rosterStudents: { enrollment: Enrollment; student: Student }[];
  isLoading: boolean;
  classId?: string;
}

export function RosterTab({ rosterStudents, isLoading, classId }: RosterTabProps) {
  const t = useTranslations("classes");

  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <CardContent className="p-4">
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-8 w-8 bg-muted rounded-full" />
                <div className="flex-1">
                  <div className="h-4 w-32 bg-muted rounded mb-1" />
                  <div className="h-3 w-20 bg-muted rounded" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (rosterStudents.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <Users className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">{t("rosterEmpty")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
          <span className="text-xs font-medium text-muted-foreground">
            {rosterStudents.length} {rosterStudents.length === 1 ? "student" : "students"}
          </span>
          <ExportMenu
            filename="class-roster"
            title="Class Roster"
            subtitle={`${rosterStudents.length} student(s)`}
            columns={[
              { key: (r) => r.student.first_name, label: "First name", width: 16 },
              { key: (r) => r.student.last_name,  label: "Last name",  width: 16 },
              { key: (r) => r.student.admission_number ?? "—", label: "Admission #", width: 14 },
              { key: (r) => r.student.gender ?? "—", label: "Gender", width: 8 },
              { key: (r) => r.student.date_of_birth ?? "—", label: "DOB", width: 14 },
              { key: (r) => new Date(r.enrollment.enrolled_at).toLocaleDateString(), label: "Enrolled", width: 14 },
            ]}
            rows={rosterStudents}
            variant="compact"
          />
        </div>
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
                <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden sm:table-cell">
                  {t("admissionNo")}
                </th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground hidden md:table-cell">
                  {t("enrolledAt")}
                </th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                  {t("viewStudent")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rosterStudents.map((r, idx) => (
                <tr
                  key={r.enrollment.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-4 py-3 text-muted-foreground">
                    {idx + 1}
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {r.student.first_name} {r.student.last_name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden sm:table-cell">
                    {r.student.admission_number || "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                    {new Date(r.enrollment.enrolled_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/students/${r.student.id}?classId=${classId || r.enrollment.class_id}`}
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">{t("view")}</span>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-2 text-xs text-muted-foreground border-t">
          {rosterStudents.length} {rosterStudents.length === 1 ? "student" : "students"}
        </div>
      </CardContent>
    </Card>
  );
}
