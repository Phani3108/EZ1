/**
 * PageContainer — standard page wrapper with consistent padding and spacing.
 * Provides the "px-6 lg:px-8 py-6 space-y-6" rhythm from the design tokens.
 */

import React from "react";
import { cn } from "../lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div className={cn("px-6 lg:px-8 py-6 space-y-6", className)}>
      {children}
    </div>
  );
}
