/**
 * EduZim Design Tokens v1.0
 * =========================
 * Central source of truth for the design system.
 * Colors, spacing, typography, radii — all defined here.
 *
 * These tokens feed into:
 *  - Tailwind CSS variable overrides (globals.css)
 *  - Component defaults
 *  - Runtime theme utilities
 */

// ─── Core Purple Palette ───
export const colors = {
  primary: {
    50: "#F5F0FA",
    100: "#E9DEFF",
    200: "#D1BBFE",
    300: "#B48EFC",
    400: "#7C3AED",
    500: "#6D3EB3",
    600: "#5B2D8A",
    700: "#4A2370",
    800: "#3A1A59",
    900: "#2A1142",
    DEFAULT: "#5B2D8A",
    foreground: "#FFFFFF",
  },

  // ─── Zimbabwe Identity Accents ───
  zim: {
    gold: "#F5B800",
    green: "#008751",
    red: "#D62828",
    black: "#1A1A1A",
  },

  // ─── Neutral Scale ───
  neutral: {
    50: "#F9FAFB",
    100: "#F3F4F6",
    200: "#E5E7EB",
    300: "#D1D5DB",
    400: "#9CA3AF",
    500: "#6B7280",
    600: "#4B5563",
    700: "#374151",
    800: "#1F2937",
    900: "#111827",
  },

  // ─── Semantic ───
  success: "#059669",
  warning: "#D97706",
  error: "#DC2626",
  info: "#2563EB",
} as const;

// ─── Spacing Tokens ───
export const spacing = {
  pageX: "px-6 lg:px-8",
  pageY: "py-6",
  sectionGap: "space-y-6",
  cardPadding: "p-6",
  compactPadding: "p-4",
} as const;

// ─── Typography Scale ───
export const typography = {
  h1: "text-[28px] leading-[36px] font-bold tracking-tight",
  h2: "text-[22px] leading-[28px] font-semibold tracking-tight",
  h3: "text-[18px] leading-[24px] font-semibold",
  body: "text-[14px] leading-[20px]",
  bodyLg: "text-[15px] leading-[22px]",
  caption: "text-[12px] leading-[16px]",
  label: "text-[13px] leading-[18px] font-medium",
} as const;

// ─── Radii ───
export const radii = {
  sm: "8px",
  md: "10px",
  lg: "12px",
  xl: "16px",
} as const;

// ─── Shadows (soft elevation) ───
export const shadows = {
  sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
  md: "0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)",
  lg: "0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04)",
  card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
} as const;

// ─── Transitions ───
export const transitions = {
  fast: "150ms ease",
  normal: "200ms ease",
  slow: "300ms ease",
} as const;

// ─── Kid Scale (joyful theme) ───
// Generous sizing for early readers, low-literacy users and small fingers.
export const kidScale = {
  touchTarget: "min-h-[48px] min-w-[48px]",
  buttonHeight: "h-14",                 // 56px primary buttons
  iconSize: "h-8 w-8",                  // 32px default
  iconSizeLg: "h-12 w-12",              // 48px hero
  cardPadding: "p-6 sm:p-8",
  cardRadius: "rounded-2xl",            // 16px+
  bodyText: "text-[16px] leading-[1.6]",
  headingText: "text-[26px] leading-[1.3] font-extrabold tracking-tight",
  gap: "gap-5",
} as const;

// ─── Pride Accents (sovereign theme) ───
// Zimbabwe-flag-aware utility classes for the admin/ministry surfaces.
export const prideAccents = {
  flagStripe:
    "[background:var(--zim-flag-gradient)] h-1.5 w-full",
  flagStripeThick:
    "[background:var(--zim-flag-gradient)] h-3 w-full",
  watermarkCoatOfArms: "zim-watermark",
  headerAccentBar:
    "before:content-[''] before:absolute before:left-0 before:top-0 before:h-full before:w-1 before:bg-[hsl(var(--zim-green))]",
} as const;

// ─── Persona theme names (kept here for runtime checks) ───
export const PERSONA_THEMES = ["joyful", "focus", "sovereign"] as const;
export type PersonaThemeName = (typeof PERSONA_THEMES)[number];
