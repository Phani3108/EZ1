/**
 * Assessments — view all assessments across classes & subjects.
 * Teachers can create assessments; admin can view all.
 * Permission: assessment:read
 */

"use client";

import React, { useState, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge, Input, Label, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard, useAuth } from "@eduzim/auth";
import type { Assessment } from "@eduzim/api-client";
import { assessment as assessmentApi, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Plus, ClipboardList, ExternalLink } from "lucide-react";
import Link from "next/link";

const assessmentSchema = z.object({
  name: z.string().min(2, "Name is required"),
  subject_id: z.string().min(1, "Select a subject"),
  class_id: z.string().min(1, "Select a class"),
  assessment_type: z.enum(["TEST", "QUIZ", "EXAM", "ASSIGNMENT"]),
  date: z.string().min(1, "Date is required"),
  max_marks: z.coerce.number().min(1).max(1000),
  term_id: z.string().min(1, "Select a term"),
  academic_year_id: z.string().default("ay-001"),
});
type AssessmentForm = z.infer<typeof assessmentSchema>;

const TYPE_COLORS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  TEST: "default",
  QUIZ: "secondary",
  EXAM: "destructive",
  ASSIGNMENT: "outline",
};

export default function AssessmentsPage() {
  const { hasPermission } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const { data: assessments, isLoading, error, refetch } = useApiQuery(
    () => assessmentApi.list({ class_id: "", term_id: "" }),
    [],
  );
  const { data: subjects } = useApiQuery(() => school.listSubjects(), []);
  const { data: classes } = useApiQuery(() => school.listClasses(), []);
  const { data: terms } = useApiQuery(() => school.listTerms(), []);

  const canWrite = hasPermission("assessment:write");

  const createMutation = useApiMutation(
    (data: AssessmentForm) => assessmentApi.create(data),
    { onSuccess: () => { setDrawerOpen(false); refetch(); } },
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<AssessmentForm>({
    resolver: zodResolver(assessmentSchema),
    defaultValues: { assessment_type: "TEST", max_marks: 100, academic_year_id: "ay-001" },
  });

  const subjectMap = useMemo(() => {
    const m: Record<string, string> = {};
    (subjects ?? []).forEach((s) => { m[s.id] = s.name; });
    return m;
  }, [subjects]);

  const classMap = useMemo(() => {
    const m: Record<string, string> = {};
    (classes ?? []).forEach((c) => { m[c.id] = c.name; });
    return m;
  }, [classes]);

  const filtered = useMemo(() => {
    if (!assessments) return [];
    let list = assessments as Assessment[];
    if (typeFilter !== "all") list = list.filter((a) => a.assessment_type === typeFilter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          (subjectMap[a.subject_id] ?? "").toLowerCase().includes(q) ||
          (classMap[a.class_id] ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [assessments, typeFilter, search, subjectMap, classMap]);

  return (
    <RouteGuard permissions={["assessment:read"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader
          title="Assessments"
          description={`${assessments?.length ?? 0} assessments recorded`}
        >
          {canWrite && (
            <Button onClick={() => { reset(); setDrawerOpen(true); }} className="flex items-center gap-2">
              <Plus className="h-4 w-4" /> New Assessment
            </Button>
          )}
        </PageHeader>

        <div className="flex flex-col sm:flex-row gap-3">
          <SearchInput value={search} onChange={setSearch} placeholder="Search assessments…" />
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter((e.target as HTMLSelectElement).value)}
            className="w-full sm:w-48"
          >
            <option value="all">All types</option>
            <option value="TEST">Test</option>
            <option value="QUIZ">Quiz</option>
            <option value="EXAM">Exam</option>
            <option value="ASSIGNMENT">Assignment</option>
          </Select>
        </div>

        {error && <ErrorAlert message={error.message} />}

        {isLoading ? (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">Loading…</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={ClipboardList} title="No assessments found" description="Create an assessment to start capturing student marks." />
        ) : (
          <div className="rounded-lg border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Assessment</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Max</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.name}</TableCell>
                    <TableCell>
                      <Badge variant={TYPE_COLORS[a.assessment_type] ?? "outline"}>
                        {a.assessment_type}
                      </Badge>
                    </TableCell>
                    <TableCell>{classMap[a.class_id] ?? a.class_id}</TableCell>
                    <TableCell>{subjectMap[a.subject_id] ?? a.subject_id}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{a.date}</TableCell>
                    <TableCell className="text-muted-foreground">{a.max_marks}</TableCell>
                    <TableCell>
                      <Link href={`/assessments/${a.id}`} className="flex items-center gap-1 text-xs text-primary hover:underline">
                        Marks <ExternalLink className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Sheet open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <SheetHeader>
            <SheetTitle>New Assessment</SheetTitle>
            <SheetDescription>Create a test, quiz or exam for a class.</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form id="assessment-form" onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
              <div>
                <Label htmlFor="name">Assessment Name</Label>
                <Input id="name" {...register("name")} placeholder="e.g. Mathematics — Test 1" />
                {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="assessment_type">Type</Label>
                  <Select id="assessment_type" {...register("assessment_type")}>
                    <option value="TEST">Test</option>
                    <option value="QUIZ">Quiz</option>
                    <option value="EXAM">Exam</option>
                    <option value="ASSIGNMENT">Assignment</option>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="max_marks">Max Marks</Label>
                  <Input id="max_marks" type="number" {...register("max_marks")} defaultValue={100} />
                  {errors.max_marks && <p className="mt-1 text-xs text-red-600">{errors.max_marks.message}</p>}
                </div>
              </div>
              <div>
                <Label htmlFor="class_id">Class</Label>
                <Select id="class_id" {...register("class_id")}>
                  <option value="">— Select class —</option>
                  {(classes ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
                {errors.class_id && <p className="mt-1 text-xs text-red-600">{errors.class_id.message}</p>}
              </div>
              <div>
                <Label htmlFor="subject_id">Subject</Label>
                <Select id="subject_id" {...register("subject_id")}>
                  <option value="">— Select subject —</option>
                  {(subjects ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </Select>
                {errors.subject_id && <p className="mt-1 text-xs text-red-600">{errors.subject_id.message}</p>}
              </div>
              <div>
                <Label htmlFor="term_id">Term</Label>
                <Select id="term_id" {...register("term_id")}>
                  <option value="">— Select term —</option>
                  {(terms ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </Select>
                {errors.term_id && <p className="mt-1 text-xs text-red-600">{errors.term_id.message}</p>}
              </div>
              <div>
                <Label htmlFor="date">Date</Label>
                <Input id="date" type="date" {...register("date")} />
                {errors.date && <p className="mt-1 text-xs text-red-600">{errors.date.message}</p>}
              </div>
              {createMutation.error && <ErrorAlert message={createMutation.error.message} />}
            </form>
          </SheetBody>
          <SheetFooter>
            <Button variant="outline" onClick={() => setDrawerOpen(false)}>Cancel</Button>
            <Button type="submit" form="assessment-form" disabled={isSubmitting || createMutation.isSubmitting}>
              {createMutation.isSubmitting ? "Creating…" : "Create"}
            </Button>
          </SheetFooter>
        </Sheet>
      </div>
    </RouteGuard>
  );
}
