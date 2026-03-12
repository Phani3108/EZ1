/**
 * Parent Home — child overview.
 */

"use client";

import React from "react";
import Link from "next/link";
import { useAuth } from "@eduzim/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { Users, ChevronRight, Loader2, AlertCircle } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { student } from "@/lib/api";
import type { Student } from "@eduzim/api-client";

export default function ParentHomePage() {
  const { user } = useAuth();
  const { data: children, isLoading, error } = useApiQuery<Student[]>(
    () => student.getMyChildren(),
    []
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">
        Welcome, {user?.full_name ?? "Parent"}
      </h1>
      <p className="text-muted-foreground">
        View your child&apos;s attendance, fees, and announcements.
      </p>

      <Card>
        <CardHeader className="flex flex-row items-center gap-3">
          <Users className="h-5 w-5 text-primary" />
          <CardTitle className="text-lg">My Children</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error.message}</span>
            </div>
          )}

          {!isLoading && !error && children && children.length === 0 && (
            <div className="rounded-lg border bg-muted/30 p-8 text-center text-muted-foreground">
              No children linked to your account yet. Please contact the school
              administration.
            </div>
          )}

          {!isLoading && !error && children && children.length > 0 && (
            <ul className="divide-y">
              {children.map((child) => (
                <li key={child.id}>
                  <Link
                    href={`/children/${child.id}`}
                    className="flex items-center justify-between py-3 transition-colors hover:bg-muted/30 rounded px-2 -mx-2"
                  >
                    <div>
                      <p className="font-medium">
                        {child.first_name} {child.last_name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {child.student_code} &middot;{" "}
                        <span
                          className={
                            child.status === "ACTIVE"
                              ? "text-green-600"
                              : "text-muted-foreground"
                          }
                        >
                          {child.status}
                        </span>
                      </p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
