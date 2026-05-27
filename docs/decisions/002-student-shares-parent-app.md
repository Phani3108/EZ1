# ADR 002 — Student Shares the Parent App

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: product, identity, privacy, frontend

## Context

The audit noted that there was **no student app at all** in the current build, despite the audience pyramid (ADR 001) placing the student persona second only to teachers. Three options were debated:

- A — No student app, parent-mediated only
- B — Yes but secondary-only (age-gated)
- C — Universal, parent-controlled

The founder chose a fourth shape: **share the parent app**.

> "Student app is same as Parents app. No need of a different app. Teachers are not to prompt students to pay fees, they should only be able to see that."

## Decision

The parent-web (`apps/parent-web`) hosts **two distinct roles**:

- `parent`: full access to their child(ren)'s data, can pay fees, can message teacher, can submit complaints.
- `student`: read-mostly access to their own data — schedule, marks, attendance, announcements, assignments.

Single app, one codebase, role-based feature flags. No separate `student-web` app.

Behavioural rules derived from this decision (mirrored as `RULE-*` in `task.md` §2):

- **RULE-1** Parent-web hosts both roles; role-based show/hide.
- **RULE-2** Student is read-mostly: own profile, schedule, marks, announcements, assignments. No payments. No profile edits beyond self-managed metadata.
- **RULE-3** Teachers see fees read-only on the teacher's student view — no "remind" or "chase" verb. Awareness only.
- **RULE-4** Teacher announcements broadcast to all parents of all their classes by default — no audience picker. Admin can still target.
- **RULE-5** Non-teaching staff management is admin-only — not visible to teachers, students, or parents.
- **RULE-6** Parent feedback / complaint handling is admin-only. Parents file via P-007; admins handle via A-010.

## Consequences

### Positive
- Half the app surface to build, deploy, maintain.
- Family-account experience naturally falls out: parent and student see different views in the same shell.
- Single design system, single auth flow, single PWA install.
- Teacher's fees view stays useful (awareness) without becoming a chase tool.

### Negative
- Identity model gets a touch more complex (one app, two role-paths).
- Some UX trade-offs: a student logging in on a shared family device needs clear "you are signed in as <student name>" affordance.
- We must be careful about not leaking parent-level info to student-role sessions.

### Neutral
- The age-gating question (when does a child get their own login?) becomes a per-school policy, not a hard product line. Schools can configure minimum-age-for-own-login.

## Compliance & Privacy Notes

- Student data is sensitive under ZDPA + the Children's Act. Parental consent is required for under-16 student accounts.
- Audit log captures student-role logins separately so parental oversight is possible.
- Data export (Phase 8 / Phase 9) honours the role: a `student` exports only own data; a `parent` exports all linked children.

## Implementation Notes

- Identity service: extend the user model with `role` enum that includes `parent` and `student`. A child profile has a 1:1 link to a `student` user (when school enables it) and N:M link to `parent` users.
- Parent-web shell: `useRole()` hook drives all conditional renders.
- Teacher student-view: restore Fees tab but as read-only (RULE-3).
- Announcement create form (teacher side): simplify per RULE-4.
- Admin endpoints for HR (A-001) and complaints (A-010) gated to `admin` role.

## Alternatives Considered

### A — No student app, parent-mediated only
**Rejected.** Misses an entire persona. Doesn't future-proof for self-paced learning.

### B — Secondary-only (12+), separate app
**Rejected.** Two PWA codebases for parent and student is duplicative; ADR 001 audience pyramid already values teacher daily use over student-specific UX. Single app with role flags satisfies both.

### C — Universal, parent-controlled, separate app
**Rejected.** Same reasoning as B — duplicative.

## References

- Plan: §3 Debate 1 (resolved)
- Backlog: `task.md` §1 DEC-002, §2 RULE-1 through RULE-6, §7 student gaps, Phase 12 plan
- Related ADRs: 001 (audience pyramid), 007 (privacy-by-design)
