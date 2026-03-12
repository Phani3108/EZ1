/**
 * Roles & Permissions — view all roles, see assigned permissions.
 * Permission: school:manage
 */

"use client";

import React from "react";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import { users as usersApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Shield, ChevronLeft } from "lucide-react";
import Link from "next/link";

export default function RolesPage() {
  const { data: roles, isLoading, error } = useApiQuery(
    () => usersApi.listRoles(),
    [],
  );

  return (
    <RouteGuard permissions={["school:manage"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Link href="/users" className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <PageHeader
            title="Roles & Permissions"
            description="System roles determine what actions portal users can perform."
          />
        </div>

        {error && <ErrorAlert message={error.message} />}

        {isLoading ? (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">Loading…</div>
        ) : !roles?.length ? (
          <EmptyState icon={Shield} title="No roles found" description="Contact support if roles are missing." />
        ) : (
          <div className="space-y-4">
            {roles.map((role) => (
              <div key={role.id} className="rounded-lg border bg-card p-5">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <h3 className="font-semibold text-base">{role.name}</h3>
                    {role.description && (
                      <p className="text-sm text-muted-foreground mt-0.5">{role.description}</p>
                    )}
                  </div>
                  <Badge variant="outline" className="shrink-0">{role.permissions?.length ?? 0} permissions</Badge>
                </div>
                {role.permissions && role.permissions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {role.permissions.map((perm) => (
                      <span
                        key={perm.id}
                        className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground"
                      >
                        {perm.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="rounded-lg border bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-semibold mb-1">Roles are system-defined</p>
          <p>EduZim uses three fixed roles: <strong>SchoolAdmin</strong>, <strong>Teacher</strong>, and <strong>Parent</strong>. Contact support to request custom role configurations.</p>
        </div>
      </div>
    </RouteGuard>
  );
}
