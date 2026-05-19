/**
 * Parent app shell — top nav + content + footer.
 * Includes OfflineProvider for read-cache offline support.
 */

"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { RouteGuard, useAuth } from "@eduzim/auth";
import { cn } from "@eduzim/ui";
import { Home, ClipboardCheck, DollarSign, Megaphone, LogOut, WifiOff } from "lucide-react";
import { Footer } from "@/components/footer";
import { LanguageSwitcher } from "@/components/language-switcher";
import { OfflineProvider, useOffline } from "@/lib/offline-provider";
import { ReadAloudProvider } from "@/components/read-aloud-provider";

const parentNav = [
  { title: "Home", href: "/home", icon: Home },
  { title: "Attendance", href: "/attendance", icon: ClipboardCheck },
  { title: "Fees", href: "/fees", icon: DollarSign },
  { title: "Announcements", href: "/announcements", icon: Megaphone },
];

export default function ParentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <RouteGuard onUnauthenticated={() => router.replace("/login")}>
      <OfflineProvider>
        <ReadAloudProvider>
          <div className="flex min-h-screen flex-col">
            <TopNav />
            <OfflineBanner />
            <main className="flex-1 px-4 md:px-6 py-4 md:py-6">{children}</main>
            <Footer />
            <BottomNav />
          </div>
        </ReadAloudProvider>
      </OfflineProvider>
    </RouteGuard>
  );
}

function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-card px-4 md:px-6">
      <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-primary-foreground text-sm font-bold">
        E
      </div>
      <span className="ml-2 font-semibold">EduZim</span>

      {/* Desktop nav */}
      <nav className="ml-8 hidden gap-4 md:flex">
        {parentNav.map((item) => (
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
            {item.title}
          </Link>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-3">
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

  return (
    <nav className="sticky bottom-0 z-30 flex border-t bg-card md:hidden">
      {parentNav.map((item) => {
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
