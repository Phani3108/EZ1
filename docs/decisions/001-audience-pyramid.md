# ADR 001 — Audience Pyramid

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: product, prioritisation

## Context

The earlier ChatGPT-driven planning sessions framed EduZim as a Ministry-pitch product first. The audit (three parallel Explore agents reviewing backend, frontend, and infra) revealed that this framing under-served the **daily users** — teachers, students, parents, school admins — while over-investing in Ministry-facing surfaces that the Ministry itself only needs as dashboards.

The founder course-corrected explicitly:

> "This is to be used by teachers, students, parents and finally the admin of schools to see and ministry to see the complete data (mostly charts and highlights will do for them)."

## Decision

The audience priority for every UX, IA, and feature-prioritisation decision is:

```
Teacher  >  Student  >  Parent  >  School Admin  >>  Ministry
```

- **Teacher** is the primary daily user. Every-period workflow. Most demanding.
- **Student** is a daily learner. Lives on the parent-web with a `student` role (see ADR 002).
- **Parent** is the daily-to-weekly transparency user.
- **School Admin** is the daily operations user; less time-critical than classroom users.
- **Ministry** is a periodic viewer — dashboards, charts, exports. No operational verbs (see ADR 013).

The `>>` between School Admin and Ministry indicates a step change in usage frequency — Ministry sees the rolled-up data, not the row-level workflow.

## Consequences

### Positive
- UX prioritisation decisions become deterministic. When two personas conflict, the higher-priority persona wins.
- Phase ordering in `task.md` reflects this — Phase 11 (Teacher) before Phase 12 (Parent/Student) before Phase 13 (Admin) before Phase 14 (Ministry).
- Demo and pilot narratives lead with the classroom, not the Ministry.

### Negative
- Some Ministry-facing wow-features (regional heatmaps, comparative dashboards) move later in the plan.
- Founder time on Ministry-narrative work is bounded.

### Neutral
- Ministry remains an important downstream user, just not a build-priority driver.

## Alternatives Considered

### A — Ministry-first
**Rejected.** Ministry doesn't use the product daily. Building for periodic viewers first leaves daily users under-served and the product hard to sell to schools (who pay for it). Earlier plan iterations were de-facto this; we explicitly back away.

### B — Equal-weight across personas
**Rejected.** Leads to feature chaos and no clear product opinion. With finite engineering time, equal weight means everyone gets a shallow experience.

### C — Student-first
**Rejected for now.** Students are critically important (see ADR 002) but device access in Zimbabwe rural schools is the binding constraint, not philosophy. Teacher is the most reliable daily user.

## References

- Plan: `/Users/phani.m/.claude/plans/do-an-entire-run-goofy-parasol.md` §1
- Backlog: `task.md` §1 DEC-001, §3 phase ordering
- Related ADRs: 002 (student-on-parent-app), 013 (ministry-viewer-only)
