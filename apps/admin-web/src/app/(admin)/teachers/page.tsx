/**
 * Teachers directory — users with role=Teacher.
 * Shows teacher profiles and their class assignments.
 */

"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Button, Badge,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { User } from "@eduzim/api-client";
import { users } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";
import { EmptyState } from "@/components/empty-state";
import { Eye, GraduationCap } from "lucide-react";

export default function TeachersPage() {
  const [search, setSearch] = useState("");

  const { data: allUsers, isLoading, error } = useApiQuery(
    () => users.list(),
    [],
  );

  // Filter to only teachers
  const teachers = useMemo(() => {
    if (!allUsers) return [];
    return allUsers.filter((u) =>
      u.roles.some((r) => {
        const name = typeof r === "string" ? r : r.name;
        return name.toLowerCase() === "teacher";
      }),
    );
  }, [allUsers]);

  const filtered = useMemo(() => {
    if (!search) return teachers;
    const q = search.toLowerCase();
    return teachers.filter(
      (t) =>
        t.full_name?.toLowerCase().includes(q) ||
        t.email.toLowerCase().includes(q),
    );
  }, [teachers, search]);

  return (
    <RouteGuard onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader title="Teachers" description="Teacher directory — staff members with the Teacher role." />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name or email…"
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
            icon={GraduationCap}
            title={search ? "No teachers match your search" : "No teachers found"}
            description={search ? "Try a different search." : "Users with the Teacher role will appear here."}
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead className="w-20">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">
                      <Link href={`/teachers/${t.id}`} className="text-primary hover:underline">
                        {t.full_name || t.email}
                      </Link>
                    </TableCell>
                    <TableCell>{t.email}</TableCell>
                    <TableCell>
                      <Badge variant={t.is_active ? "default" : "secondary"}>
                        {t.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {t.roles.map((r) => {
                          const name = typeof r === "string" ? r : r.name;
                          return (
                            <Badge key={name} variant="outline" className="text-xs">
                              {name}
                            </Badge>
                          );
                        })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Link href={`/teachers/${t.id}`}>
                        <Button variant="ghost" size="sm"><Eye className="h-4 w-4" /></Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
