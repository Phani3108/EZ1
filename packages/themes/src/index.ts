/**
 * @eduzim/themes
 * ==============
 * Persona-based theme tokens for EduZim apps.
 *
 *  - joyful    → parent-web + student surfaces (kid-friendly, bright)
 *  - focus     → teacher-web (clean, professional)
 *  - sovereign → admin-web + ministry-web (Zimbabwe national pride)
 *
 * CSS variables for each theme live in the matching `.css` file and
 * should be imported exactly once per app via globals.css.
 *
 *    @import "@eduzim/themes/joyful.css";
 *
 * Typed token objects below mirror the CSS variables so components
 * and tests can reference them programmatically.
 */

export type PersonaTheme = "joyful" | "focus" | "sovereign";

export interface ThemeTokens {
  name: PersonaTheme;
  /** Tailwind-safe font family (the app loads the actual font via next/font). */
  fontFamily: string;
  /** Light or dual (light+dark). joyful is light-only by policy. */
  modes: ("light" | "dark")[];
  /** Minimum touch target in pixels — joyful is the most generous. */
  minTouchTargetPx: number;
  /** Base text size key (sm|md|lg|xl). */
  baseTextSize: "sm" | "md" | "lg" | "xl";
  /** Whether the theme bundles Zimbabwe national imagery. */
  nationalImagery: boolean;
  /** Whether read-aloud audio support is wired in. */
  readAloud: boolean;
}

export const joyful: ThemeTokens = {
  name: "joyful",
  fontFamily: "Nunito",
  modes: ["light"],
  minTouchTargetPx: 48,
  baseTextSize: "lg",
  nationalImagery: false,
  readAloud: true,
};

export const focus: ThemeTokens = {
  name: "focus",
  fontFamily: "Inter",
  modes: ["light", "dark"],
  minTouchTargetPx: 44,
  baseTextSize: "md",
  nationalImagery: false,
  readAloud: false,
};

export const sovereign: ThemeTokens = {
  name: "sovereign",
  fontFamily: "Inter",
  modes: ["light", "dark"],
  minTouchTargetPx: 44,
  baseTextSize: "md",
  nationalImagery: true,
  readAloud: false,
};

export const themes = { joyful, focus, sovereign } as const;

/** Persona → role mapping used by auth-service to seed defaults. */
export const ROLE_THEME_MAP: Record<string, PersonaTheme> = {
  parent: "joyful",
  student: "joyful",
  guardian: "joyful",
  teacher: "focus",
  head_teacher: "focus",
  admin: "sovereign",
  school_admin: "sovereign",
  ministry: "sovereign",
  provincial_coordinator: "sovereign",
};

/**
 * Zimbabwe flag colour reference (sovereign + joyful accents).
 * Hex values mirrored from `packages/ui/src/tokens/index.ts → colors.zim`.
 */
export const ZIM_FLAG = {
  green: "#008751",
  yellow: "#F5B800",
  red: "#D62828",
  black: "#1A1A1A",
  white: "#FFFFFF",
} as const;
