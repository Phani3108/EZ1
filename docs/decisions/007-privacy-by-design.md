# ADR 007 — Privacy-by-Design as a Gating Discipline

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: privacy, compliance, process

## Context

The audit found that EduZim collects substantial PII about minors — names, DOBs, attendance patterns, marks, photos (when added), behavioural incidents — without a documented privacy impact assessment, retention policy, or data-export pathway. The Zimbabwe Data Protection Act (2021), the Children's Act, and international norms (COPPA-equivalent, GDPR-influenced) treat this data as sensitive.

The question was: do we adopt minimal-data + privacy-by-design now, or collect aggressively and rely on encryption?

## Decision

**Privacy-by-design is a hard gate on every new feature.** Practically:

1. **Minimal-data principle.** No new field collected without justifying its specific purpose, retention window, and access scope.
2. **Privacy Impact Assessment (PIA)** at `docs/compliance/pia-v1.md` listing every PII field, its purpose, its retention, and its access scope. Updated as the data model evolves.
3. **Public Privacy Policy + Retention Policy** at `/privacy` and `/retention` on all web apps.
4. **Named Data Protection Officer (DPO)** in the footer of every app and on the privacy page.
5. **Data export endpoint** per parent (own children) and per school (per ADR 009 tenancy tiers, full export at any tier).
6. **Right-to-delete** with consent-aware tombstone behaviour: writeable data deletes; legally required academic records retain with anonymised identifiers.
7. **Audit log** of every PII write/read with a `who/when/what/where` row (Phase 9 PH9 tasks).
8. **Privacy review** is a required step on every PR introducing a new field on a PII-classified table; PR template enforces it.

## Consequences

### Positive
- Pilot-deployable in the ZDPA framework. Lawyer review (ADR 005) has something concrete to audit.
- Builds parental and Ministry trust. Reduces reputational risk if any incident occurs.
- Forces feature owners to *justify* data collection — usually leading to better, narrower features.

### Negative
- Each new feature has additional review overhead (~30 min PIA update per typical feature; ~half-day for heavy ones like A-007 health records).
- Some features may slow or be scoped down (e.g., health-record visibility limited to nurse-equivalent role rather than all admins).

### Neutral
- Compliance posture is rare in African EdTech and may become a competitive differentiator — but we don't market it as such; we just do it.

## Compliance & Privacy Notes

- ZDPA: data subject rights (access, correction, deletion, portability) all map to endpoints we either have or will build in Phase 8 / 9.
- Children's Act: parental consent capture required for under-16 student accounts (ADR 002 student role).
- Cybersecurity and Data Protection Act: incident notification obligations imply we need observability (Phase 6) + an incident response runbook (Phase 17).
- Records of decisions: PIA, retention policy, DPO appointment all stored in `docs/compliance/`.

## Implementation Notes

- **Minimum-data audit** during Phase 9 PH9-2: review every PII field; remove (or anonymise) what isn't strictly needed for a downstream consumer. Example to evaluate: student DOB — if only age band is consumed by analytics, store age band; keep DOB only where strict accuracy is required (e.g., transcripts, age-gated features).
- PR template (`.github/pull_request_template.md`) adds: "Does this PR introduce or modify PII fields? If yes, has the PIA been updated and the privacy reviewer signed off?"
- Audit-log writes are non-blocking (async); but every PII write goes through a thin wrapper that captures the actor, target, fields touched, and timestamp.

## Alternatives Considered

### B — Collect aggressively + encrypt heavily
**Rejected.** Encryption does not satisfy minimisation. A breach where encryption is defeated still exposes everything we hold.

### C — Per-school consent profiles
**Rejected as primary mechanism.** Too configurable, hard to audit, hard to support. The right model is: minimal-data globally, per-feature opt-in for non-essentials.

## References

- Plan: §3 Debate 6 (resolved)
- Backlog: `task.md` §1 DEC-007, RULE-10, Phase 9 (privacy/audit/compliance)
- Related ADRs: 002 (student data), 005 (data residency), 009 (tenancy tiers)
- Compliance docs: `docs/compliance/pia-v1.md` (Phase 9), `/privacy` and `/retention` pages
