/**
 * Classes — CRUD page with Sheet drawer.
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
  ExportMenu,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { SchoolClass } from "@eduzim/api-client";
import { school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { Plus, Pencil, Trash2 } from "lucide-react";

// ─── Zod Schema ───

const classSchema = z.object({
  name: z.string().min(1, "Name is required").max(50),
  grade_level: z.coerce.number().int().min(0, "Must be 0 or above").max(20, "Must be 20 or below"),
  capacity: z.coerce.number().int().min(1, "Minimum 1").max(200, "Maximum 200").optional().or(z.literal("")),
  academic_year_id: z.string().optional(),
  is_active: z.boolean().default(true),
});

type ClassFormData = z.infer<typeof classSchema>;

// ─── Page ───

export default function ClassesPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<SchoolClass | null>(null);

  const { data: classes, isLoading, error, refetch } = useApiQuery(
    () => school.listClasses(),
    []
  );

  const deleteMutation = useApiMutation(
    (id: string) => school.deleteClass(id),
    { onSuccess: () => refetch() }
  );

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  const openEdit = (cls: SchoolClass) => {
    setEditing(cls);
    setDrawerOpen(true);
  };

  const handleSaved = useCallback(() => {
    setDrawerOpen(false);
    setEditing(null);
    refetch();
  }, [refetch]);

  const handleDelete = (cls: SchoolClass) => {
    if (confirm(`Delete class "${cls.name}"? This cannot be undone.`)) {
      deleteMutation.mutate(cls.id);
    }
  };

  return (
    <RouteGuard permissions={["school:manage"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Classes</h1>
            <p className="text-sm text-muted-foreground">
              Manage school classes and grade levels.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ExportMenu
              filename="classes"
              title="Classes"
              subtitle={`${classes?.length ?? 0} class(es)`}
              columns={[
                { key: "name",        label: "Name",        width: 18 },
                { key: "grade_level", label: "Grade level", width: 12 },
                { key: "capacity",    label: "Capacity",    width: 10 },
                { key: (c: SchoolClass) => (c.is_active ? "Active" : "Inactive"), label: "Status", width: 10 },
              ]}
              rows={classes ?? []}
            />
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              New Class
            </Button>
          </div>
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
                  <TableHead>Grade Level</TableHead>
                  <TableHead>Capacity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(!classes || classes.length === 0) ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      No classes found. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  classes.map((cls) => (
                    <TableRow key={cls.id}>
                      <TableCell className="font-medium">
                        <a href={`/classes/${cls.id}`} className="text-primary hover:underline">
                          {cls.name}
                        </a>
                      </TableCell>
                      <TableCell>{cls.grade_level}</TableCell>
                      <TableCell>{cls.capacity || "—"}</TableCell>
                      <TableCell>
                        <Badge variant="success">Active</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEdit(cls)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(cls)}
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

        <ClassDrawer
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

function ClassDrawer({
  open,
  onClose,
  editing,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editing: SchoolClass | null;
  onSaved: () => void;
}) {
  const isEdit = !!editing;

  const { register, handleSubmit, formState: { errors }, reset } = useForm<ClassFormData>({
    resolver: zodResolver(classSchema),
    defaultValues: editing
      ? { name: editing.name, grade_level: editing.grade_level, capacity: editing.capacity ?? undefined, is_active: true }
      : { name: "", grade_level: 1, capacity: 40, is_active: true },
  });

  React.useEffect(() => {
    if (open) {
      reset(
        editing
          ? { name: editing.name, grade_level: editing.grade_level, capacity: editing.capacity ?? undefined, is_active: true }
          : { name: "", grade_level: 1, capacity: 40, is_active: true }
      );
    }
  }, [editing, open, reset]);

  const createMutation = useApiMutation(
    (data: ClassFormData) => school.createClass({ ...data, capacity: data.capacity ? Number(data.capacity) : undefined }),
    { onSuccess: onSaved }
  );

  const updateMutation = useApiMutation(
    (data: ClassFormData) => school.updateClass(editing!.id, { ...data, capacity: data.capacity ? Number(data.capacity) : undefined }),
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
          <SheetTitle>{isEdit ? "Edit Class" : "New Class"}</SheetTitle>
          <SheetDescription>
            {isEdit ? "Update class details." : "Create a new class."}
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
            <Label htmlFor="name" required>Class Name</Label>
            <Input
              id="name"
              placeholder="e.g. Grade 6A"
              error={errors.name?.message}
              {...register("name")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="grade_level" required>Grade Level</Label>
            <Input
              id="grade_level"
              type="number"
              min={0}
              max={20}
              error={errors.grade_level?.message}
              {...register("grade_level")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="capacity">Capacity</Label>
            <Input
              id="capacity"
              type="number"
              min={1}
              max={200}
              placeholder="Optional"
              error={errors.capacity?.message}
              {...register("capacity")}
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
