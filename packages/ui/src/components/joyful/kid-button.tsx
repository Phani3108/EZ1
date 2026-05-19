/**
 * KidButton — joyful theme
 * Oversized button (≥56px tall, ≥48px wide) with large icon, friendly
 * rounded shape and AAA-contrast colours. Children must remain readable
 * for early readers; we intentionally bump font size + weight.
 *
 * Only use in parent-web / student surfaces.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const kidButtonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "rounded-2xl font-extrabold tracking-tight",
    "transition-transform active:scale-[0.97]",
    "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/40",
    "disabled:pointer-events-none disabled:opacity-50",
    "min-h-touch min-w-touch",
  ].join(" "),
  {
    variants: {
      tone: {
        primary:
          "bg-primary text-primary-foreground shadow-joyful hover:brightness-105",
        sunshine:
          "bg-secondary text-secondary-foreground shadow-joyful hover:brightness-105",
        sky: "bg-joyful-sky text-accent-foreground shadow-card hover:brightness-105",
        mint: "bg-joyful-mint text-foreground shadow-card hover:brightness-105",
        ghost: "bg-transparent text-foreground hover:bg-muted",
        danger:
          "bg-destructive text-destructive-foreground shadow-card hover:brightness-105",
      },
      size: {
        md: "h-14 px-5 text-base",
        lg: "h-16 px-7 text-lg",
        xl: "h-20 px-8 text-xl",
      },
      full: { true: "w-full", false: "" },
    },
    defaultVariants: { tone: "primary", size: "md", full: false },
  },
);

export interface KidButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof kidButtonVariants> {
  icon?: React.ReactNode;
}

export const KidButton = React.forwardRef<HTMLButtonElement, KidButtonProps>(
  ({ className, tone, size, full, icon, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(kidButtonVariants({ tone, size, full }), className)}
      {...props}
    >
      {icon ? (
        <span aria-hidden="true" className="inline-flex h-8 w-8 items-center justify-center">
          {icon}
        </span>
      ) : null}
      <span>{children}</span>
    </button>
  ),
);
KidButton.displayName = "KidButton";
