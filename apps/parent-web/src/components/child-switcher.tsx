/**
 * ChildSwitcher — Phase 12a / P-002.
 *
 * Dropdown in the parent-web top nav. For single-child households this
 * renders as a static label (no dropdown), avoiding a useless click
 * target. The selection persists in localStorage via `useChild()`.
 *
 * Hidden entirely for the Student role (a student only ever sees their
 * own data).
 */

"use client";

import React from "react";
import { ChevronDown, User } from "lucide-react";
import { useChild } from "@/lib/child-context";


export function ChildSwitcher() {
  const { children, selected, selectChild, isLoading } = useChild();

  if (isLoading) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs text-muted-foreground"
        data-testid="child-switcher-loading"
      >
        <User className="h-3.5 w-3.5" /> …
      </span>
    );
  }

  if (children.length === 0) {
    // No children yet — render nothing rather than an empty switcher.
    return null;
  }

  if (children.length === 1) {
    const c = children[0]!;
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
        data-testid="child-switcher-single"
      >
        <User className="h-3 w-3" />
        {c.first_name} {c.last_name}
      </span>
    );
  }

  return (
    <div className="relative" data-testid="child-switcher">
      <select
        value={selected?.id ?? ""}
        onChange={(e) => selectChild(e.target.value)}
        aria-label="Select child"
        className="appearance-none rounded-full border border-input bg-card pr-7 pl-3 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {children.map((c) => (
          <option key={c.id} value={c.id}>
            {c.first_name} {c.last_name}
            {c.is_primary ? " ★" : ""}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 pointer-events-none text-muted-foreground" />
    </div>
  );
}
