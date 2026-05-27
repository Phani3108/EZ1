# ADR 008 — PWA in v1, Teacher Native in Phase 2

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: frontend, mobile, ux

## Context

The current build is three Next.js PWAs (admin-web, parent-web, teacher-web). The audit flagged that teacher is the most demanding user — offline, frequent input, camera, intermittent connectivity — and may benefit from a native app. Three options:

- A — PWA everywhere (current)
- B — PWA now; teacher-native (React Native or Flutter) as Phase 2
- C — Native everywhere

## Decision

- **v1**: PWA for all three apps (admin-web, parent-web, teacher-web).
- **Phase 2**: Build a native teacher app (React Native) once the PWA UX is validated in real classrooms and we know exactly which native capabilities matter (specific notification UX, specific camera workflow, specific offline-storage limit relief).
- Admin remains web-only (desktop-heavy). Parent stays PWA (low-friction, casual use).

## Consequences

### Positive
- One codebase per app for v1.
- Install-to-home from any modern browser. Works on cheap Android.
- Easy update cadence — no app store gates.
- We don't commit to native infrastructure until we know the actual UX wins.

### Negative
- Notifications less reliable on PWA (especially iOS Safari, less of a Zimbabwe concern).
- Camera capture is fine but not best-in-class.
- IndexedDB storage limits can bite at scale (browser caps).
- We will eventually maintain two teacher codebases (web + native) — a known cost.

### Neutral
- React Native vs Flutter is a Phase 2 decision; both are viable. We'll choose based on team expertise at the time.

## Implementation Notes

- v1 PWAs already have Service Workers and manifests. The audit identified gaps (e.g., roster offline cache missing — `task.md` BUG-010, T-014). Phase 11a addresses those.
- Phase 2 native plan deferred to a later ADR (when triggered).
- Provider-pattern code (per ADR 004) is written so a native app can reuse the same API surface — no special "native-only" endpoints.

## Alternatives Considered

### A — PWA everywhere, never native
**Rejected long-term.** Teacher UX will eventually hit PWA ceilings. Native is the right destination for teacher.

### C — Native everywhere day 1
**Rejected.** App store review cycles slow shipping. Cost vs benefit unjustified before we know what the daily teacher app actually needs.

## References

- Plan: §3 Debate 4 (resolved)
- Backlog: `task.md` §1 DEC-008, Phase 11 (PWA polish), future Phase 2 native plan
- Related ADRs: 004 (Provider interfaces are API-only, native-friendly)
