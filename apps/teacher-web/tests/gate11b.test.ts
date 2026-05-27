/**
 * Teacher-web — Gate 11b: Messaging + simplified announcement form
 * ===================================================================
 *
 * Phase 11b ships three things teacher-web-side:
 *   T-011: parent-teacher 1:1 messaging — inbox + thread page
 *   RULE-4: simplify announcement-create form (no audience picker)
 *   T-008: file attachments (backend-only on teacher-web for now —
 *          the upload UI plugs in during the matching consumer phases)
 *
 * Source-pattern + i18n parity tests below; behaviour coverage will
 * land via Playwright in a Phase 11g sweep.
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
const read = (p: string | undefined) => {
  if (!p) throw new Error("source file not found");
  return readFileSync(p, "utf8");
};

const inboxPath = findFirst(baseFor("src/app/(teacher)/messages/page.tsx"));
const threadPath = findFirst(baseFor("src/app/(teacher)/messages/[id]/page.tsx"));
const layoutPath = findFirst(baseFor("src/app/(teacher)/layout.tsx"));
const annPath = findFirst(baseFor("src/app/(teacher)/announcements/page.tsx"));

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


// ─── T-011 inbox + thread ──────────────────────────────────────────


describe("T-011: messages inbox page", () => {
  it("source file exists", () => {
    expect(inboxPath).toBeTruthy();
  });

  it("calls comm.listThreads", () => {
    expect(read(inboxPath)).toMatch(/comm\.listThreads\(\)/);
  });

  it("renders an unread badge when unread_count > 0", () => {
    const src = read(inboxPath);
    expect(src).toMatch(/unread_count\s*>\s*0/);
    expect(src).toMatch(/data-testid="thread-unread-badge"/);
  });

  it("exposes a thread-list test id for Playwright", () => {
    expect(read(inboxPath)).toMatch(/data-testid="messages-thread-list"/);
  });
});

describe("T-011: thread detail page", () => {
  it("source file exists", () => {
    expect(threadPath).toBeTruthy();
  });

  it("calls comm.markThreadRead on mount", () => {
    // Marking read should happen when the data arrives, otherwise the
    // unread badge sits at >0 even when the teacher is staring at the
    // thread.
    expect(read(threadPath)).toMatch(/comm\.markThreadRead/);
  });

  it("compose input + send button have test ids", () => {
    const src = read(threadPath);
    expect(src).toMatch(/data-testid="messages-compose-input"/);
    expect(src).toMatch(/data-testid="messages-send-button"/);
  });

  it("send is debounced behind isSending state", () => {
    const src = read(threadPath);
    // Double-clicks must not double-send.
    expect(src).toMatch(/isSending/);
    expect(src).toMatch(/disabled=\{isSending/);
  });

  it("Enter sends, Shift+Enter inserts a newline", () => {
    const src = read(threadPath);
    expect(src).toMatch(/e\.key\s*===\s*"Enter"\s*&&\s*!e\.shiftKey/);
  });
});

describe("T-011: layout nav exposes Messages", () => {
  it("adds the messages nav item", () => {
    const src = read(layoutPath);
    expect(src).toMatch(/{ key: "messages", href: "\/messages"/);
  });
});


// ─── RULE-4 simplified announcement form ───────────────────────────


describe("RULE-4: simplified teacher announcement form", () => {
  it("source file exists", () => {
    expect(annPath).toBeTruthy();
  });

  it("does NOT contain a class picker for teachers", () => {
    const src = read(annPath);
    // The old form rendered a <select> populated from
    // teacher.getMyClasses(). Both should be gone.
    expect(src).not.toMatch(/teacher\.getMyClasses\(\)/);
    expect(src).not.toMatch(/setClassId/);
  });

  it("posts TEACHER_CLASSES as the audience type", () => {
    const src = read(annPath);
    expect(src).toMatch(/audience:\s*{\s*type:\s*"TEACHER_CLASSES"\s*}/);
  });

  it("shows a non-picker hint explaining the audience", () => {
    const src = read(annPath);
    expect(src).toMatch(/audienceHintTeacherClasses/);
    expect(src).toMatch(/data-testid="teacher-announcement-audience-hint"/);
  });
});


// ─── i18n parity ───────────────────────────────────────────────────


describe("Phase 11b i18n parity: messages.* + announcements.audienceHint", () => {
  const messagesKeys = [
    "title", "threadsCount", "noThreads", "noThreadsHint",
    "threadWithParent", "noMessagesYet", "threadDetailTitle",
    "loading", "composePlaceholder", "send", "redacted",
  ] as const;

  for (const [locale, path] of Object.entries(localePaths)) {
    describe(locale, () => {
      it("messages.* contains all required keys", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        for (const k of messagesKeys) {
          expect(json.messages?.[k]).toBeTruthy();
        }
      });

      it("announcements.audienceHintTeacherClasses is set", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        expect(json.announcements?.audienceHintTeacherClasses).toBeTruthy();
      });

      it("nav.messages is set", () => {
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        expect(json.nav?.messages).toBeTruthy();
      });

      it("Shona/Ndebele are not English copies for messages.title", () => {
        if (locale === "en") return;
        const json = JSON.parse(readFileSync(path, "utf8")) as Record<
          string, Record<string, string>
        >;
        const en = JSON.parse(readFileSync(localePaths.en, "utf8")) as Record<
          string, Record<string, string>
        >;
        expect(json.messages?.title).not.toBe(en.messages?.title);
      });
    });
  }
});
