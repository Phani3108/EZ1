/**
 * Enrollments — list all class enrollments with student + class details.
 * Allows assigning a student to a class (create enrollment).
 * Permission: student:write
 */

"use client";

import React, { useState, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge, Label, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Enrollment } from "@eduzim/api-client";
import { student as studentApi, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Plus, BookOpen } from "lucide-react";

const enrollSchema = z.object({
  student_id: z.string().min(1, "Select a student"),
  class_id: z.string().min(1, "Select a class"),
  academic_year_id: z.string().min(1, "Select academic year"),
});
type EnrollForm = z.infer<typeof enrollSchema>;

export default function EnrollmentsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data: enrollments, isLoading, error, refetch } = useApiQuery(
    () => studentApi.listEnrollments({}),
    [],
  );
  const { data: students } = useApiQuery(() => studentApi.list(), []);
  const { data: classes } = useApiQuery(() => school.listClasses(), []);
  const { data: academicYears } = useApiQuery(() => school.listAcademicYears(), []);

  const createMutation = useApiMutation(
    (data: EnrollForm) => studentApi.createEnrollment(data),
    { onSuccess: () => { setDrawerOpen(false); refetch(); } },
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EnrollForm>({
    resolver: zodResolver(enrollSchema),
    defaultValues: { academic_year_id: "ay-001" },
  });

  const openCreate = () => { reset({ academic_year_id: "ay-001" }); setDrawerOpen(true); };

  const studentMap = useMemo(() => {
    const m: Record<string, string> = {};
    (students ?? []).forEach((s) => { m[s.id] = `${s.first_name} ${s.last_name} (${s.student_code})`; });
    return m;
  }, [students]);

  const classMap = useMemo(() => {
    const m: Record<string, string> = {};
    (classes ?? []).forEach((c) => { m[c.id] = c.name; });
    return m;
  }, [classes]);

  const filtered = useMemo(() => {
    if (!enrollments) return [];
    if (!search) return enrollments;
    const q = search.toLowerCase();
    return (enrollments as Enrollment[]).filter(
      (e) =>
        (studentMap[e.student_id] ?? "").toLowerCase().includes(q) ||
        (classMap[e.class_id] ?? "").toLowerCase().includes(q),
    );
  }, [enrollments, search, studentMap, classMap]);

  return (
    <RouteGuard permissions={["student:write"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader
          title="Enrollments"
          description={`${enrollments?.length ?? 0} students enrolled`}
        >
          <Button onClick={openCreate} className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Enroll Student
          </Button>
        </PageHeader>

        <SearchInput value={search} onChange={setSearch} placeholder="Search student or class…" />

        {error && <ErrorAlert message={error.message} />}

        {isLoading ? (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">Loading…</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={BookOpen} title="No enrollments found" description="Enroll students into classes to get started." />
        ) : (
          <div className="rounded-lg border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Enrolled</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-medium">
                      {studentMap[e.student_id] ?? e.student_id}
                    </TableCell>
                    <TableCell>{classMap[e.class_id] ?? e.class_id}</TableCell>
                    <TableCell>
                      <Badge variant={e.status === "active" ? "success" : "secondary"}>
                        {e.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(e.enrolled_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Sheet open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <SheetHeader>
            <SheetTitle>Enroll Student</SheetTitle>
            <SheetDescription>Assign a student to a class for the current academic year.</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form id="enroll-form" onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
              <div>
                <Label htmlFor="student_id">Student</Label>
                <Select id="student_id" {...register("student_id")}>
                  <option value="">— Select student —</option>
                  {(students ?? []).map((s) => (
                    <option key={s.id} value={s.id}>{s.first_name} {s.last_name} ({s.student_code})</option>
                  ))}
                </Select>
                {errors.student_id && <p className="mt-1 text-xs text-red-600">{errors.student_id.message}</p>}
              </div>
              <div>
                <Label htmlFor="class_id">Class</Label>
                <Select id="class_id" {...register("class_id")}>
                  <option value="">— Select class —</option>
                  {(classes ?? []).map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </Select>
                {errors.class_id && <p className="mt-1 text-xs text-red-600">{errors.class_id.message}</p>}
              </div>
              <div>
                <Label htmlFor="academic_year_id">Academic Year</Label>
                <Select id="academic_year_id" {...register("academic_year_id")}>
                  {(academicYears ?? []).map((y) => (
                    <option key={y.id} value={y.id}>{y.name}</option>
                  ))}
                </Select>
                {errors.academic_year_id && <p className="mt-1 text-xs text-red-600">{errors.academic_year_id.message}</p>}
              </div>
              {createMutation.error && <ErrorAlert message={createMutation.error.message} />}
            </form>
          </SheetBody>
          <SheetFooter>
            <Button variant="outline" onClick={() => setDrawerOpen(false)}>Cancel</Button>
            <Button type="submit" form="enroll-form" disabled={isSubmitting || createMutation.isSubmitting}>
              {createMutation.isSubmitting ? "Enrolling…" : "Enroll"}
            </Button>
          </SheetFooter>
        </Sheet>
      </div>
    </RouteGuard>
  );
}
