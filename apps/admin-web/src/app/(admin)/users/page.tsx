/**
 * Users — list all school users, create/deactivate.
 * Permission: school:manage
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
import { RouteGuard } from "@eduzim/auth";
import type { User } from "@eduzim/api-client";
import { users as usersApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Plus, Users as UsersIcon, Shield } from "lucide-react";
import Link from "next/link";

const userSchema = z.object({
  full_name: z.string().min(2, "Full name is required"),
  email: z.string().email("Enter a valid email"),
  role: z.string().min(1, "Select a role"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});
type UserForm = z.infer<typeof userSchema>;

const ROLE_OPTIONS = ["SchoolAdmin", "Teacher", "Parent"];

export default function UsersPage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data: userList, isLoading, error, refetch } = useApiQuery(
    () => usersApi.list(),
    [],
  );

  const createMutation = useApiMutation(
    (data: UserForm) => usersApi.create(data),
    { onSuccess: () => { setDrawerOpen(false); refetch(); } },
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UserForm>({ resolver: zodResolver(userSchema) });

  const openCreate = () => { reset(); setDrawerOpen(true); };

  const filtered = useMemo(() => {
    if (!userList) return [];
    if (!search) return userList as User[];
    const q = search.toLowerCase();
    return (userList as User[]).filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.roles?.some((r) => r.name.toLowerCase().includes(q)),
    );
  }, [userList, search]);

  const roleColor = (name: string) => {
    if (name === "SchoolAdmin") return "destructive";
    if (name === "Teacher") return "default";
    return "secondary";
  };

  return (
    <RouteGuard permissions={["school:manage"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader
          title="Users"
          description={`${userList?.length ?? 0} accounts`}
        >
          <Link href="/users/roles">
            <Button variant="outline" className="flex items-center gap-2">
              <Shield className="h-4 w-4" /> Manage Roles
            </Button>
          </Link>
          <Button onClick={openCreate} className="flex items-center gap-2">
            <Plus className="h-4 w-4" /> Add User
          </Button>
        </PageHeader>

        <SearchInput value={search} onChange={setSearch} placeholder="Search by name, email or role…" />

        {error && <ErrorAlert message={error.message} />}

        {isLoading ? (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">Loading…</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={UsersIcon} title="No users found" description="Add users to grant access to the portal." />
        ) : (
          <div className="rounded-lg border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.roles?.map((r) => (
                          <Badge key={r.id} variant={roleColor(r.name) as "destructive" | "default" | "secondary"}>
                            {r.name}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "success" : "secondary"}>
                        {u.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Sheet open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <SheetHeader>
            <SheetTitle>Add User</SheetTitle>
            <SheetDescription>Create a new portal account for a staff member or parent.</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form id="user-form" onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
              <div>
                <Label htmlFor="full_name">Full Name</Label>
                <Input id="full_name" {...register("full_name")} placeholder="e.g. Takesure Moyo" />
                {errors.full_name && <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>}
              </div>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" {...register("email")} placeholder="user@school.edu.zw" />
                {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
              </div>
              <div>
                <Label htmlFor="role">Role</Label>
                <Select id="role" {...register("role")}>
                  <option value="">— Select role —</option>
                  {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </Select>
                {errors.role && <p className="mt-1 text-xs text-red-600">{errors.role.message}</p>}
              </div>
              <div>
                <Label htmlFor="password">Temporary Password</Label>
                <Input id="password" type="password" {...register("password")} placeholder="Min 6 characters" />
                {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
              </div>
              {createMutation.error && <ErrorAlert message={createMutation.error.message} />}
            </form>
          </SheetBody>
          <SheetFooter>
            <Button variant="outline" onClick={() => setDrawerOpen(false)}>Cancel</Button>
            <Button type="submit" form="user-form" disabled={isSubmitting || createMutation.isSubmitting}>
              {createMutation.isSubmitting ? "Creating…" : "Create User"}
            </Button>
          </SheetFooter>
        </Sheet>
      </div>
    </RouteGuard>
  );
}
