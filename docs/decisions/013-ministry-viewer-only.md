# ADR 013 — Ministry as Viewer + Auditor Only

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: product, ministry, governance, scope

## Context

Earlier planning (and the unverified marketing claims in `VISION.md`) implied Ministry was a primary user. The founder corrected this:

> "Mostly charts and highlights will do for them."

The audit confirmed there is no Ministry-specific surface in the current build. The question is: what *should* Ministry have, and what should they explicitly *not* have?

## Decision

Ministry is **a viewer and auditor**, never an operator.

| Ministry **does** get | Ministry **does not** get |
|---|---|
| District / Province / National aggregate dashboards (charts) | Ability to mark attendance |
| Compliance dashboard (which schools have submitted what) | Ability to record payments |
| Drop-out heatmap (Zimbabwe geomap) | Ability to enrol or transfer a student |
| Subject pass-rate by region | Ability to send announcements |
| Resource allocation views (PTR, devices, electricity) | Ability to enter marks |
| Anonymised comparative school views | Direct access to any per-student PII without explicit authorisation |
| Policy impact tracking (before/after) | Operational verbs on any school's data |
| Donor / NGO impact reporting | Ability to modify school configuration |
| One-click UNESCO / UNICEF export templates | Ability to suspend a teacher account |

Implementation: a `ministry-web` PWA (or a Ministry role inside admin-web — final form decided as part of Phase 14 ADR follow-up). All routes are read-only; no `POST` / `PUT` / `DELETE` paths exposed to Ministry role.

## Consequences

### Positive
- Clear scope. Ministry-facing surface is small (~6 dashboard pages + export endpoints).
- Schools retain operational autonomy. Ministry doesn't accidentally (or intentionally) act on a school's data.
- Compliance / audit story is clean: Ministry can verify aggregate outcomes without per-student access by default.
- Aggregation API is the single integration point — Ministry consumers go through one well-defined channel.

### Negative
- Some Ministry stakeholders may push for operational verbs (e.g., "I want to enrol a transferred student myself"). We refuse and point them to the relevant school admin.
- Per-student access exists as an exception path for child welfare / safeguarding scenarios — gated, audit-logged, and time-bound.

### Neutral
- The Ministry role inside admin-web vs a separate ministry-web app is a Phase 14 UX decision. Both satisfy this ADR.

## Compliance & Privacy Notes

- Per ADR 007 (privacy-by-design), aggregate views default to anonymised. Identified views (by school name) are still aggregate-level (no per-student PII).
- Exception path for per-student access (child welfare / safeguarding): requires school admin co-sign, audit-log entry, and time-bounded grant.
- Data export at Ministry level honours ZDPA cross-border transfer rules — exports leave the platform only via documented endpoints.

## Implementation Notes

- Phase 14 builds the Ministry surface (M-001 through M-011 in `task.md`).
- Aggregation API: a read-only HTTP layer over the reporting projection DB (per ADR 006 — reporting is async consumer + projection). Lives inside `academics` service.
- Ministry role in `identity` service: explicit `read-only` flag; the gateway RBAC layer enforces.
- Charts per ADR 011: ECharts for ministry-web (heatmaps, geomap, sankey).

## Alternatives Considered

### Ministry as operator (full admin equivalent)
**Rejected.** Confuses school autonomy and creates political risk if Ministry takes operational action on a school's data.

### Ministry inside admin-web only (no ministry-web)
**Deferred.** Either form satisfies this ADR; final decision is part of Phase 14 work.

## References

- Plan: §3 Debate 12 (resolved)
- Backlog: `task.md` §1 DEC-013, Phase 14
- Related ADRs: 001 (audience pyramid), 006 (services consolidation), 011 (charts split), 007 (privacy)
