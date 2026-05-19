/** @type {import('tailwindcss').Config} */
module.exports = {
  // joyful theme is light-only by policy — no `dark` class needed.
  darkMode: "class",
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        zim: {
          gold: "hsl(var(--zim-gold))",
          green: "hsl(var(--zim-green))",
          red: "hsl(var(--zim-red))",
        },
        // Joyful pastel palette (status, illustrations, KidButton variants)
        joyful: {
          pink: "hsl(var(--joyful-pink))",
          peach: "hsl(var(--joyful-peach))",
          mint: "hsl(var(--joyful-mint))",
          sky: "hsl(var(--joyful-sky))",
          lavender: "hsl(var(--joyful-lavender))",
          sunshine: "hsl(var(--joyful-sunshine))",
        },
        status: {
          present: "hsl(var(--status-present))",
          absent: "hsl(var(--status-absent))",
          late: "hsl(var(--status-late))",
        },
      },
      borderRadius: {
        // joyful is generous — base 16px feels right for kid surfaces.
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        xl: "20px",
        "2xl": "24px",
        "3xl": "32px",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)",
        joyful: "0 4px 12px -2px rgb(0 135 81 / 0.10), 0 2px 6px -1px rgb(0 0 0 / 0.05)",
      },
      // Minimum touch target utility for joyful (48px).
      minHeight: { touch: "48px" },
      minWidth: { touch: "48px" },
    },
  },
  plugins: [],
};
