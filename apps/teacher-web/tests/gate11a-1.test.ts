/**
 * Teacher-web — Gate 11a-1: Bulk-mark polish (T-001)
 * ==================================================
 *
 * The "Mark all present / absent" buttons existed before Phase 11 but had
 * a silent-overwrite UX bug: clicking either button blew away every
 * individual mark with no recovery. Teachers who'd painstakingly toggled
 * a handful of Absents lost their work on a stray click.
 *
 * T-001's polish:
 *   1. Snapshot the previous statuses before any bulk op.
 *   2. Show an inline Undo affordance for ~10s after the op.
 *   3. Label the bulk buttons with the affected count
 *      ("Mark all 30 present") so the blast radius is visible.
 *   4. Suppress the Undo when the op was a no-op (everyone already in
 *      the target state — affected=0).
 *   5. Translate the new strings into Shona and Ndebele.
 *
 * These tests are source-string-pattern checks (same convention as
 * `gate10b-4.test.ts`'s BUG-005 regression) — they're fast, run without
 * a real DOM, and they guard the file invariants. Behavior-level
 * Playwright coverage will land alongside the rest of Phase 11a.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ─── Source file locator (mirrors gate10b-4 convention) ────────────

const candidatePaths = [
  resolve(__dirname, "../src/app/(teacher)/classes/[id]/attendance-tab.tsx"),
  resolve(process.cwd(), "src/app/(teacher)/classes/[id]/attendance-tab.tsx"),
  resolve(
    process.cwd(),
    "apps/teacher-web/src/app/(teacher)/classes/[id]/attendance-tab.tsx",
  ),
];
const sourcePath = candidatePaths.find((p) => existsSync(p));

function loadSource(): string {
  if (!sourcePath) throw new Error("attendance-tab.tsx not found");
  return readFileSync(sourcePath, "utf8");
}

// ─── T-001: undo snapshot wiring ───────────────────────────────────

describe("T-001: bulk-mark snapshot wiring", () => {
  it("source file is reachable", () => {
    expect(sourcePath).toBeTruthy();
  });

  it("declares an undoSnapshot state", () => {
    // Must store { previous, affected, action } so we can show the
    // count and the action type in the Undo pill, and restore the
    // exact pre-bulk state on click.
    const src = loadSource();
    expect(src).toMatch(/undoSnapshot/);
    expect(src).toMatch(/setUndoSnapshot/);
  });

  it("snapshots `statuses` before the bulk overwrite", () => {
    const src = loadSource();
    // The snapshot must come from a COPY of `statuses` (otherwise an
    // undo restores the post-overwrite reference, which is a no-op).
    // The implementation copies into a `previous` local, then passes
    // it via shorthand into setUndoSnapshot — so verify both.
    expect(src).toMatch(/const\s+previous\s*=\s*\{\s*\.\.\.statuses\s*\}/);
    expect(src).toMatch(/setUndoSnapshot\(\{[\s\S]{0,120}previous,/);
  });

  it("counts affected rows so a no-op bulk shows no Undo", () => {
    const src = loadSource();
    // The implementation increments `affected` only when before !== status.
    expect(src).toMatch(/affected\s*\+=\s*1/);
    // And bails out of the undo path when affected === 0.
    expect(src).toMatch(/affected\s*===\s*0/);
  });

  it("clears the undo timer on unmount", () => {
    const src = loadSource();
    // Failing to clear the timeout leaks a setTimeout across nav.
    expect(src).toMatch(/clearTimeout\(undoTimeoutRef\.current\)/);
  });

  it("clears the undo snapshot on any individual edit", () => {
    // Individual edits diverge from the bulk-applied state, so the
    // undo target stops being meaningful. We must clear it.
    const src = loadSource();
    expect(src).toMatch(/clearUndo/);
    // And clearUndo must be called from setStatus (the individual-edit handler).
    const setStatusBlock =
      src.match(/const setStatus[\s\S]*?\[clearUndo\]/) ?? [];
    expect(setStatusBlock[0]).toBeTruthy();
  });
});

// ─── T-001: button labels show the affected count ──────────────────

describe("T-001: bulk button labels carry the count", () => {
  it("renders the count-bearing translation keys", () => {
    const src = loadSource();
    expect(src).toMatch(/markAllPresentN/);
    expect(src).toMatch(/markAllAbsentN/);
    expect(src).toMatch(/undoBulkN/);
  });

  it("the labels are parameterised with rosterStudents.length / affected", () => {
    const src = loadSource();
    expect(src).toMatch(/markAllPresentN[\s\S]{0,80}rosterStudents\.length/);
    expect(src).toMatch(/markAllAbsentN[\s\S]{0,80}rosterStudents\.length/);
    expect(src).toMatch(/undoBulkN[\s\S]{0,80}undoSnapshot\.affected/);
  });

  it("attaches test ids so Playwright can target the controls", () => {
    const src = loadSource();
    expect(src).toMatch(/data-testid="attendance-bulk-present"/);
    expect(src).toMatch(/data-testid="attendance-bulk-absent"/);
    expect(src).toMatch(/data-testid="attendance-bulk-undo"/);
  });
});

// ─── T-001: i18n key parity across EN / SN / ND ────────────────────

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

describe("T-001: i18n parity across EN / SN / ND", () => {
  const requiredKeys = [
    "markAllPresentN",
    "markAllAbsentN",
    "undoBulkN",
  ] as const;

  for (const [locale, path] of Object.entries(localePaths)) {
    describe(locale, () => {
      it("file exists", () => {
        expect(existsSync(path)).toBe(true);
      });

      it("contains every T-001 key under classes", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.classes?.[key]).toBeTruthy();
        }
      });

      it("each value contains the {n} placeholder", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.classes?.[key]).toMatch(/\{n\}/);
        }
      });

      it("Shona/Ndebele are NOT English copies (translation parity)", () => {
        // Skip for EN itself.
        if (locale === "en") return;
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        // None of the new keys should equal the English copy verbatim.
        // (`undoBulkN` in Shona = "Dzosera ({n} zvachinjwa)" ≠ EN "Undo (...)").
        const enJson = JSON.parse(readFileSync(localePaths.en, "utf8")) as Record<
          string,
          Record<string, string>
        >;
        for (const key of requiredKeys) {
          expect(json.classes?.[key]).not.toBe(enJson.classes?.[key]);
        }
      });
    });
  }
});
