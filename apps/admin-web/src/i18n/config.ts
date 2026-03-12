/**
 * i18n configuration — supported locales and default.
 */

export const locales = ["en", "sn", "nd"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export const localeNames: Record<Locale, string> = {
  en: "English",
  sn: "Shona",
  nd: "Ndebele",
};
