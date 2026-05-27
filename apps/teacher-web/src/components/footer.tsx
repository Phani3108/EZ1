/**
 * Footer — institutional footer with Zimbabwe identity.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "./language-switcher";

function ZimFlagStripe() {
  return (
    <div className="flex h-1.5 w-full overflow-hidden" aria-hidden="true">
      <div className="flex-1 bg-[#008751]" />
      <div className="flex-1 bg-[#FFD200]" />
      <div className="flex-1 bg-[#D62828]" />
      <div className="flex-1 bg-[#1A1A1A]" />
      <div className="flex-1 bg-[#D62828]" />
      <div className="flex-1 bg-[#FFD200]" />
      <div className="flex-1 bg-[#008751]" />
    </div>
  );
}

export function Footer() {
  const t = useTranslations("footer");
  const year = new Date().getFullYear();

  return (
    <footer className="border-t bg-card mt-auto">
      <ZimFlagStripe />
      <div className="px-6 lg:px-8 py-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-foreground">
              {t("tagline")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("ministry")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("vision2030")}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2">
            <LanguageSwitcher />
            <p className="text-xs text-muted-foreground italic">
              &ldquo;{t("motto")}&rdquo;
            </p>
          </div>
        </div>

        {/* Q-010 (Phase 9): privacy / DPO links — ZDPA + Children's Act. */}
        <nav
          aria-label="Privacy and policy links"
          className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
        >
          <a href="/privacy" className="hover:text-foreground">
            {t("privacyPolicy")}
          </a>
          <span aria-hidden="true">·</span>
          <a href="/retention" className="hover:text-foreground">
            {t("retentionPolicy")}
          </a>
          <span aria-hidden="true">·</span>
          <a
            href={`mailto:${t("dpoEmail")}`}
            className="hover:text-foreground"
          >
            {t("dpoContact", { email: t("dpoEmail") })}
          </a>
        </nav>

        <div className="mt-4 border-t pt-3">
          <p className="text-xs text-muted-foreground text-center">
            {t("copyright", { year: String(year) })}
          </p>
        </div>
      </div>
    </footer>
  );
}
