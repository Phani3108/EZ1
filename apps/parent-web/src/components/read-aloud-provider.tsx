/**
 * ReadAloudProvider
 * ==================
 * Single shared HTMLAudioElement for the joyful theme's "read aloud" feature.
 * Components (e.g. AudioPlayButton) call `play(src)` and the provider:
 *   • pauses any currently-playing clip first (one-at-a-time semantics)
 *   • tracks which `src` is active so multiple buttons can show pause state
 *   • respects the user's `read_aloud_enabled` preference (no-op when disabled)
 *
 * The audio element is created lazily on first interaction — important on
 * iOS Safari where autoplay is blocked until a user gesture, and on low-end
 * Android where we don't want to allocate the media pipeline unnecessarily.
 *
 * NB: We never call browser TTS. All audio is pre-recorded by humans in
 * en/sn/nd and shipped via the content-service (see audio-manifest.ts).
 */
"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useAuth } from "@eduzim/auth";

interface ReadAloudContextValue {
  /** Whether read-aloud is allowed (user preference + audio support). */
  enabled: boolean;
  /** Currently playing src, or null. */
  activeSrc: string | null;
  /** Play a clip; pauses anything else first. No-op if disabled or src is empty. */
  play: (src: string | undefined | null) => Promise<void>;
  /** Pause whatever is playing. */
  stop: () => void;
}

const ReadAloudContext = createContext<ReadAloudContextValue | null>(null);

export function ReadAloudProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [activeSrc, setActiveSrc] = useState<string | null>(null);

  // Server-driven preference; default to enabled for the joyful persona.
  const enabled =
    typeof window !== "undefined" &&
    (user?.preferences?.read_aloud_enabled ?? true);

  const ensureElement = useCallback(() => {
    if (audioRef.current) return audioRef.current;
    const el = new Audio();
    el.preload = "none"; // don't fetch until the user hits play
    el.addEventListener("ended", () => setActiveSrc(null));
    el.addEventListener("pause", () => {
      // Pause may fire from `stop()` — only clear if we actually ended naturally.
      if (el.ended) setActiveSrc(null);
    });
    el.addEventListener("error", () => setActiveSrc(null));
    audioRef.current = el;
    return el;
  }, []);

  const stop = useCallback(() => {
    const el = audioRef.current;
    if (el && !el.paused) el.pause();
    setActiveSrc(null);
  }, []);

  const play = useCallback(
    async (src: string | undefined | null) => {
      if (!enabled || !src) return;
      const el = ensureElement();
      // Toggle behaviour: tapping the active clip stops it.
      if (activeSrc === src && !el.paused) {
        stop();
        return;
      }
      try {
        if (el.src !== src) {
          el.src = src;
          el.load();
        }
        el.currentTime = 0;
        setActiveSrc(src);
        await el.play();
      } catch {
        setActiveSrc(null);
      }
    },
    [activeSrc, enabled, ensureElement, stop],
  );

  // Stop audio when navigating away / unmounting to free the audio pipeline.
  useEffect(() => {
    return () => {
      const el = audioRef.current;
      if (el) {
        el.pause();
        el.src = "";
      }
    };
  }, []);

  const value = useMemo<ReadAloudContextValue>(
    () => ({ enabled, activeSrc, play, stop }),
    [enabled, activeSrc, play, stop],
  );

  return (
    <ReadAloudContext.Provider value={value}>
      {children}
    </ReadAloudContext.Provider>
  );
}

export function useReadAloud(): ReadAloudContextValue {
  const ctx = useContext(ReadAloudContext);
  if (!ctx) {
    // Safe fallback so components don't crash when used outside the provider
    // (e.g. in tests). Always-disabled, no-op implementation.
    return {
      enabled: false,
      activeSrc: null,
      play: async () => {},
      stop: () => {},
    };
  }
  return ctx;
}
