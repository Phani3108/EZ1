/**
 * Teacher-web — Gate 11a-3: Period-based attendance (T-002, frontend)
 * ====================================================================
 *
 * T-002 (Phase 11a) added period_number to the attendance pipeline.
 * Backend tests in services/academics/tests/test_attendance.py prove
 * the schema + sync engine; these tests prove the teacher-web UI:
 *
 *   1. The attendance tab has a period selector (Day / Period 1–8).
 *   2. The selector defaults to "Day" (period_number = 0), so primary
 *      schools and any user who doesn't touch it behave exactly like
 *      pre-T-002.
 *   3. The selector value threads into the dailyRecords fetch so the
 *      grid shows only the chosen period's marks.
 *   4. The selector value threads into the sync event payload's
 *      `period_number` field so backend upserts target the correct
 *      (student, date, period) tuple.
 *   5. The client_event_id includes the period to avoid dedup collisions
 *      when the same teacher marks period 1 and period 2 on the same day.
 *   6. The period labels are translated into EN / SN / ND.
 *   7. The AttendanceSyncEvent + AttendanceDailyRecord types in
 *      @eduzim/api-client expose period_number.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

function findFirst(candidates: string[]): string | undefined {
  return candidates.find((p) => existsSync(p));
}

const baseFor = (rel: string) => [
  resolve(__dirname, "..", rel),
  resolve(process.cwd(), rel),
  resolve(process.cwd(), "apps/teacher-web", rel),
];

const tabPath = findFirst(
  baseFor("src/app/(teacher)/classes/[id]/attendance-tab.tsx"),
);
const apiTypesPath = findFirst([
  resolve(__dirname, "../../../packages/api-client/src/types.ts"),
  resolve(process.cwd(), "../../packages/api-client/src/types.ts"),
  resolve(process.cwd(), "packages/api-client/src/types.ts"),
]);

function read(p: string | undefined): string {
  if (!p) throw new Error("source file not found");
  return readFileSync(p, "utf8");
}

// ─── attendance-tab.tsx: period selector + payload threading ──────

describe("T-002: period selector state", () => {
  it("source file is reachable", () => {
    expect(tabPath).toBeTruthy();
  });

  it("declares a selectedPeriod state with default 0", () => {
    const src = read(tabPath);
    expect(src).toMatch(
      /useState<number>\s*\(\s*0\s*\)/,
    );
    expect(src).toMatch(/selectedPeriod/);
  });

  it("the period selector renders 9 options (Day + periods 1–8)", () => {
    const src = read(tabPath);
    // The "Day" option uses the periodDay key, the 1–8 options use
    // periodN. Both must appear in the JSX.
    expect(src).toMatch(/t\("periodDay"\)/);
    expect(src).toMatch(/t\("periodN"/);
    // Iterates periods 1 through 8 (an array literal).
    expect(src).toMatch(/\[1,\s*2,\s*3,\s*4,\s*5,\s*6,\s*7,\s*8\]\.map/);
  });

  it("has a test-id on the period select for Playwright", () => {
    expect(read(tabPath)).toMatch(/data-testid="attendance-period-select"/);
  });
});

describe("T-002: fetch + payload thread the period through", () => {
  it("dailyRecords API call includes period_number", () => {
    const src = read(tabPath);
    expect(src).toMatch(
      /attendance\.dailyRecords\(\{[\s\S]{0,200}period_number:\s*String\(selectedPeriod\)/,
    );
  });

  it("the fetch effect depends on selectedPeriod", () => {
    const src = read(tabPath);
    // The deps array of the existingRecords query must list
    // selectedPeriod so changing it triggers a refetch.
    expect(src).toMatch(
      /\[selectedDate,\s*classId,\s*selectedPeriod\]/,
    );
  });

  it("each sync event carries period_number", () => {
    const src = read(tabPath);
    expect(src).toMatch(/period_number:\s*selectedPeriod/);
  });

  it("the client_event_id is namespaced by period to avoid dedup collisions", () => {
    // If the client_event_id were just student+date, marking period 1
    // first and period 2 second would have the second event hit the
    // already-processed dedup index and be silently ignored.
    const src = read(tabPath);
    expect(src).toMatch(/p\$\{selectedPeriod\}/);
  });
});

// ─── i18n parity for period.* keys ─────────────────────────────────

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

describe("T-002: period.* i18n parity across EN / SN / ND", () => {
  const requiredKeys = ["periodLabel", "periodDay", "periodN"] as const;

  for (const [locale, path] of Object.entries(localePaths)) {
    describe(locale, () => {
      it("file exists", () => {
        expect(existsSync(path)).toBe(true);
      });

      it("contains every period.* key under classes", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.classes?.[key]).toBeTruthy();
        }
      });

      it("periodN has the {n} placeholder", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        expect(json.classes?.periodN).toMatch(/\{n\}/);
      });

      it("SN/ND are real translations of periodLabel + periodDay", () => {
        if (locale === "en") return;
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        const en = JSON.parse(readFileSync(localePaths.en, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        expect(json.classes?.periodLabel).not.toBe(en.classes?.periodLabel);
        expect(json.classes?.periodDay).not.toBe(en.classes?.periodDay);
      });
    });
  }
});

// ─── api-client types ──────────────────────────────────────────────

describe("T-002: api-client types expose period_number", () => {
  it("AttendanceSyncEvent has an optional period_number", () => {
    const src = read(apiTypesPath);
    // Look up the SyncEvent block then verify the field is in it.
    const block = src.match(
      /export interface AttendanceSyncEvent[\s\S]*?\n\}/,
    );
    expect(block).toBeTruthy();
    expect(block?.[0]).toMatch(/period_number\?:\s*number/);
  });

  it("AttendanceDailyRecord has an optional period_number", () => {
    const src = read(apiTypesPath);
    const block = src.match(
      /export interface AttendanceDailyRecord[\s\S]*?\n\}/,
    );
    expect(block).toBeTruthy();
    expect(block?.[0]).toMatch(/period_number\?:\s*number/);
  });
});
