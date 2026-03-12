/**
 * Parents directory — table + search + drawer create/edit.
 * One parent profile shared across multiple children.
 * Permission: student:read
 */

"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Input, Label, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Parent } from "@eduzim/api-client";
import { student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Plus, Pencil, Users, Eye } from "lucide-react";

// ─── Zod Schema ───

const parentSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(50),
  last_name: z.string().min(1, "Last name is required").max(50),
  phone: z.string().min(1, "Phone number is required").max(20),
  email: z.string().email("Enter a valid email").optional().or(z.literal("")),
  relationship: z.string().optional().or(z.literal("")),
});

type ParentFormData = z.infer<typeof parentSchema>;

// ─── Page ───

export default function ParentsPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Parent | null>(null);
  const [search, setSearch] = useState("");

  const { data: parents, isLoading, error, refetch } = useApiQuery(
    () => studentApi.listParents(),
    [],
  );

  const createMutation = useApiMutation(
    (data: ParentFormData) => studentApi.createParent(data),
    { onSuccess: () => { setDrawerOpen(false); refetch(); } },
  );

  const updateMutation = useApiMutation(
    (args: { id: string; data: ParentFormData }) =>
      studentApi.updateParent(args.id, args.data),
    { onSuccess: () => { setDrawerOpen(false); setEditing(null); refetch(); } },
  );

  const openCreate = () => { setEditing(null); setDrawerOpen(true); };
  const openEdit = (p: Parent) => { setEditing(p); setDrawerOpen(true); };

  const filtered = useMemo(() => {
    if (!parents) return [];
    if (!search) return parents;
    const q = search.toLowerCase();
    return parents.filter(
      (p) =>
        p.first_name.toLowerCase().includes(q) ||
        p.last_name.toLowerCase().includes(q) ||
        p.phone.includes(q) ||
        (p.email?.toLowerCase().includes(q) ?? false),
    );
  }, [parents, search]);

  return (
    <RouteGuard permissions={["student:read"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader title="Parents" description="Parent & guardian directory. One profile per parent, linked to children.">
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" /> Add Parent
          </Button>
        </PageHeader>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name, phone, or email…"
            className="sm:w-80"
          />
        </div>

        {error && (
          <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />
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
            title={search ? "No parents match your search" : "No parents yet"}
            description={search ? "Try a different search term." : "Add your first parent or guardian."}
          >
            {!search && (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4 mr-1" /> Add Parent
              </Button>
            )}
          </EmptyState>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Relationship</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">
                      <Link href={`/parents/${p.id}`} className="text-primary hover:underline">
                        {p.first_name} {p.last_name}
                      </Link>
                    </TableCell>
                    <TableCell>{p.phone}</TableCell>
                    <TableCell>{p.email || "—"}</TableCell>
                    <TableCell className="capitalize">{p.relationship || "—"}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Link href={`/parents/${p.id}`}>
                          <Button variant="ghost" size="sm"><Eye className="h-4 w-4" /></Button>
                        </Link>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(p)}>
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
            <SheetTitle>{editing ? "Edit Parent" : "Add Parent"}</SheetTitle>
            <SheetDescription>
              {editing ? "Update parent information." : "Add a new parent or guardian."}
            </SheetDescription>
          </SheetHeader>
          <ParentForm
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

function ParentForm({
  initial,
  isSubmitting,
  error,
  onSubmit,
  onCancel,
}: {
  initial: Parent | null;
  isSubmitting: boolean;
  error: { message: string; requestId: string | null; details: Record<string, unknown> | null } | null;
  onSubmit: (data: ParentFormData) => void;
  onCancel: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ParentFormData>({
    resolver: zodResolver(parentSchema),
    defaultValues: {
      first_name: initial?.first_name ?? "",
      last_name: initial?.last_name ?? "",
      phone: initial?.phone ?? "",
      email: initial?.email ?? "",
      relationship: initial?.relationship ?? "",
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
            <Label htmlFor="phone">Phone *</Label>
            <Input id="phone" {...register("phone")} placeholder="+263 77 123 4567" />
            {errors.phone && (
              <p className="mt-1 text-xs text-destructive">{errors.phone.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" {...register("email")} />
            {errors.email && (
              <p className="mt-1 text-xs text-destructive">{errors.email.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="relationship">Relationship</Label>
            <Select
              id="relationship"
              {...register("relationship")}
              placeholder="— Select —"
              options={[
                { value: "father", label: "Father" },
                { value: "mother", label: "Mother" },
                { value: "guardian", label: "Guardian" },
                { value: "grandparent", label: "Grandparent" },
                { value: "sibling", label: "Sibling" },
                { value: "other", label: "Other" },
              ]}
            />
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
