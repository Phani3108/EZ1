/**
 * Parent + Student app shell — Phase 12a.
 *
 * The single parent-web hosts both Parent and Student roles per
 * DEC-002. The nav now branches on `user.roles`:
 *   - Parent (default): home, attendance, fees, announcements,
 *     plus the Phase 12 additions as they land.
 *   - Student: schedule, attendance, marks, announcements,
 *     assignments. Payments + messaging are HIDDEN.
 *
 * A child switcher renders next to the user's name for the Parent
 * role only — students are always looking at their own data.
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { RouteGuard, useAuth } from "@eduzim/auth";
import { cn } from "@eduzim/ui";
import {
  Home,
  ClipboardCheck,
  DollarSign,
  Megaphone,
  MessageCircle,
  CalendarRange,
  HeartHandshake,
  Sparkles,
  GraduationCap,
  Calendar,
  ListChecks,
  LogOut,
  WifiOff,
} from "lucide-react";
import { Footer } from "@/components/footer";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ChildSwitcher } from "@/components/child-switcher";
import { OfflineProvider, useOffline } from "@/lib/offline-provider";
import { ChildProvider } from "@/lib/child-context";
import { ReadAloudProvider } from "@/components/read-aloud-provider";


// Phase 12a: role-keyed nav definitions. The user role determines which
// list renders. RULE-1 / DEC-002 keeps the shell shared; the feature
// surface is gated.
const PARENT_NAV = [
  { title: "Home", href: "/home", icon: Home },
  { title: "Attendance", href: "/attendance", icon: ClipboardCheck },
  { title: "Fees", href: "/fees", icon: DollarSign },
  { title: "Announcements", href: "/announcements", icon: Megaphone },
  // Phase 12 additions — parent-side UI for the new backend surfaces.
  { title: "Messages", href: "/messages", icon: MessageCircle },
  { title: "Events", href: "/events", icon: CalendarRange },
  { title: "Connect", href: "/connect", icon: HeartHandshake },
  { title: "More", href: "/more", icon: Sparkles },
] as const;

const STUDENT_NAV = [
  { title: "Home", href: "/home", icon: Home },
  { title: "Schedule", href: "/schedule", icon: Calendar },
  { title: "Attendance", href: "/attendance", icon: ClipboardCheck },
  { title: "Marks", href: "/marks", icon: GraduationCap },
  { title: "Assignments", href: "/assignments", icon: ListChecks },
  { title: "Announcements", href: "/announcements", icon: Megaphone },
] as const;


function isStudent(roles: readonly string[] | undefined): boolean {
  if (!roles) return false;
  return roles.some((r) => r.toLowerCase() === "student");
}


export default function ParentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <RouteGuard onUnauthenticated={() => router.replace("/login")}>
      <OfflineProvider>
        <ChildProvider>
          <ReadAloudProvider>
            <div className="flex min-h-screen flex-col">
              <TopNav />
              <OfflineBanner />
              <main className="flex-1 px-4 md:px-6 py-4 md:py-6">{children}</main>
              <Footer />
              <BottomNav />
            </div>
          </ReadAloudProvider>
        </ChildProvider>
      </OfflineProvider>
    </RouteGuard>
  );
}


function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const studentMode = isStudent(user?.roles);
  const nav = studentMode ? STUDENT_NAV : PARENT_NAV;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-card px-4 md:px-6">
      <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-primary-foreground text-sm font-bold">
        E
      </div>
      <span className="ml-2 font-semibold">EduZim</span>

      {/* Desktop nav */}
      <nav className="ml-8 hidden gap-4 md:flex" data-testid="parent-web-nav">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            data-testid={`nav-${item.href.replace(/^\//, "")}`}
            className={cn(
              "text-sm transition-colors",
              pathname.startsWith(item.href)
                ? "text-primary font-medium"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.title}
          </Link>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        {/* Child switcher only for parents — students always see
            their own data. */}
        {!studentMode && <ChildSwitcher />}
        <LanguageSwitcher />
        {user && (
          <span className="hidden text-sm text-muted-foreground md:block">
            {user.full_name}
          </span>
        )}
        <button
          onClick={logout}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden md:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}


function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const studentMode = isStudent(user?.roles);
  const nav = studentMode ? STUDENT_NAV : PARENT_NAV;

  return (
    <nav className="sticky bottom-0 z-30 flex border-t bg-card md:hidden overflow-x-auto">
      {nav.map((item) => {
        const Icon = item.icon;
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors min-w-[70px]",
              active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <Icon className="h-5 w-5" />
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}


/* ─── Offline Banner ─── */
function OfflineBanner() {
  const { online } = useOffline();

  if (online) return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-yellow-50 border-b border-yellow-200 px-4 py-2 text-sm text-yellow-800">
      <WifiOff className="h-4 w-4 shrink-0" />
      <span>You are offline. Showing last saved data.</span>
    </div>
  );
}
