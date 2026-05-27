/**
 * Teacher-web — Gate 11c: Gradebook + Comment Bank + Voice Notes
 * =================================================================
 *
 * T-015 (gradebook), T-007 (comment bank), T-009 (voice notes).
 * Source-pattern + i18n parity checks.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const baseFor = (rel: string) => [
  resolve(__dirname, "..", rel),
  resolve(process.cwd(), rel),
  resolve(process.cwd(), "apps/teacher-web", rel),
];
const findFirst = (cs: string[]) => cs.find((p) => existsSync(p));
const read = (p: string | undefined) => {
  if (!p) throw new Error("source file not found");
  return readFileSync(p, "utf8");
};

const indexPath = findFirst(baseFor("src/app/(teacher)/gradebook/page.tsx"));
const classPath = findFirst(
  baseFor("src/app/(teacher)/gradebook/[classId]/page.tsx"),
);
const recorderPath = findFirst(baseFor("src/components/voice-recorder.tsx"));
const layoutPath = findFirst(baseFor("src/app/(teacher)/layout.tsx"));

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

// ─── T-015 gradebook ───────────────────────────────────────────────

describe("T-015: gradebook pages exist + wired", () => {
  it("index page and class page exist", () => {
    expect(indexPath).toBeTruthy();
    expect(classPath).toBeTruthy();
  });

  it("class page calls assessment.classGradebook", () => {
    expect(read(classPath)).toMatch(/assessment\.classGradebook/);
  });

  it("class page test-ids expose the gradebook table + term filter", () => {
    const src = read(classPath);
    expect(src).toMatch(/data-testid="gradebook-table"/);
    expect(src).toMatch(/data-testid="gradebook-term-filter"/);
  });

  it("nav layout adds the gradebook entry", () => {
    expect(read(layoutPath)).toMatch(
      /\{ key: "gradebook", href: "\/gradebook"/,
    );
  });
});

// ─── T-009 voice recorder ──────────────────────────────────────────

describe("T-009: voice recorder component", () => {
  it("source file exists", () => {
    expect(recorderPath).toBeTruthy();
  });

  it("checks MediaRecorder + getUserMedia support before recording", () => {
    const src = read(recorderPath);
    expect(src).toMatch(/navigator\.mediaDevices\?\.getUserMedia/);
    expect(src).toMatch(/window\.MediaRecorder/);
  });

  it("auto-stops at maxSeconds via setTimeout", () => {
    expect(read(recorderPath)).toMatch(/maxSeconds\s*\*\s*1000/);
  });

  it("uploads to /api/v1/comm/attachments with owner_kind + owner_id", () => {
    const src = read(recorderPath);
    // Path appears inside a template literal — match either form.
    expect(src).toMatch(/\/api\/v1\/comm\/attachments/);
    expect(src).toMatch(/owner_kind/);
    expect(src).toMatch(/owner_id/);
  });

  it("releases media tracks + URL.revokeObjectURL on unmount", () => {
    const src = read(recorderPath);
    expect(src).toMatch(/stream\.getTracks\(\)\.forEach/);
    expect(src).toMatch(/URL\.revokeObjectURL/);
  });

  it("exposes test ids for record/stop/upload/discard", () => {
    const src = read(recorderPath);
    expect(src).toMatch(/data-testid="voice-record-start"/);
    expect(src).toMatch(/data-testid="voice-record-stop"/);
    expect(src).toMatch(/data-testid="voice-record-upload"/);
    expect(src).toMatch(/data-testid="voice-record-discard"/);
  });
});

// ─── i18n parity ───────────────────────────────────────────────────

describe("Phase 11c i18n parity: gradebook.* + voiceNotes.*", () => {
  const gradebookKeys = [
    "title", "description", "noClasses", "noAssessments", "loading",
    "termFilterLabel", "termFilterPlaceholder", "studentColumn",
    "averageColumn", "absentShort",
  ] as const;
  const voiceKeys = [
    "record", "stop", "upload", "uploading",
    "notSupported", "error", "retry",
  ] as const;

  for (const [locale, path] of Object.entries(localePaths)) {
    describe(locale, () => {
      it("gradebook.* contains all required keys", () => {
        const j = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        for (const k of gradebookKeys) {
          expect(j.gradebook?.[k]).toBeTruthy();
        }
      });
      it("voiceNotes.* contains all required keys", () => {
        const j = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        for (const k of voiceKeys) {
          expect(j.voiceNotes?.[k]).toBeTruthy();
        }
      });
      it("nav.gradebook is set", () => {
        const j = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        expect(j.nav?.gradebook).toBeTruthy();
      });
      it("SN/ND are not English copies for gradebook.title", () => {
        if (locale === "en") return;
        const j = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        const en = JSON.parse(readFileSync(localePaths.en, "utf8")) as Record<
          string, Record<string, string>
        >;
        expect(j.gradebook?.title).not.toBe(en.gradebook?.title);
      });
    });
  }
});
