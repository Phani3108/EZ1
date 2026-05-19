/**
 * Admin Sidebar — permission-aware, collapsible nav.
 */

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@eduzim/auth";
import { cn } from "@eduzim/ui";
import { adminNav, type NavItem } from "@/lib/nav";
import { ChevronDown, LogOut, Menu, X } from "lucide-react";
import { LanguageSwitcher } from "./language-switcher";

export function Sidebar() {
  const { user, hasPermission, logout } = useAuth();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const visibleItems = adminNav.filter(
    (item) =>
      item.permission === "authenticated" || hasPermission(item.permission)
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="fixed top-4 left-4 z-50 lg:hidden rounded-md bg-background p-2 shadow-md border"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-card transition-all duration-200",
          collapsed ? "w-16" : "w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b px-4">
          <img
            src="/national/coat-of-arms.svg"
            alt="Zimbabwe coat of arms"
            className="h-8 w-8"
            width={32}
            height={32}
          />
          {!collapsed && (
            <span className="ml-2 text-lg font-semibold">EduZim</span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto hidden lg:block text-muted-foreground hover:text-foreground"
          >
            <Menu className="h-4 w-4" />
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto py-2">
          {visibleItems.map((item) => (
            <NavEntry
              key={item.href}
              item={item}
              pathname={pathname}
              collapsed={collapsed}
              hasPermission={hasPermission}
            />
          ))}
        </nav>

        {/* User info + Logout */}
        <div className="border-t p-3 space-y-2">
          {!collapsed && <LanguageSwitcher />}
          {!collapsed && user && (
            <div className="truncate text-xs text-muted-foreground">
              {user.full_name} &middot;{" "}
              <span className="capitalize">{user.roles.join(", ")}</span>
            </div>
          )}
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            {!collapsed && "Sign out"}
          </button>
        </div>
      </aside>
    </>
  );
}

// ─── Single nav entry (with children expansion) ───

function NavEntry({
  item,
  pathname,
  collapsed,
  hasPermission,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
  hasPermission: (p: string) => boolean;
}) {
  const isActive =
    pathname === item.href || pathname.startsWith(item.href + "/");
  const [open, setOpen] = useState(isActive);

  const Icon = item.icon;

  const visibleChildren = item.children?.filter(
    (c) => c.permission === "authenticated" || hasPermission(c.permission)
  );

  if (!visibleChildren || visibleChildren.length === 0) {
    return (
      <Link
        href={item.href}
        className={cn(
          "flex items-center gap-3 mx-2 rounded-md px-3 py-2 text-sm transition-colors",
          isActive
            ? "bg-primary/10 text-primary font-medium"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && item.title}
      </Link>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex w-full items-center gap-3 mx-2 rounded-md px-3 py-2 text-sm transition-colors",
          isActive
            ? "text-primary font-medium"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && (
          <>
            <span className="flex-1 text-left">{item.title}</span>
            <ChevronDown
              className={cn(
                "h-3 w-3 transition-transform",
                open && "rotate-180"
              )}
            />
          </>
        )}
      </button>
      {!collapsed && open && (
        <div className="ml-9 space-y-0.5">
          {visibleChildren.map((child) => (
            <Link
              key={child.href}
              href={child.href}
              className={cn(
                "block rounded-md px-3 py-1.5 text-sm transition-colors",
                pathname === child.href
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              {child.title}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
