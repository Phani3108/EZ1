/**
 * Terms — CRUD page with Sheet drawer.
 * Permission: school:manage
 */

"use client";

import React, { useState, useCallback } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge, Input, Label, Select, Switch,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Term, AcademicYear } from "@eduzim/api-client";
import { school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { Plus, Pencil } from "lucide-react";

// ─── Zod Schema ───

const termSchema = z.object({
  academic_year_id: z.string().min(1, "Academic year is required"),
  name: z.string().min(1, "Name is required").max(50, "Name too long"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  is_current: z.boolean().default(false),
}).refine((d) => !d.start_date || !d.end_date || d.start_date < d.end_date, {
  message: "End date must be after start date",
  path: ["end_date"],
});

type TermFormData = z.infer<typeof termSchema>;

// ─── Page ───

export default function TermsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Term | null>(null);

  const { data: terms, isLoading, error, refetch } = useApiQuery(
    () => school.listTerms(),
    []
  );

  const { data: years } = useApiQuery(
    () => school.listAcademicYears(),
    []
  );

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };

  const openEdit = (term: Term) => {
    setEditing(term);
    setDrawerOpen(true);
  };

  const handleSaved = useCallback(() => {
    setDrawerOpen(false);
    setEditing(null);
    refetch();
  }, [refetch]);

  const yearName = (yearId: string) => {
    return years?.find((y) => y.id === yearId)?.name ?? yearId;
  };

  return (
    <RouteGuard permissions={["school:manage"]}>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Terms</h1>
            <p className="text-sm text-muted-foreground">
              Manage terms within academic years.
            </p>
          </div>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New Term
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
                  <TableHead>Academic Year</TableHead>
                  <TableHead>Start Date</TableHead>
                  <TableHead>End Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(!terms || terms.length === 0) ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No terms found. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  terms.map((term) => (
                    <TableRow key={term.id}>
                      <TableCell className="font-medium">{term.name}</TableCell>
                      <TableCell>{yearName(term.academic_year_id)}</TableCell>
                      <TableCell>{term.start_date}</TableCell>
                      <TableCell>{term.end_date}</TableCell>
                      <TableCell>
                        <Badge variant={term.is_current ? "success" : "secondary"}>
                          {term.is_current ? "Current" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" onClick={() => openEdit(term)}>
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

        <TermDrawer
          open={drawerOpen}
          onClose={() => { setDrawerOpen(false); setEditing(null); }}
          editing={editing}
          years={years ?? []}
          onSaved={handleSaved}
        />
      </div>
    </RouteGuard>
  );
}

// ─── Drawer Form ───

function TermDrawer({
  open,
  onClose,
  editing,
  years,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  editing: Term | null;
  years: AcademicYear[];
  onSaved: () => void;
}) {
  const isEdit = !!editing;

  const { register, handleSubmit, formState: { errors }, reset } = useForm<TermFormData>({
    resolver: zodResolver(termSchema),
    defaultValues: editing
      ? { academic_year_id: editing.academic_year_id, name: editing.name, start_date: editing.start_date, end_date: editing.end_date, is_current: editing.is_current }
      : { academic_year_id: "", name: "", start_date: "", end_date: "", is_current: false },
  });

  React.useEffect(() => {
    if (open) {
      reset(
        editing
          ? { academic_year_id: editing.academic_year_id, name: editing.name, start_date: editing.start_date, end_date: editing.end_date, is_current: editing.is_current }
          : { academic_year_id: "", name: "", start_date: "", end_date: "", is_current: false }
      );
    }
  }, [editing, open, reset]);

  const createMutation = useApiMutation(
    (data: TermFormData) => school.createTerm(data),
    { onSuccess: onSaved }
  );

  const updateMutation = useApiMutation(
    (data: TermFormData) => school.updateTerm(editing!.id, data),
    { onSuccess: onSaved }
  );

  const mutation = isEdit ? updateMutation : createMutation;

  const onSubmit = handleSubmit((data) => {
    mutation.mutate(data);
  });

  const yearOptions = years.map((y) => ({ value: y.id, label: y.name }));

  return (
    <Sheet open={open} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col h-full">
        <SheetHeader>
          <SheetTitle>{isEdit ? "Edit Term" : "New Term"}</SheetTitle>
          <SheetDescription>
            {isEdit ? "Update term details." : "Create a new term."}
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
            <Label htmlFor="academic_year_id" required>Academic Year</Label>
            <Select
              id="academic_year_id"
              options={yearOptions}
              placeholder="Select academic year"
              error={errors.academic_year_id?.message}
              {...register("academic_year_id")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="name" required>Name</Label>
            <Input
              id="name"
              placeholder="e.g. Term 1"
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
            <Label htmlFor="is_current">Set as current term</Label>
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
