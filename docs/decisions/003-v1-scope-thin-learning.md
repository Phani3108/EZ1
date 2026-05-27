# ADR 003 — v1 Scope: ERP + Thin Learning Layer

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: product, scope, learning

## Context

The audit found that v1 was effectively a "digital school administration" product — students wouldn't experience anything transformative. Three scope options were debated:

- A — Pure ERP, defer all learning content to Phase 2
- B — ERP + thin learning layer (lesson plans, objective quizzes, one content partner)
- C — Defer entirely, position v1 to admins only

The founder chose B.

## Decision

v1 scope = **ERP + thin learning layer**.

The "thin" learning layer comprises:

1. **Lesson plan library** — native data model; schools author and share lesson plans across teachers and grades.
2. **Objective quiz creator** — MCQ + short-answer auto-graded. Native data model; runs offline-capable.
3. **Content delivery** — `ContentProvider` interface (see ADR 004); reference implementations include Khan Academy Lite, Worldreader, manual upload. No native content library.

What's **NOT** in v1 (Phase 2+):
- AI tutoring
- Personalised learning paths
- Career guidance
- Skills marketplace
- Adaptive assessment

## Consequences

### Positive
- v1 narrative shifts from "digital register" to "learning platform". Material change in perception for students, parents, and Ministry alike.
- Teachers gain a real productivity tool (lesson plan library + quiz creator) that supports the rest of the suite.
- Provides the substrate that future Phase 2 features (AI tutoring, paths) can plug into.

### Negative
- Real scope addition: roughly 6 weeks of build (per audit estimate) for the native side. Content provider wiring is faster because of DEC-004 (integration, not native).
- We must guard against scope creep into "full LMS" territory. The thinness is the discipline.

### Neutral
- The Khan Academy Lite / Worldreader / RACHEL question is deferred to Phase 15 implementation: any one is enough; provider interface (per ADR 004) makes the choice non-permanent.

## Alternatives Considered

### A — Pure ERP, learning deferred
**Rejected.** Underwhelms students. Misses the engagement story for parents. Makes v1 hard to differentiate from existing manual-replacement tools.

### C — Defer learning, sell to admins only
**Rejected.** Misses the bigger market and the founder's stated mission (children's future). Admin-only positioning caps adoption.

## Implementation Notes

- Native: `services/academics/` gets lesson plan + quiz models, repository, endpoints.
- Integration: `ContentProvider` interface in `services/academics/providers/content/`; reference impls in `providers/content/khan_academy_lite.py`, `providers/content/worldreader.py`, `providers/content/manual_upload.py`.
- Per-school provider selection stored on `school.providers.content`.
- Student role on parent-web (ADR 002) consumes both native (quizzes) and provider-sourced content uniformly.

## References

- Plan: §3 Debate 11 (resolved)
- Backlog: `task.md` §1 DEC-003, Phase 15
- Related ADRs: 002 (student app), 004 (integration-only providers)
