/**
 * JoyfulCard — joyful theme
 * Pastel-tinted, generously rounded card with an illustration slot.
 * Use for child summaries, announcements directed at parents, fee cards,
 * etc. Pastel tone is chosen per-card to keep the home grid playful.
 */
import React from "react";
import { cn } from "../../lib/utils";

type Tone = "pink" | "peach" | "mint" | "sky" | "lavender" | "sunshine" | "white";

const toneClass: Record<Tone, string> = {
  pink: "bg-joyful-pink",
  peach: "bg-joyful-peach",
  mint: "bg-joyful-mint",
  sky: "bg-joyful-sky",
  lavender: "bg-joyful-lavender",
  sunshine: "bg-joyful-sunshine",
  white: "bg-card",
};

export interface JoyfulCardProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  tone?: Tone;
  illustration?: React.ReactNode;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  footer?: React.ReactNode;
}

export function JoyfulCard({
  tone = "white",
  illustration,
  title,
  subtitle,
  footer,
  className,
  children,
  ...rest
}: JoyfulCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border/60 p-5 shadow-joyful sm:p-6",
        toneClass[tone],
        className,
      )}
      {...rest}
    >
      {illustration ? (
        <div className="mb-3 flex h-24 items-center justify-center" aria-hidden="true">
          {illustration}
        </div>
      ) : null}
      {title ? (
        <h3 className="text-xl font-extrabold tracking-tight text-foreground">
          {title}
        </h3>
      ) : null}
      {subtitle ? (
        <p className="mt-1 text-sm text-foreground/70">{subtitle}</p>
      ) : null}
      {children ? <div className="mt-3">{children}</div> : null}
      {footer ? (
        <div className="mt-4 border-t border-foreground/10 pt-3">{footer}</div>
      ) : null}
    </div>
  );
}
