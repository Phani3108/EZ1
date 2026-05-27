# ADR 005 — Data Residency: AWS Cape Town v1 → Zimbabwean Provider Year 2

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: infrastructure, compliance, legal, sovereignty

## Context

Zimbabwe's Data Protection Act (2021) and the Cybersecurity and Data Protection Act regulate the storage and cross-border transfer of personal data — especially data concerning children. A Ministry-aligned national education platform will be scrutinised for data residency. Five options were debated:

- A — AWS Cape Town (af-south-1)
- B — AWS Mumbai or Frankfurt
- C — On-premises at Ministry data centre
- D — Hybrid (compute in cloud, data in Zimbabwe)
- E — A Zimbabwean cloud provider (Liquid Intelligent Technologies / Dandemutande / similar)

## Decision

- **v1 deploys in AWS Cape Town (af-south-1)** — closest mature region, lowest latency to Zimbabwe, full managed services available.
- **Year 2 migration target: a Zimbabwean cloud provider** (Liquid Intelligent Technologies or Dandemutande, finalised after operational review).
- **Lawyer engagement before any pilot**: a Zimbabwean legal counsel reviews data flow against ZDPA, the Children's Act, the Cybersecurity and Data Protection Act, and any Ministry-specific data-handling requirements. The lawyer signs off before a single school onboards in production.
- All school contracts include a clause documenting the v1 hosting region and the Year 2 migration commitment.

## Consequences

### Positive
- v1 ships on a known-stable managed cloud — Postgres Multi-AZ, MSK, ElastiCache, EKS — without standing up infrastructure ourselves.
- Latency to Zimbabwe is acceptable (~50ms vs ~150ms to Mumbai/Frankfurt).
- Legal review pre-pilot caps regulatory risk.
- A documented sovereignty story exists; Ministry can be told "data is in Africa today, in Zimbabwe by Year 2."

### Negative
- South African jurisdiction touches the data initially. Some Ministry stakeholders may push back even with the migration commitment.
- Year 2 migration is real engineering work — Postgres replication across providers, DNS cutover, blue/green migration of running schools.
- Smaller Zimbabwean providers have weaker managed-service tiers; we may end up running more services ourselves post-migration.

### Neutral
- Decision can be revisited if a Ministry contract explicitly requires day-1 in-country hosting; the architecture (compose / Terraform per Phase 17) is provider-agnostic.

## Compliance & Privacy Notes

- ZDPA cross-border transfer requires either adequacy decision or specific safeguards. AWS Cape Town does **not** automatically satisfy "in Zimbabwe" — the lawyer review will surface whether contractual safeguards are sufficient for v1.
- Per ADR 002, student/minor data is sensitive. Cross-border for minors needs explicit parental consent in pilot deployments; we add the consent capture to onboarding (Phase 8).
- The Year 2 migration is treated as a feature, not a stretch goal. Implemented as part of platform engineering work in Phase 17.

## Implementation Notes

- Terraform (Phase 17) is written provider-neutral where possible; AWS-specific modules isolated.
- Database: choose Postgres replication topology that supports inter-provider streaming (logical replication) so cutover is online.
- Object storage: S3-compatible. Use a wrapper that works against AWS S3 today and a ZW provider's S3-compatible bucket later.
- DNS: low-TTL records on the apex; cutover is one record change.
- Backups: cross-provider from day 1 (backup in ZW provider even while compute is in AWS).

## Alternatives Considered

### B — Mumbai / Frankfurt
**Rejected.** Higher latency; same cross-border-data concern; no political benefit.

### C — On-prem at Ministry data centre
**Rejected for v1.** Operational ownership of physical infrastructure is not a path we want to start on. May revisit for very-high-sovereignty Ministry deployments via Phase 18 (open core release) — Ministry can self-host the open source.

### D — Hybrid (compute cloud, data ZW)
**Rejected.** Every query crosses a network boundary; latency unacceptable.

### E — Zimbabwean provider day 1
**Rejected for v1.** Managed services not yet mature enough; ops cost too high. **Adopted as Year 2 target.**

## References

- Plan: §3 Debate 5 (resolved)
- Backlog: `task.md` §1 DEC-005, Phase 5 (infra), Phase 17 (deploy), Phase 9 (compliance)
- Related ADRs: 007 (privacy-by-design), 009 (tenancy tiers — supports per-school residency at premium tier)
