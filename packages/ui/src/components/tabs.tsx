/**
 * Tabs — controlled/uncontrolled tab component.
 * Usage:
 *   <Tabs defaultValue="overview">
 *     <TabsList>
 *       <TabsTrigger value="overview">Overview</TabsTrigger>
 *       <TabsTrigger value="details">Details</TabsTrigger>
 *     </TabsList>
 *     <TabsContent value="overview">…</TabsContent>
 *     <TabsContent value="details">…</TabsContent>
 *   </Tabs>
 */

"use client";

import React, { createContext, useContext, useState } from "react";
import { cn } from "../lib/utils";

/* ── context ── */

interface TabsCtx {
  value: string;
  onValueChange: (v: string) => void;
}

const Ctx = createContext<TabsCtx>({ value: "", onValueChange: () => {} });

/* ── Tabs root ── */

interface TabsProps {
  defaultValue: string;
  value?: string;
  onValueChange?: (v: string) => void;
  children: React.ReactNode;
  className?: string;
}

function Tabs({
  defaultValue,
  value: controlled,
  onValueChange,
  children,
  className,
}: TabsProps) {
  const [internal, setInternal] = useState(defaultValue);
  const value = controlled ?? internal;
  const setValue = onValueChange ?? setInternal;

  return (
    <Ctx.Provider value={{ value, onValueChange: setValue }}>
      <div className={className}>{children}</div>
    </Ctx.Provider>
  );
}

/* ── TabsList ── */

function TabsList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex h-10 items-center gap-1 rounded-lg bg-muted p-1",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* ── TabsTrigger ── */

interface TabsTriggerProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

function TabsTrigger({ value, children, className, disabled }: TabsTriggerProps) {
  const ctx = useContext(Ctx);
  const active = ctx.value === value;

  return (
    <button
      role="tab"
      type="button"
      aria-selected={active}
      disabled={disabled}
      onClick={() => ctx.onValueChange(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        active
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* ── TabsContent ── */

interface TabsContentProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

function TabsContent({ value, children, className }: TabsContentProps) {
  const ctx = useContext(Ctx);
  if (ctx.value !== value) return null;

  return (
    <div
      role="tabpanel"
      className={cn(
        "mt-4 ring-offset-background focus-visible:outline-none",
        className,
      )}
    >
      {children}
    </div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
