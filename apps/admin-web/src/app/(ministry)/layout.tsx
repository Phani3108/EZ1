/**
 * Ministry (MoPSE) layout — Phase 14e / ADR 020.
 *
 * Role-gated route group living next to (admin). The Ministry persona
 * gets a distinct sidebar with READ-ONLY surfaces only — no operational
 * verbs anywhere in this tree.
 *
 * Defence-in-depth: the route layer in each ministry endpoint ALSO
 * asserts the Ministry role. Removing this layout guard alone would
 * not leak data, but the guard remains because (a) it produces a
 * proper 403 page instead of a flash of unauthenticated state, and
 * (b) it stops Ministry users from accidentally clicking into School
 * Admin pages and getting confusing 403 toasts.
 */

"use client";

import React from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth, RouteGuard } from "@eduzim/auth";
import { cn } from "@eduzim/ui";
import {
  LayoutDashboard,
  Map,
  BarChart3,
  AlertTriangle,
  BookOpen,
  Users2,
  ScrollText,
  ClipboardCheck,
  Heart,
  FileDown,
  Scale,
  LogOut,
} from "lucide-react";

interface MinistryNavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const ministryNav: MinistryNavItem[] = [
  { title: "Overview", href: "/ministry", icon: LayoutDashboard },
  { title: "School onboarding", href: "/ministry/onboarding", icon: ClipboardCheck },
  { title: "National Curriculum", href: "/ministry/curriculum", icon: BookOpen },
  { title: "Geography", href: "/ministry/geography", icon: Map },
  { title: "Enrolment", href: "/ministry/enrolment", icon: Users2 },
  { title: "Attendance", href: "/ministry/attendance", icon: ClipboardCheck },
  { title: "Drop-outs", href: "/ministry/dropouts", icon: AlertTriangle },
  { title: "Subjects", href: "/ministry/subjects", icon: BookOpen },
  { title: "Resources (PTR)", href: "/ministry/resources", icon: Scale },
  { title: "Compliance", href: "/ministry/compliance", icon: ScrollText },
  { title: "Comparative", href: "/ministry/comparative", icon: BarChart3 },
  { title: "Donors / NGOs", href: "/ministry/donors", icon: Heart },
  { title: "Exports", href: "/ministry/exports", icon: FileDown },
];

export default function MinistryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout, hasRole } = useAuth();

  return (
    <RouteGuard
      // Layout-level: require ministry:read permission. The backend
      // also asserts the Ministry role on every endpoint, so a user
      // who has the perm but not the role gets a 403 from the API.
      permissions={["ministry:read"]}
      onUnauthenticated={() => router.replace("/login")}
      onForbidden={() => router.replace("/dashboard")}
    >
      <div className="flex min-h-screen flex-col bg-background">
        {/* Distinct Ministry colorway — green stripe so users always
            know they're in the cross-school surface, not their own
            school's operational pages. */}
        <div
          aria-hidden="true"
          className="h-1.5 w-full shrink-0 bg-emerald-700"
        />
        <div className="flex flex-1">
          <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r bg-card lg:flex">
            <div className="flex h-14 items-center gap-2 border-b px-4">
              <Scale className="h-6 w-6 text-emerald-700" />
              <div className="flex flex-col leading-tight">
                <span className="text-sm font-semibold">Ministry</span>
                <span className="text-xs text-muted-foreground">
                  MoPSE · read-only
                </span>
              </div>
            </div>
            <nav className="flex-1 overflow-y-auto py-2">
              {ministryNav.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                      active
                        ? "bg-emerald-50 text-emerald-900 border-r-2 border-emerald-700 font-medium"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.title}</span>
                  </Link>
                );
              })}
            </nav>
            <div className="border-t p-4">
              <div className="mb-2 text-xs text-muted-foreground">
                Signed in as
              </div>
              <div className="mb-3 truncate text-sm font-medium">
                {user?.email || "Ministry user"}
              </div>
              <button
                onClick={() => logout()}
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-muted"
              >
                <LogOut className="h-4 w-4" />
                <span>Sign out</span>
              </button>
            </div>
          </aside>
          <main className="flex-1 px-6 py-6 lg:ml-64 lg:px-8">{children}</main>
        </div>
      </div>
    </RouteGuard>
  );
}
