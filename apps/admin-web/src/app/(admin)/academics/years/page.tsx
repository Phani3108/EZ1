/**
 * Academic Years — CRUD page with Sheet drawer.
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
import type { AcademicYear } from "@eduzim/api-client";
import { school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { Plus, Pencil } from "lucide-react";

// ─── Zod Schema ───

const academicYearSchema = z.object({
  name: z.string().min(1, "Name is required").max(50, "Name too long"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  is_current: z.boolean().default(false),
}).refine((d) => !d.start_date || !d.end_date || d.start_date < d.end_date, {
  message: "End date must be after start date",
  path: ["end_date"],
});

type AcademicYearFormData = z.infer<typeof academicYearSchema>;

// ─── Page ───

export default function AcademicYearsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<AcademicYear | null>(null);

  const { data: years, isLoading, error, refetch } = useApiQuery(
    () => school.listAcademicYears(),
    []
  );

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  const openEdit = (year: AcademicYear) => {
    setEditing(year);
    setDrawerOpen(true);
  };

  const handleSaved = useCallback(() => {
    setDrawerOpen(false);
    setEditing(null);
    refetch();
  }, [refetch]);

  return (
    <RouteGuard permissions={["school:manage"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Academic Years</h1>
            <p className="text-sm text-muted-foreground">
              Manage academic years for your school.
            </p>
          </div>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New Academic Year
          </Button>
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
                  <TableHead>Start Date</TableHead>
                  <TableHead>End Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(!years || years.length === 0) ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      No academic years found. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  years.map((year) => (
                    <TableRow key={year.id}>
                      <TableCell className="font-medium">{year.name}</TableCell>
                      <TableCell>{year.start_date}</TableCell>
                      <TableCell>{year.end_date}</TableCell>
                      <TableCell>
                        <Badge variant={year.is_current ? "success" : "secondary"}>
                          {year.is_current ? "Current" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(year)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}

        <AcademicYearDrawer
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

function AcademicYearDrawer({
  open,
  onClose,
  editing,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editing: AcademicYear | null;
  onSaved: () => void;
}) {
  const isEdit = !!editing;

  const { register, handleSubmit, formState: { errors }, reset } = useForm<AcademicYearFormData>({
    resolver: zodResolver(academicYearSchema),
    defaultValues: editing
      ? { name: editing.name, start_date: editing.start_date, end_date: editing.end_date, is_current: editing.is_current }
      : { name: "", start_date: "", end_date: "", is_current: false },
  });

  // Reset form when editing changes
  React.useEffect(() => {
    if (open) {
      reset(
        editing
          ? { name: editing.name, start_date: editing.start_date, end_date: editing.end_date, is_current: editing.is_current }
          : { name: "", start_date: "", end_date: "", is_current: false }
      );
    }
  }, [editing, open, reset]);

  const createMutation = useApiMutation(
    (data: AcademicYearFormData) => school.createAcademicYear(data),
    { onSuccess: onSaved }
  );

  const updateMutation = useApiMutation(
    (data: AcademicYearFormData) => school.updateAcademicYear(editing!.id, data),
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
          <SheetTitle>{isEdit ? "Edit Academic Year" : "New Academic Year"}</SheetTitle>
          <SheetDescription>
            {isEdit ? "Update the academic year details." : "Create a new academic year."}
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
            <Label htmlFor="name" required>Name</Label>
            <Input
              id="name"
              placeholder="e.g. 2025"
              error={errors.name?.message}
              {...register("name")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="start_date" required>Start Date</Label>
            <Input
              id="start_date"
              type="date"
              error={errors.start_date?.message}
              {...register("start_date")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="end_date" required>End Date</Label>
            <Input
              id="end_date"
              type="date"
              error={errors.end_date?.message}
              {...register("end_date")}
            />
          </div>

          <div className="flex items-center gap-2">
            <Switch id="is_current" {...register("is_current")} />
            <Label htmlFor="is_current">Set as current year</Label>
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
