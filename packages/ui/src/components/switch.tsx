/**
 * Switch — simple toggle component.
 * Pure HTML checkbox styled as a switch.
 */

"use client";

import * as React from "react";
import { cn } from "../lib/utils";

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, label, ...props }, ref) => {
    return (
      <label className={cn("inline-flex items-center gap-2 cursor-pointer", className)}>
        <div className="relative">
          <input
            type="checkbox"
            ref={ref}
            className="peer sr-only"
            {...props}
          />
          <div className="h-5 w-9 rounded-full bg-muted transition-colors peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2" />
          <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-background shadow transition-transform peer-checked:translate-x-4" />
        </div>
        {label && <span className="text-sm">{label}</span>}
      </label>
    );
  }
);
Switch.displayName = "Switch";

export { Switch };
