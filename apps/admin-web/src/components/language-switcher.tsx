/**
 * LanguageSwitcher — dropdown to switch between English, Shona, and Ndebele.
 * Stores the locale preference in a cookie and reloads.
 */

"use client";

import React, { useTransition } from "react";
import { useLocale } from "next-intl";
import { Globe } from "lucide-react";

const localeLabels: Record<string, string> = {
  en: "English",
  sn: "Shona",
  nd: "Ndebele",
};

const locales = ["en", "sn", "nd"] as const;

export function LanguageSwitcher() {
  const currentLocale = useLocale();
  const [isPending, startTransition] = useTransition();

  const switchLocale = (newLocale: string) => {
    if (newLocale === currentLocale) return;

    startTransition(() => {
      // Set cookie so next-intl picks it up on next request
      document.cookie = `NEXT_LOCALE=${newLocale};path=/;max-age=31536000`;
      window.location.reload();
    });
  };

  return (
    <div className="relative inline-flex items-center gap-1.5">
      <Globe className="h-4 w-4 text-muted-foreground" />
      <select
        value={currentLocale}
        onChange={(e) => switchLocale(e.target.value)}
        disabled={isPending}
        className="appearance-none bg-transparent text-sm text-muted-foreground hover:text-foreground cursor-pointer border-none outline-none pr-4"
        aria-label="Select language"
      >
        {locales.map((l) => (
          <option key={l} value={l}>
            {localeLabels[l]}
          </option>
        ))}
      </select>
    </div>
  );
}
