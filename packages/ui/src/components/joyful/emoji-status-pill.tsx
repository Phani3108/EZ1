/**
 * EmojiStatusPill — joyful theme
 * Status badge that pairs an emoji, a colour AND a text label so it is
 * understandable for early readers, low-literacy parents and colour-blind
 * users. Never use colour-only status.
 */
import React from "react";
import { cn } from "../../lib/utils";

export type Status = "present" | "absent" | "late" | "excused" | "unknown";

const map: Record<
  Status,
  { emoji: string; label: string; bg: string; text: string }
> = {
  present: {
    emoji: "🟢",
    label: "Present",
    bg: "bg-[hsl(var(--status-present)_/_0.15)]",
    text: "text-[hsl(var(--status-present))]",
  },
  absent: {
    emoji: "🔴",
    label: "Absent",
    bg: "bg-[hsl(var(--status-absent)_/_0.15)]",
    text: "text-[hsl(var(--status-absent))]",
  },
  late: {
    emoji: "🟡",
    label: "Late",
    bg: "bg-[hsl(var(--status-late)_/_0.18)]",
    text: "text-[hsl(var(--status-late))]",
  },
  excused: {
    emoji: "📝",
    label: "Excused",
    bg: "bg-muted",
    text: "text-muted-foreground",
  },
  unknown: {
    emoji: "❔",
    label: "No data",
    bg: "bg-muted",
    text: "text-muted-foreground",
  },
};

export interface EmojiStatusPillProps {
  status: Status;
  /** Override the localised label (i18n owners pass through next-intl). */
  label?: string;
  className?: string;
  size?: "sm" | "md";
}

export function EmojiStatusPill({
  status,
  label,
  className,
  size = "md",
}: EmojiStatusPillProps) {
  const cfg = map[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold",
        cfg.bg,
        cfg.text,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        className,
      )}
      role="status"
      aria-label={label ?? cfg.label}
    >
      <span aria-hidden="true">{cfg.emoji}</span>
      <span>{label ?? cfg.label}</span>
    </span>
  );
}
