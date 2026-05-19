#!/usr/bin/env bash
# ============================================================
# Theme-bleed guard
# ============================================================
# Ensures persona themes stay in their lane:
#   * joyful-*    classes / @eduzim/themes/joyful  → parent-web only
#   * sovereign-* classes / @eduzim/themes/sovereign / zim-watermark
#     and FlagHeader / MinistryStatCard / ProvinceMap / OfficialBadge
#                                                    → admin-web (+ future ministry-web) only
#   * KidButton / JoyfulCard / EmojiStatusPill / BigStat / AudioPlayButton
#                                                    → parent-web only
#
# Run via: `pnpm lint:theme-bleed` (also in CI).
# Fails (exit 1) on any cross-persona import / class usage.
# ============================================================
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }

EXIT=0

# Helper: grep -rn excluding node_modules / .next / build dirs.
search() {
  grep -rn --include='*.ts' --include='*.tsx' --include='*.css' \
    --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=dist --exclude-dir=.turbo \
    "$@" 2>/dev/null || true
}

# 1. Joyful must not appear outside parent-web
JOYFUL_PATTERN='joyful-|@eduzim/themes/joyful|JoyfulCard|KidButton|EmojiStatusPill|BigStat|IllustratedEmptyState|AudioPlayButton'
for app in apps/admin-web apps/teacher-web; do
  HIT=$(search -E "$JOYFUL_PATTERN" "$app/src" || true)
  if [ -n "$HIT" ]; then
    red "✗ Joyful theme bleed in $app:"
    echo "$HIT"
    EXIT=1
  fi
done

# 2. Sovereign must not appear outside admin-web (future: ministry-web)
SOVEREIGN_PATTERN='@eduzim/themes/sovereign|zim-watermark|zim-flag-gradient|FlagHeader|MinistryStatCard|ProvinceMap|OfficialBadge'
for app in apps/teacher-web apps/parent-web; do
  HIT=$(search -E "$SOVEREIGN_PATTERN" "$app/src" || true)
  if [ -n "$HIT" ]; then
    red "✗ Sovereign theme bleed in $app:"
    echo "$HIT"
    EXIT=1
  fi
done

if [ "$EXIT" -eq 0 ]; then
  green "✓ No theme bleed detected."
fi

exit "$EXIT"
