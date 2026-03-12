/**
 * Parent detail page — profile + linked children.
 * One parent profile shared across multiple children.
 */

"use client";

import React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Card, CardContent, CardHeader, CardTitle,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import { student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { DetailHeader } from "@/components/detail-header";
import { EmptyState } from "@/components/empty-state";
import { User, Phone, Mail, Users, Heart } from "lucide-react";

export default function ParentDetailPage() {
  const params = useParams<{ id: string }>();
  const parentId = params.id;

  const { data: parent, isLoading, error } = useApiQuery(
    () => studentApi.getParent(parentId),
    [parentId],
  );

  const { data: children, isLoading: childrenLoading } = useApiQuery(
    () => studentApi.getParentChildren(parentId),
    [parentId],
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
        <DetailHeader backHref="/parents" backLabel="Parents" title="Parent" />
        <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />
      </div>
    );
  }

  if (!parent) return null;

  return (
    <RouteGuard permissions={["student:read"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <DetailHeader
          backHref="/parents"
          backLabel="Parents"
          title={`${parent.first_name} ${parent.last_name}`}
          subtitle={parent.relationship ? `Relationship: ${parent.relationship}` : undefined}
        />

        {/* Profile card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" /> Contact Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Full Name</dt>
                <dd className="mt-1 text-sm">{parent.first_name} {parent.last_name}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Phone className="h-3 w-3" /> Phone
                </dt>
                <dd className="mt-1 text-sm">{parent.phone}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Mail className="h-3 w-3" /> Email
                </dt>
                <dd className="mt-1 text-sm">{parent.email || "—"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Heart className="h-3 w-3" /> Relationship
                </dt>
                <dd className="mt-1 text-sm capitalize">{parent.relationship || "—"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">Since</dt>
                <dd className="mt-1 text-sm">{new Date(parent.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Linked Children */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" /> Linked Children
            </CardTitle>
          </CardHeader>
          <CardContent>
            {childrenLoading ? (
              <div className="h-20 animate-pulse rounded bg-muted" />
            ) : !children || children.length === 0 ? (
              <EmptyState
                icon={Users}
                title="No children linked"
                description="Link students to this parent from the Students directory."
              />
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Admission #</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {children.map((child) => (
                      <TableRow key={child.id}>
                        <TableCell className="font-medium">
                          <Link href={`/students/${child.id}`} className="text-primary hover:underline">
                            {child.first_name} {child.last_name}
                          </Link>
                        </TableCell>
                        <TableCell>{child.admission_number || "—"}</TableCell>
                        <TableCell>
                          <Badge variant={child.is_active ? "default" : "secondary"}>
                            {child.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Phase 2 placeholders */}
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">Fee Status per Child</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">Coming in Phase 2</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">Announcements per Child</CardTitle>
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
