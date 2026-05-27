# ADR 009 — Tenancy Tiers (Shared / Dedicated / District)

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: architecture, multi-tenancy, compliance, scale

## Context

The current build uses single shared multi-tenant databases with `school_id` on every row. The audit flagged that:

- A bad query from one school can slow all schools.
- Per-school data export is hard.
- Per-school data residency is impossible.
- One DB per school × 5,000 schools is operationally unviable.

Three options:

- A — Stay shared multi-tenant
- B — Tenancy tiers (shared default, dedicated premium, district shared)
- C — One DB per school

## Decision

Tenancy is **tiered**, configured per school via `school.tenancy_tier`:

| Tier | Storage | Use Case |
|---|---|---|
| `shared` (default) | Shared DB cluster, `school_id` row-level | Small/medium schools, low data volume, no sovereignty requirements |
| `dedicated` | Per-school dedicated DB | Large private schools, schools that pay for isolation, schools with strict data requirements |
| `district` | Shared DB scoped to district | Ministry-onboarded district rollouts, where a district owns the data umbrella |

A query routing layer in `services/shared/db.py` resolves a school's connection at request time. Promoting `shared → dedicated` is a background migration job (Phase 8 PH8-3).

## Consequences

### Positive
- Most schools start cheap (shared); large or sensitive schools pay for or are allocated isolation.
- Per-school data export is easier on dedicated (whole DB dump) and well-defined on shared.
- Supports the Year 2 data-residency migration (ADR 005) at a per-school granularity — a school can be moved to a ZW-hosted dedicated DB without dragging others along.
- District tier supports Ministry-driven rollouts cleanly.

### Negative
- Three modes to maintain in code paths that touch DB resolution.
- Promotion (shared → dedicated) is real engineering: data extraction + new DB provisioning + cutover + verification.
- Query layer cost: every request resolves which DB to hit; cache aggressively.

### Neutral
- The decision can be revisited per service: if `finance` data has stricter residency than `academics`, the tier can be per-service-per-school in a later iteration. For v1, tier is per-school across all services.

## Compliance & Privacy Notes

- Promotion to `dedicated` is part of the data subject rights flow if a school demands isolation (ZDPA Section 12 / similar).
- Data export endpoint (Phase 8 PH8-4) works uniformly across tiers: caller doesn't know which tier the school is on.
- Right-to-delete (ADR 007 / Phase 9) flows through the tier-resolved DB.

## Implementation Notes

- `school.tenancy_tier` column added in Phase 8 PH8-1.
- Query router: `services/shared/db.py` exposes `get_engine_for(school_id, service_name)`; defaults to shared, switches to dedicated when configured.
- Migration job for `shared → dedicated`:
  1. Provision new DB (Terraform-driven).
  2. Lock the school in a maintenance mode (writes paused).
  3. Snapshot the school's rows from shared.
  4. Restore into dedicated.
  5. Flip `tenancy_tier`.
  6. Verify row counts and a sample checksum.
  7. Soft-delete from shared (kept 30 days for rollback).
- Documented in `docs/runbooks/tenancy-upgrade.md` (Phase 8 PH8-4 deliverable).

## Alternatives Considered

### A — Always shared
**Rejected.** Ceiling on compliance and noisy-neighbour management.

### C — Always one DB per school
**Rejected.** 5,000 DBs is infeasible without serious tooling we don't yet have. May revisit in Year 3+ if we build the tooling.

## References

- Plan: §3 Debate 7 (resolved)
- Backlog: `task.md` §1 DEC-009, Phase 8
- Related ADRs: 005 (data residency), 007 (privacy-by-design)
