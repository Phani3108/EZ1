/**
 * EduZim Auth — Route Guard
 * ============================
 * Client-side route protection. Redirects to login if not authenticated.
 * Optionally checks for required permissions.
 */

"use client";

import React from "react";
import { useAuth } from "./provider";

interface RouteGuardProps {
  children: React.ReactNode;
  /** Required permission(s). If unset, only requires authentication. */
  permissions?: string[];
  /** Any-of mode: user needs at least ONE of the permissions (default: all). */
  anyOf?: boolean;
  /** Render when redirecting / checking auth */
  fallback?: React.ReactNode;
  /** Called when access is denied (redirect to login or 403 page) */
  onUnauthenticated?: () => void;
  onForbidden?: () => void;
}

export function RouteGuard({
  children,
  permissions,
  anyOf = false,
  fallback,
  onUnauthenticated,
  onForbidden,
}: RouteGuardProps) {
  const { isLoading, isAuthenticated, hasPermission, hasAnyPermission } = useAuth();

  if (isLoading) {
    return <>{fallback ?? <DefaultLoader />}</>;
  }

  if (!isAuthenticated) {
    onUnauthenticated?.();
    return <>{fallback ?? <DefaultLoader />}</>;
  }

  // Permission check
  if (permissions && permissions.length > 0) {
    const allowed = anyOf
      ? hasAnyPermission(...permissions)
      : permissions.every((p) => hasPermission(p));
    if (!allowed) {
      onForbidden?.();
      return <ForbiddenPage />;
    }
  }

  return <>{children}</>;
}

function DefaultLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  );
}

function ForbiddenPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-2">
      <h1 className="text-2xl font-bold text-destructive">403 — Forbidden</h1>
      <p className="text-muted-foreground">
        You don&apos;t have permission to access this page.
      </p>
    </div>
  );
}
