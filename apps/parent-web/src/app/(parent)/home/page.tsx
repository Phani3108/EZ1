/**
 * Parent Home — joyful theme
 * ===========================
 * Big colourful cards, one per child. Status pill uses emoji + label
 * (never colour-only) so it passes WCAG 1.4.1. Read-aloud button is
 * present but disabled until the audio-manifest ships clips for the
 * locale.
 */

"use client";

import React from "react";
import Link from "next/link";
import { useTranslations, useLocale } from "next-intl";
import { useAuth } from "@eduzim/auth";
import {
  JoyfulCard,
  BigStat,
  EmojiStatusPill,
  IllustratedEmptyState,
  AudioPlayButton,
  KidButton,
  getClip,
  type SupportedLocale,
  type EmojiStatus,
} from "@eduzim/ui";
import { Loader2, AlertCircle, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { student } from "@/lib/api";
import type { Student } from "@eduzim/api-client";

function timeOfDay(): "Morning" | "Afternoon" | "Evening" {
  const h = new Date().getHours();
  if (h < 12) return "Morning";
  if (h < 17) return "Afternoon";
  return "Evening";
}

const CARD_TONES = ["pink", "peach", "mint", "sky", "lavender", "sunshine"] as const;

export default function ParentHomePage() {
  const t = useTranslations("parent.home");
  const tStatus = useTranslations("parent.status");
  const locale = (useLocale() as SupportedLocale) || "en";
  const { user } = useAuth();

  const greetingKey = `greeting${timeOfDay()}` as
    | "greetingMorning"
    | "greetingAfternoon"
    | "greetingEvening";

  const firstName = user?.full_name?.split(" ")[0] ?? "Parent";

  const { data: children, isLoading, error } = useApiQuery<Student[]>(
    () => student.getMyChildren(),
    [],
  );

  return (
    <div className="space-y-6">
      {/* Greeting hero */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold leading-tight text-foreground">
            {t(greetingKey, { name: firstName })}
          </h1>
          <p className="mt-2 text-lg text-muted-foreground">{t("subtitle")}</p>
        </div>
        <AudioPlayButton
          ariaLabel={t("readAloud")}
          src={getClip("parent.home.subtitle", locale)}
          size="lg"
        />
      </div>

      {/* Children grid */}
      <section aria-labelledby="children-heading" className="space-y-3">
        <h2 id="children-heading" className="text-xl font-bold">
          {t("yourChildren")}
        </h2>

        {isLoading && (
          <JoyfulCard tone="white" className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </JoyfulCard>
        )}

        {error && (
          <JoyfulCard tone="peach" className="flex items-start gap-3">
            <AlertCircle className="h-6 w-6 shrink-0 text-status-absent" />
            <p className="text-base text-foreground">{error.message}</p>
          </JoyfulCard>
        )}

        {!isLoading && !error && children && children.length === 0 && (
          <IllustratedEmptyState
            title={t("noChildren")}
            illustration={
              <svg
                viewBox="0 0 120 120"
                className="h-24 w-24"
                aria-hidden="true"
              >
                <circle cx="60" cy="60" r="55" fill="hsl(var(--joyful-sunshine))" />
                <circle cx="45" cy="50" r="5" fill="#1A1A1A" />
                <circle cx="75" cy="50" r="5" fill="#1A1A1A" />
                <path
                  d="M 40 75 Q 60 90 80 75"
                  stroke="#1A1A1A"
                  strokeWidth="4"
                  fill="none"
                  strokeLinecap="round"
                />
              </svg>
            }
          />
        )}

        {!isLoading && !error && children && children.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {children.map((child, idx) => (
              <ChildCard
                key={child.id}
                child={child}
                tone={CARD_TONES[idx % CARD_TONES.length]}
                ctaLabel={t("viewChild")}
                attendanceLabel={t("attendanceToday")}
                feesLabel={t("feesDue")}
                statusLabel={(s) =>
                  tStatus(
                    s as
                      | "present"
                      | "absent"
                      | "late"
                      | "excused"
                      | "unknown",
                  )
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

interface ChildCardProps {
  child: Student;
  tone: (typeof CARD_TONES)[number];
  ctaLabel: string;
  attendanceLabel: string;
  feesLabel: string;
  statusLabel: (s: EmojiStatus) => string;
}

function ChildCard({
  child,
  tone,
  ctaLabel,
  attendanceLabel,
  feesLabel,
  statusLabel,
}: ChildCardProps) {
  // Until attendance + fees APIs surface per-child summaries on this endpoint
  // we render `unknown` placeholders. Real wiring lands when the student
  // endpoint is extended with `today_attendance` / `outstanding_fees`.
  const attendanceStatus: EmojiStatus = "unknown";
  const outstanding: number | null = null;

  return (
    <JoyfulCard tone={tone}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xl font-extrabold text-foreground">
            {child.first_name} {child.last_name}
          </p>
          <p className="text-sm text-foreground/70">{child.student_code}</p>
        </div>
        <EmojiStatusPill status={attendanceStatus} label={statusLabel(attendanceStatus)} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <BigStat
          label={attendanceLabel}
          value={statusLabel(attendanceStatus)}
        />
        <BigStat
          label={feesLabel}
          value={outstanding === null ? "—" : `$${(outstanding as number).toFixed(2)}`}
        />
      </div>

      <Link href={`/children/${child.id}`} className="mt-4 block">
        <KidButton tone="primary" size="md" className="w-full justify-center">
          {ctaLabel}
          <ChevronRight className="h-5 w-5" aria-hidden="true" />
        </KidButton>
      </Link>
    </JoyfulCard>
  );
}
