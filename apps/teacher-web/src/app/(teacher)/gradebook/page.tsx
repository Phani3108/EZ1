/**
 * Gradebook — Phase 11c / T-015.
 *
 * Cross-assessment view: pick a class, a term, optionally a subject,
 * and see a matrix of every student in the class against every
 * assessment in the term. Each cell shows the mark; the rightmost
 * column shows the running average %.
 *
 * The student list is drawn from the class roster (the same API the
 * attendance and roster tabs use), then joined locally with the sparse
 * grade matrix returned by `assessment.classGradebook`. Students with
 * no marks yet still show up as empty rows so the teacher sees the
 * full class.
 */

"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { BookOpen, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher, student, assessment } from "@/lib/api";
import type {
  TeacherClass,
  Enrollment,
  Student as StudentType,
  ClassGradebook,
} from "@eduzim/api-client";

export default function GradebookIndexPage() {
  const t = useTranslations("gradebook");
  const { data: classes, isLoading } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    [],
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
      <p className="text-sm text-muted-foreground">{t("description")}</p>

      {isLoading && (
        <Card className="animate-pulse">
          <CardContent className="p-4 h-16" />
        </Card>
      )}

      {!isLoading && (!classes || classes.length === 0) && (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            {t("noClasses")}
          </CardContent>
        </Card>
      )}

      <ul className="space-y-2" data-testid="gradebook-class-list">
        {classes?.map((c) => (
          <li key={c.id}>
            <Link href={`/gradebook/${c.id}`}>
              <Card className="hover:bg-muted/30 transition-colors cursor-pointer">
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <BookOpen className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.name}</p>
                    <p className="text-xs text-muted-foreground">{c.section}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
