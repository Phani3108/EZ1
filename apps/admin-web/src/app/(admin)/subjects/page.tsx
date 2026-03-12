/**
 * Subjects — CRUD page with Sheet drawer.
 * Permission: school:manage
 */

"use client";

import React, { useState, useCallback } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge, Input, Label, Switch,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Subject } from "@eduzim/api-client";
import { school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { Plus, Pencil, Trash2 } from "lucide-react";

// ─── Zod Schema ───

const subjectSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20, "Code too long"),
  description: z.string().max(500).optional().or(z.literal("")),
  is_active: z.boolean().default(true),
});

type SubjectFormData = z.infer<typeof subjectSchema>;

// ─── Page ───

export default function SubjectsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Subject | null>(null);

  const { data: subjects, isLoading, error, refetch } = useApiQuery(
    () => school.listSubjects(),
    []
  );

  const deleteMutation = useApiMutation(
    (id: string) => school.deleteSubject(id),
    { onSuccess: () => refetch() }
  );

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  const openEdit = (subject: Subject) => {
    setEditing(subject);
    setDrawerOpen(true);
  };

  const handleSaved = useCallback(() => {
    setDrawerOpen(false);
    setEditing(null);
    refetch();
  }, [refetch]);

  const handleDelete = (subject: Subject) => {
    if (confirm(`Delete subject "${subject.name}" (${subject.code})? This cannot be undone.`)) {
      deleteMutation.mutate(subject.id);
    }
  };

  return (
    <RouteGuard permissions={["school:manage"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Subjects</h1>
            <p className="text-sm text-muted-foreground">
              Manage subjects offered at your school.
            </p>
          </div>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New Subject
          </Button>
        </div>

        {error && (
          <ErrorAlert
            message={error.message}
            requestId={error.requestId}
            details={error.details}
          />
        )}

        {deleteMutation.error && (
          <ErrorAlert
            message={deleteMutation.error.message}
            requestId={deleteMutation.error.requestId}
            details={deleteMutation.error.details}
            onDismiss={deleteMutation.clearError}
          />
        )}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(!subjects || subjects.length === 0) ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      No subjects found. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  subjects.map((subject) => (
                    <TableRow key={subject.id}>
                      <TableCell className="font-medium">{subject.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{subject.code}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-muted-foreground">
                        {subject.description || "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="success">Active</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEdit(subject)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(subject)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}

        <SubjectDrawer
          open={drawerOpen}
          onClose={() => { setDrawerOpen(false); setEditing(null); }}
          editing={editing}
          onSaved={handleSaved}
        />
      </div>
    </RouteGuard>
  );
}

// ─── Drawer Form ───

function SubjectDrawer({
  open,
  onClose,
  editing,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editing: Subject | null;
  onSaved: () => void;
}) {
  const isEdit = !!editing;

  const { register, handleSubmit, formState: { errors }, reset } = useForm<SubjectFormData>({
    resolver: zodResolver(subjectSchema),
    defaultValues: editing
      ? { name: editing.name, code: editing.code, description: editing.description ?? "", is_active: true }
      : { name: "", code: "", description: "", is_active: true },
  });

  React.useEffect(() => {
    if (open) {
      reset(
        editing
          ? { name: editing.name, code: editing.code, description: editing.description ?? "", is_active: true }
          : { name: "", code: "", description: "", is_active: true }
      );
    }
  }, [editing, open, reset]);

  const createMutation = useApiMutation(
    (data: SubjectFormData) => school.createSubject({ ...data, description: data.description || undefined }),
    { onSuccess: onSaved }
  );

  const updateMutation = useApiMutation(
    (data: SubjectFormData) => school.updateSubject(editing!.id, { ...data, description: data.description || undefined }),
    { onSuccess: onSaved }
  );

  const mutation = isEdit ? updateMutation : createMutation;

  const onSubmit = handleSubmit((data) => {
    mutation.mutate(data);
  });

  return (
    <Sheet open={open} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col h-full">
        <SheetHeader>
          <SheetTitle>{isEdit ? "Edit Subject" : "New Subject"}</SheetTitle>
          <SheetDescription>
            {isEdit ? "Update subject details." : "Create a new subject."}
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-4">
          {mutation.error && (
            <ErrorAlert
              message={mutation.error.message}
              requestId={mutation.error.requestId}
              details={mutation.error.details}
              onDismiss={mutation.clearError}
            />
          )}

          <div className="space-y-2">
            <Label htmlFor="name" required>Subject Name</Label>
            <Input
              id="name"
              placeholder="e.g. Mathematics"
              error={errors.name?.message}
              {...register("name")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="code" required>Subject Code</Label>
            <Input
              id="code"
              placeholder="e.g. MATH"
              error={errors.code?.message}
              {...register("code")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              placeholder="Optional description"
              error={errors.description?.message}
              {...register("description")}
            />
          </div>

          <div className="flex items-center gap-2">
            <Switch id="is_active" {...register("is_active")} defaultChecked />
            <Label htmlFor="is_active">Active</Label>
          </div>
        </SheetBody>

        <SheetFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isSubmitting}>
            {isEdit ? "Update" : "Create"}
          </Button>
        </SheetFooter>
      </form>
    </Sheet>
  );
}
