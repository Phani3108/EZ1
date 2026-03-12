/**
 * Students directory — table + search + filters + drawer create/edit.
 * Permission: student:read (view), student:write (create/edit)
 */

"use client";

import React, { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge, Input, Label, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Student } from "@eduzim/api-client";
import { student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Plus, Pencil, Users, Eye, Upload } from "lucide-react";

// ─── Zod Schema ───

const studentSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(50),
  last_name: z.string().min(1, "Last name is required").max(50),
  date_of_birth: z.string().optional().or(z.literal("")),
  gender: z.string().optional().or(z.literal("")),
  admission_number: z.string().optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type StudentFormData = z.infer<typeof studentSchema>;

// ─── Page ───

export default function StudentsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Student | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");

  const { data: students, isLoading, error, refetch } = useApiQuery(
    () => studentApi.list(),
    [],
  );

  const createMutation = useApiMutation(
    (data: StudentFormData) => studentApi.create(data),
    { onSuccess: () => { setDrawerOpen(false); refetch(); } },
  );

  const updateMutation = useApiMutation(
    (args: { id: string; data: StudentFormData }) =>
      studentApi.update(args.id, args.data),
    { onSuccess: () => { setDrawerOpen(false); setEditing(null); refetch(); } },
  );

  const openCreate = () => { setEditing(null); setDrawerOpen(true); };
  const openEdit = (s: Student) => { setEditing(s); setDrawerOpen(true); };

  // Client-side filtering
  const filtered = useMemo(() => {
    if (!students) return [];
    let list = students;
    if (statusFilter === "active") list = list.filter((s) => s.is_active);
    if (statusFilter === "inactive") list = list.filter((s) => !s.is_active);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) =>
          s.first_name.toLowerCase().includes(q) ||
          s.last_name.toLowerCase().includes(q) ||
          (s.admission_number?.toLowerCase().includes(q) ?? false),
      );
    }
    return list;
  }, [students, search, statusFilter]);

  return (
    <RouteGuard permissions={["student:read"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader title="Students" description="View and manage student records.">
          <Link href="/students/import">
            <Button variant="outline" className="flex items-center gap-2">
              <Upload className="h-4 w-4" /> Import CSV
            </Button>
          </Link>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" /> Add Student
          </Button>
        </PageHeader>

        {/* Filters bar */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name or admission #…"
            className="sm:w-80"
          />
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "inactive")}
            className="w-40"
            options={[
              { value: "all", label: "All Status" },
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
          />
        </div>

        {error && (
          <ErrorAlert
            message={error.message}
            requestId={error.requestId}
            details={error.details}
          />
        )}

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Users}
            title={search || statusFilter !== "all" ? "No students match your filters" : "No students yet"}
            description={search || statusFilter !== "all" ? "Try a different search or filter." : "Add your first student to get started."}
          >
            {!search && statusFilter === "all" && (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4 mr-1" /> Add Student
              </Button>
            )}
          </EmptyState>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Admission #</TableHead>
                  <TableHead>Gender</TableHead>
                  <TableHead>Date of Birth</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">
                      <Link
                        href={`/students/${s.id}`}
                        className="text-primary hover:underline"
                      >
                        {s.first_name} {s.last_name}
                      </Link>
                    </TableCell>
                    <TableCell>{s.admission_number || "—"}</TableCell>
                    <TableCell className="capitalize">{s.gender || "—"}</TableCell>
                    <TableCell>{s.date_of_birth || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={s.is_active ? "default" : "secondary"}>
                        {s.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Link href={`/students/${s.id}`}>
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(s)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Create / Edit Drawer */}
        <Sheet open={drawerOpen} onClose={() => { setDrawerOpen(false); setEditing(null); }}>
          <SheetHeader>
            <SheetTitle>{editing ? "Edit Student" : "Add Student"}</SheetTitle>
            <SheetDescription>
              {editing ? "Update student information." : "Register a new student."}
            </SheetDescription>
          </SheetHeader>
          <StudentForm
            initial={editing}
            isSubmitting={createMutation.isSubmitting || updateMutation.isSubmitting}
            error={createMutation.error || updateMutation.error}
            onSubmit={(data) =>
              editing
                ? updateMutation.mutate({ id: editing.id, data })
                : createMutation.mutate(data)
            }
            onCancel={() => { setDrawerOpen(false); setEditing(null); }}
          />
        </Sheet>
      </div>
    </RouteGuard>
  );
}

// ─── Form ───

function StudentForm({
  initial,
  isSubmitting,
  error,
  onSubmit,
  onCancel,
}: {
  initial: Student | null;
  isSubmitting: boolean;
  error: { message: string; requestId: string | null; details: Record<string, unknown> | null } | null;
  onSubmit: (data: StudentFormData) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<StudentFormData>({
    resolver: zodResolver(studentSchema),
    defaultValues: {
      first_name: initial?.first_name ?? "",
      last_name: initial?.last_name ?? "",
      date_of_birth: initial?.date_of_birth ?? "",
      gender: initial?.gender ?? "",
      admission_number: initial?.admission_number ?? "",
      is_active: initial?.is_active ?? true,
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <SheetBody>
        {error && (
          <ErrorAlert
            message={error.message}
            requestId={error.requestId}
            details={error.details}
            className="mb-4"
          />
        )}

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="first_name">First Name *</Label>
              <Input id="first_name" {...register("first_name")} />
              {errors.first_name && (
                <p className="mt-1 text-xs text-destructive">{errors.first_name.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="last_name">Last Name *</Label>
              <Input id="last_name" {...register("last_name")} />
              {errors.last_name && (
                <p className="mt-1 text-xs text-destructive">{errors.last_name.message}</p>
              )}
            </div>
          </div>

          <div>
            <Label htmlFor="admission_number">Admission Number</Label>
            <Input id="admission_number" {...register("admission_number")} placeholder="e.g. ADM-2025-001" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input id="date_of_birth" type="date" {...register("date_of_birth")} />
            </div>
            <div>
              <Label htmlFor="gender">Gender</Label>
              <Select
                id="gender"
                {...register("gender")}
                placeholder="— Select —"
                options={[
                  { value: "male", label: "Male" },
                  { value: "female", label: "Female" },
                  { value: "other", label: "Other" },
                ]}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_active" {...register("is_active")} className="h-4 w-4" />
            <Label htmlFor="is_active">Active</Label>
          </div>
        </div>
      </SheetBody>
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : initial ? "Update" : "Create"}
        </Button>
      </SheetFooter>
    </form>
  );
}
