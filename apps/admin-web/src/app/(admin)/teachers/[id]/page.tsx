/**
 * Teacher detail page — profile + assigned classes.
 * Teachers are users with the Teacher role.
 */

"use client";

import React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Card, CardContent, CardHeader, CardTitle,
  Badge,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import { users, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { DetailHeader } from "@/components/detail-header";
import { EmptyState } from "@/components/empty-state";
import { User, Mail, Shield, GraduationCap, ClipboardCheck, Megaphone } from "lucide-react";

export default function TeacherDetailPage() {
  const params = useParams<{ id: string }>();
  const teacherId = params.id;

  const { data: teacher, isLoading, error } = useApiQuery(
    () => users.get(teacherId),
    [teacherId],
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <DetailHeader backHref="/teachers" backLabel="Teachers" title="Teacher" />
        <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />
      </div>
    );
  }

  if (!teacher) return null;

  const roleNames = teacher.roles.map((r) => (typeof r === "string" ? r : r.name));

  return (
    <RouteGuard onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <DetailHeader
          backHref="/teachers"
          backLabel="Teachers"
          title={teacher.full_name || teacher.email}
          subtitle={teacher.email}
          badges={[
            {
              label: teacher.is_active ? "Active" : "Inactive",
              variant: teacher.is_active ? "default" : "secondary",
            },
            ...roleNames.map((r) => ({ label: r, variant: "outline" as const })),
          ]}
        />

        {/* Profile */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" /> Teacher Profile
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Full Name</dt>
                <dd className="mt-1 text-sm">{teacher.full_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Mail className="h-3 w-3" /> Email
                </dt>
                <dd className="mt-1 text-sm">{teacher.email}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Shield className="h-3 w-3" /> Roles
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {roleNames.map((r) => (
                    <Badge key={r} variant="outline" className="text-xs">{r}</Badge>
                  ))}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Status</dt>
                <dd className="mt-1">
                  <Badge variant={teacher.is_active ? "default" : "secondary"}>
                    {teacher.is_active ? "Active" : "Inactive"}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Since</dt>
                <dd className="mt-1 text-sm">{new Date(teacher.created_at).toLocaleDateString()}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Permissions</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {teacher.permissions.length > 0 ? (
                    teacher.permissions.map((p) => (
                      <Badge key={p} variant="secondary" className="text-xs">{p}</Badge>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">None assigned</span>
                  )}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Assigned Classes — placeholder for class → teacher mapping */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5" /> Assigned Classes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={GraduationCap}
              title="Class assignments"
              description="Teacher → class mapping will be available once class assignments are configured in the school service."
            />
          </CardContent>
        </Card>

        {/* Phase 2 placeholders */}
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4" /> Attendance Marking Coverage
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Coming in Phase 2</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <Megaphone className="h-4 w-4" /> Communication History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Coming in Phase 2</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </RouteGuard>
  );
}
