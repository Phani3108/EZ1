/**
 * AudioPlayButton — joyful theme
 * Read-aloud trigger. Plays a pre-recorded clip (NOT TTS) so it works
 * fully offline once the audio bundle is cached.
 *
 * Wire up the `src` from the audio-manifest for the current locale, or
 * pass an HTMLAudioElement instance via `audio` if you manage playback
 * higher up the tree (preferred when many buttons share one player).
 */
"use client";

import React from "react";
import { cn } from "../../lib/utils";

export interface AudioPlayButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** URL of the pre-recorded clip (locale-specific). */
  src?: string;
  /** Accessible label, e.g. "Read this aloud". */
  ariaLabel: string;
  /** Optional shared audio element. */
  audio?: HTMLAudioElement | null;
  /** Visual size. */
  size?: "sm" | "md" | "lg";
}

const sizeClass: Record<NonNullable<AudioPlayButtonProps["size"]>, string> = {
  sm: "h-10 w-10",
  md: "h-12 w-12",
  lg: "h-14 w-14",
};

export function AudioPlayButton({
  src,
  ariaLabel,
  audio,
  size = "md",
  className,
  ...rest
}: AudioPlayButtonProps) {
  const [playing, setPlaying] = React.useState(false);
  const localAudioRef = React.useRef<HTMLAudioElement | null>(null);

  const getAudio = React.useCallback((): HTMLAudioElement | null => {
    if (audio) return audio;
    if (typeof window === "undefined") return null;
    if (!localAudioRef.current && src) {
      localAudioRef.current = new Audio(src);
      localAudioRef.current.preload = "none";
    }
    return localAudioRef.current;
  }, [audio, src]);

  React.useEffect(() => {
    const a = getAudio();
    if (!a) return;
    const onEnd = () => setPlaying(false);
    a.addEventListener("ended", onEnd);
    return () => a.removeEventListener("ended", onEnd);
  }, [getAudio]);

  const toggle = () => {
    const a = getAudio();
    if (!a) return;
    if (playing) {
      a.pause();
      a.currentTime = 0;
      setPlaying(false);
    } else {
      a.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={ariaLabel}
      aria-pressed={playing}
      disabled={!src && !audio}
      className={cn(
        "inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground shadow-joyful transition active:scale-95 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/40 disabled:opacity-50",
        sizeClass[size],
        className,
      )}
      {...rest}
    >
      {/* Inline icon — avoids a dep, keeps bundle tiny */}
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="h-1/2 w-1/2"
      >
        {playing ? (
          <>
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </>
        ) : (
          <path d="M8 5v14l11-7L8 5z" />
        )}
      </svg>
    </button>
  );
}
