/**
 * Teacher-web — Gate 11a-2: Offline roster cache + offline badge (T-014)
 * ========================================================================
 *
 * The class-detail roster fetches went straight to the network with no
 * cache layer. When a teacher's device dropped connectivity mid-period
 * the page hung on its skeleton loader forever (BUG-010), and the
 * teacher had no signal that the cause was offline (vs. a slow server).
 *
 * T-014 closes both:
 *   1. `useCachedApiQuery` paints from IndexedDB-cached data immediately
 *      when a cache hit exists, then refreshes in the background.
 *   2. Cache failures and stale cache are tolerant — the user always
 *      sees something useful instead of an error.
 *   3. `OfflineBadge` surfaces both the live network state ("Offline")
 *      and the freshness state ("Showing cached data") next to the
 *      class header.
 *   4. EN / SN / ND have a dedicated `offline.*` translation namespace.
 *
 * These tests are source-string-pattern checks. The behavior-level
 * contract for the underlying OfflineCache is covered by the
 * @eduzim/offline-core package's own cache.test.ts.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ─── Source locators ───────────────────────────────────────────────

function findFirst(candidates: string[]): string | undefined {
  return candidates.find((p) => existsSync(p));
}

const baseFor = (rel: string) => [
  resolve(__dirname, "..", rel),
  resolve(process.cwd(), rel),
  resolve(process.cwd(), "apps/teacher-web", rel),
];

const hookPath = findFirst(baseFor("src/hooks/use-cached-api-query.ts"));
const badgePath = findFirst(baseFor("src/components/offline-badge.tsx"));
const classPagePath = findFirst(
  baseFor("src/app/(teacher)/classes/[id]/page.tsx"),
);

function read(path: string | undefined): string {
  if (!path) throw new Error("source file not found");
  return readFileSync(path, "utf8");
}

// ─── useCachedApiQuery contract ────────────────────────────────────

describe("T-014: useCachedApiQuery hook", () => {
  it("hook source file exists", () => {
    expect(hookPath).toBeTruthy();
  });

  it("imports OfflineCache from offline-core", () => {
    expect(read(hookPath)).toMatch(
      /import\s*{\s*OfflineCache\s*}\s*from\s*"@eduzim\/offline-core"/,
    );
  });

  it("uses a single shared cache instance (one per module load)", () => {
    // Creating a new OfflineCache per render would still be correct
    // (the underlying IndexedDB is a singleton), but the shared
    // instance is the cheaper/clearer pattern.
    const src = read(hookPath);
    expect(src).toMatch(/const\s+cache\s*=\s*new\s+OfflineCache\(\)/);
  });

  it("exposes `fromCache` in its return type", () => {
    // The whole point of the hook over plain useApiQuery is signalling
    // when data is stale. The UI needs the flag.
    const src = read(hookPath);
    expect(src).toMatch(/fromCache\s*:\s*boolean/);
  });

  it("defaults the TTL to 24 hours", () => {
    // 24h is the documented default — one school day. Changing it
    // is a meaningful product decision and should fail this test.
    const src = read(hookPath);
    expect(src).toMatch(/DEFAULT_TTL_MS\s*=\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000/);
  });

  it("paints from cache BEFORE awaiting the network", () => {
    // The `cache.get` call must run before `fetcher()`. Ordering matters
    // because a slow network on a cache hit would defeat the purpose.
    const src = read(hookPath);
    const getIdx = src.indexOf("cache.get<T>");
    const fetcherIdx = src.indexOf("await fetcher()");
    expect(getIdx).toBeGreaterThan(-1);
    expect(fetcherIdx).toBeGreaterThan(getIdx);
  });

  it("write-through caches on successful fetch", () => {
    // The next mount has to find the cache populated.
    const src = read(hookPath);
    expect(src).toMatch(/await\s+cache\.set\(cacheKey,\s*result\.data,\s*ttlMs\)/);
  });

  it("does NOT surface a network error when cached data is showing", () => {
    // The user has a roster on screen; they don't need to be alarmed.
    const src = read(hookPath);
    expect(src).toMatch(/if\s*\(cachedHit\)\s*\{[\s\S]{0,200}return;/);
  });

  it("swallows cache read/write errors (non-fatal)", () => {
    // Safari private mode + some Android browsers block IndexedDB.
    // The hook must not crash there.
    const src = read(hookPath);
    // Two try/catch blocks: one around cache.get, one around cache.set.
    const catchCount = (src.match(/}\s*catch\s*{/g) ?? []).length;
    expect(catchCount).toBeGreaterThanOrEqual(2);
  });
});

// ─── OfflineBadge contract ─────────────────────────────────────────

describe("T-014: OfflineBadge component", () => {
  it("source file exists", () => {
    expect(badgePath).toBeTruthy();
  });

  it("supports both 'status' and 'cache' modes", () => {
    const src = read(badgePath);
    expect(src).toMatch(/mode\s*:\s*"status"\s*\|\s*"cache"/);
  });

  it("renders nothing in 'status' mode while online (no visual noise)", () => {
    // A persistent "online" pill is clutter. The badge must only
    // appear when offline.
    const src = read(badgePath);
    expect(src).toMatch(/if\s*\(mode\s*===\s*"status"\)[\s\S]{0,200}if\s*\(online\)\s*return\s+null/);
  });

  it("renders nothing in 'cache' mode when fromCache is false", () => {
    const src = read(badgePath);
    expect(src).toMatch(/if\s*\(!fromCache\)\s*return\s+null/);
  });

  it("uses next-intl translations from the 'offline' namespace", () => {
    const src = read(badgePath);
    expect(src).toMatch(/useTranslations\("offline"\)/);
  });

  it("exposes Playwright test ids", () => {
    const src = read(badgePath);
    expect(src).toMatch(/data-testid="offline-status-badge"/);
    expect(src).toMatch(/data-testid="cache-badge"/);
  });

  it("uses aria-live for screen-reader announcement of the offline state", () => {
    // Going offline is a state change the user needs to be told about.
    const src = read(badgePath);
    expect(src).toMatch(/aria-live="polite"/);
  });
});

// ─── Class-detail page wiring ──────────────────────────────────────

describe("T-014: class detail page integration", () => {
  it("imports useCachedApiQuery and OfflineBadge", () => {
    const src = read(classPagePath);
    expect(src).toMatch(/from\s*"@\/hooks\/use-cached-api-query"/);
    expect(src).toMatch(/from\s*"@\/components\/offline-badge"/);
  });

  it("the roster enrollments fetch uses the cached hook", () => {
    // We MUST cache the enrollments (per-class) and the student list
    // (global). Both are large reads; the network round-trip
    // dominates the spinner time.
    const src = read(classPagePath);
    expect(src).toMatch(/useCachedApiQuery<Enrollment\[\]>/);
    expect(src).toMatch(/cacheKey:\s*`roster:enrollments:\$\{classId\}`/);
  });

  it("the student list fetch uses the cached hook with a global key", () => {
    const src = read(classPagePath);
    expect(src).toMatch(
      /useCachedApiQuery<\s*[\s\S]{0,40}\s*>\([\s\S]{0,200}cacheKey:\s*"roster:students:list"/,
    );
  });

  it("renders both status- and cache-mode badges", () => {
    const src = read(classPagePath);
    expect(src).toMatch(/<OfflineBadge\s+mode="status"\s*\/>/);
    expect(src).toMatch(/<OfflineBadge\s+mode="cache"\s+fromCache=\{rosterFromCache\}/);
  });
});

// ─── i18n parity for the offline.* namespace ───────────────────────

const localePaths = {
  en: resolve(
    process.cwd(),
    process.cwd().endsWith("teacher-web")
      ? "messages/en.json"
      : "apps/teacher-web/messages/en.json",
  ),
  sn: resolve(
    process.cwd(),
    process.cwd().endsWith("teacher-web")
      ? "messages/sn.json"
      : "apps/teacher-web/messages/sn.json",
  ),
  nd: resolve(
    process.cwd(),
    process.cwd().endsWith("teacher-web")
      ? "messages/nd.json"
      : "apps/teacher-web/messages/nd.json",
  ),
};

describe("T-014: offline.* i18n parity across EN / SN / ND", () => {
  const requiredKeys = ["offline", "showingCached", "offlineShowingCached"] as const;

  for (const [locale, path] of Object.entries(localePaths)) {
    describe(locale, () => {
      it("file exists", () => {
        expect(existsSync(path)).toBe(true);
      });

      it("contains every offline.* key", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.offline?.[key]).toBeTruthy();
        }
      });

      it("SN/ND are real translations, not English copies", () => {
        if (locale === "en") return;
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        const en = JSON.parse(readFileSync(localePaths.en, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.offline?.[key]).not.toBe(en.offline?.[key]);
        }
      });
    });
  }
});
