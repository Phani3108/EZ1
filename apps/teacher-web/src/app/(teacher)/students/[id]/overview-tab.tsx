/**
 * Overview Tab — Student basic info display with attendance risk badge.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { UserCircle } from "lucide-react";
import type { Student, DropoutStudentDetail } from "@eduzim/api-client";
import { RiskBadge } from "@/components/risk-badge";

interface OverviewTabProps {
  student: Student | null | undefined;
  isLoading: boolean;
  riskDetail?: DropoutStudentDetail | null;
}

export function OverviewTab({ student, isLoading, riskDetail }: OverviewTabProps) {
  const t = useTranslations("students");

  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 bg-muted rounded-full" />
            <div className="space-y-2 flex-1">
              <div className="h-5 w-48 bg-muted rounded" />
              <div className="h-4 w-32 bg-muted rounded" />
            </div>
          </div>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-24 bg-muted rounded" />
              <div className="h-4 w-32 bg-muted rounded" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!student) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <UserCircle className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            {t("studentNotFound")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const fields = [
    { label: t("firstName"), value: student.first_name },
    { label: t("lastName"), value: student.last_name },
    { label: t("admissionNo"), value: student.student_code || "—" },
    {
      label: t("dateOfBirth"),
      value: student.dob
        ? new Date(student.dob).toLocaleDateString()
        : "—",
    },
    { label: t("gender"), value: student.gender || "—" },
    {
      label: t("admissionDate"),
      value: student.admission_date
        ? new Date(student.admission_date).toLocaleDateString()
        : "—",
    },
    { label: t("status"), value: student.status || "—" },
  ];

  return (
    <Card>
      <CardContent className="p-6">
        {/* Avatar + Name + Risk Badge */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <UserCircle className="h-8 w-8 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-lg font-semibold">
              {student.first_name} {student.last_name}
            </p>
            {student.student_code && (
              <p className="text-sm text-muted-foreground">
                {student.student_code}
              </p>
            )}
          </div>
          {riskDetail && riskDetail.risk_score > 0 && (
            <RiskBadge
              score={riskDetail.risk_score}
              band={riskDetail.risk_band as "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"}
              size="md"
            />
          )}
        </div>

        {/* Attendance risk signals (fees hidden for teachers) */}
        {riskDetail && riskDetail.signals && riskDetail.signals.length > 0 && (
          <div className="mb-6 rounded-lg border bg-muted/30 p-4" data-testid="risk-signals">
            <p className="text-sm font-medium mb-2">{t("riskSignals")}</p>
            <div className="space-y-1.5">
              {riskDetail.signals
                .filter((s) => !s.code.startsWith("FEE_"))
                .map((signal) => (
                  <div key={signal.code} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{signal.label}</span>
                    <span className="font-medium">+{signal.points}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Info grid */}
        <div className="space-y-3 divide-y">
          {fields.map((f) => (
            <div
              key={f.label}
              className="flex items-center justify-between pt-3 first:pt-0"
            >
              <span className="text-sm text-muted-foreground">{f.label}</span>
              <span className="text-sm font-medium">{f.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
