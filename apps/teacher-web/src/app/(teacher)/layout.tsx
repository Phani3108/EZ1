/**
 * Teacher app shell — top nav + content + footer.
 * Simplified nav: Today, My Classes, Announcements, Sync Center.
 * Includes SyncProvider for offline queue management.
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { RouteGuard, useAuth } from "@eduzim/auth";
import { cn } from "@eduzim/ui";
import {
  CalendarDays,
  BookOpen,
  Megaphone,
  LogOut,
  CheckCircle,
  Clock,
  AlertTriangle,
  WifiOff,
} from "lucide-react";
import { Footer } from "@/components/footer";
import { LanguageSwitcher } from "@/components/language-switcher";
import { SyncProvider, useSync } from "@/lib/sync-provider";

const teacherNav = [
  { key: "today", href: "/today", icon: CalendarDays },
  { key: "myClasses", href: "/classes", icon: BookOpen },
  { key: "announcements", href: "/announcements", icon: Megaphone },
] as const;

export default function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <RouteGuard onUnauthenticated={() => router.replace("/login")}>
      <SyncProvider>
        <div className="flex min-h-screen flex-col">
          <TopNav />
          <OfflineBanner />
          <main className="flex-1 px-4 md:px-6 py-4 md:py-6">{children}</main>
          <Footer />
          <BottomNav />
        </div>
      </SyncProvider>
    </RouteGuard>
  );
}

function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-card px-4 md:px-6">
      <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-primary-foreground text-sm font-bold">
        E
      </div>
      <span className="ml-2 font-semibold">{tCommon("appName")}</span>

      {/* Desktop nav */}
      <nav className="ml-8 hidden gap-4 md:flex">
        {teacherNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "text-sm transition-colors",
              pathname.startsWith(item.href)
                ? "text-primary font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(item.key)}
          </Link>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <SyncStatusPill />
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
          <span className="hidden md:inline">{tCommon("signOut")}</span>
        </button>
      </div>
    </header>
  );
}

function BottomNav() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  return (
    <nav className="sticky bottom-0 z-30 flex border-t bg-card md:hidden">
      {teacherNav.map((item) => {
        const Icon = item.icon;
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors",
              active ? "text-primary" : "text-muted-foreground"
            )}
          >
            <Icon className="h-5 w-5" />
            {t(item.key)}
          </Link>
        );
      })}
    </nav>
  );
}

/* ─── Sync Status Pill (TopNav) ─── */
function SyncStatusPill() {
  const { syncStatus, online } = useSync();
  const { failed, queued, syncing } = syncStatus;

  if (!online) {
    return (
      <Link
        href="/sync-center"
        className="flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
      >
        <WifiOff className="h-3 w-3" />
        <span className="hidden sm:inline">Offline</span>
      </Link>
    );
  }

  if (failed > 0) {
    return (
      <Link
        href="/sync-center"
        className="flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700"
      >
        <AlertTriangle className="h-3 w-3" />
        {failed} failed
      </Link>
    );
  }

  if (queued > 0 || syncing > 0) {
    return (
      <Link
        href="/sync-center"
        className="flex items-center gap-1.5 rounded-full bg-yellow-100 px-2.5 py-1 text-xs font-medium text-yellow-700"
      >
        <Clock className="h-3 w-3" />
        {queued + syncing} pending
      </Link>
    );
  }

  return (
    <Link
      href="/sync-center"
      className="flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700"
    >
      <CheckCircle className="h-3 w-3" />
      <span className="hidden sm:inline">Synced</span>
    </Link>
  );
}

/* ─── Offline Banner ─── */
function OfflineBanner() {
  const { online } = useSync();

  if (online) return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-yellow-50 border-b border-yellow-200 px-4 py-2 text-sm text-yellow-800">
      <WifiOff className="h-4 w-4 shrink-0" />
      <span>
        You are offline. Changes will sync automatically when connection is
        restored.
      </span>
    </div>
  );
}
