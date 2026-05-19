/**
 * Audio manifest — joyful theme read-aloud clips
 * ================================================
 * Maps i18n keys to pre-recorded audio files for each supported locale.
 * Clips are short (< 4s) so they fit in the Workbox pre-cache budget.
 *
 * The actual .mp3 files live in the content-service under /media/audio/...
 * and are referenced here by stable, content-hashed paths. Until the
 * content-service ships the recordings we keep this manifest empty —
 * components fall back to silent state and never block UI.
 */

export type SupportedLocale = "en" | "sn" | "nd";

export interface AudioClip {
  /** i18n message key, e.g. "home.welcome". */
  key: string;
  /** Map of locale → URL (relative to the API base). */
  sources: Partial<Record<SupportedLocale, string>>;
  /** Approximate duration in seconds (for pre-cache budgeting). */
  durationSec?: number;
}

export const AUDIO_MANIFEST: AudioClip[] = [
  // Empty until content-service ships recordings.
  // Example shape kept here for typing:
  // {
  //   key: "home.welcome",
  //   sources: {
  //     en: "/media/audio/en/home-welcome.v1.mp3",
  //     sn: "/media/audio/sn/home-welcome.v1.mp3",
  //     nd: "/media/audio/nd/home-welcome.v1.mp3",
  //   },
  //   durationSec: 2.4,
  // },
];

export function getClip(
  key: string,
  locale: SupportedLocale,
): string | undefined {
  return AUDIO_MANIFEST.find((c) => c.key === key)?.sources[locale];
}
