# ADR 012 — Open Core Release Post-v1

- **Status**: Accepted (deferred to post-v1)
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: licensing, strategy, governance

## Context

EduZim is positioned as critical national infrastructure for education. Trust, auditability, and adoptability by peer governments / NGOs matter at least as much as commercial defensibility. Three options:

- A — Closed source. Control + IP defensibility.
- B — Open core. Core platform open; commercial / managed layer closed.
- C — Fully open source. Monetise on services and managed offerings.

## Decision

**Open core, executed post-v1**, timed with the first signed Ministry pilot.

| Component | License | Hosted Where |
|---|---|---|
| ERP services (identity, academics, finance, communications) | AGPL-3.0 | Public `github.com/eduzim-platform` |
| API Gateway | AGPL-3.0 | Public |
| `@eduzim/ui`, `@eduzim/api-client`, `@eduzim/auth`, `@eduzim/offline-core` packages | AGPL-3.0 | Public |
| Reporting consumer (basic) | AGPL-3.0 | Public |
| Provider SDK (Python + TypeScript) | Apache 2.0 | Public, permissive for integrators |
| AI / advanced analytics modules (Phase 5 in the original 6-pillar vision) | Commercial | Private |
| Managed cloud (hosting, ops, support) | Commercial offering | Private |
| Premium content modules (when/if we add them) | Commercial | Private |

## Consequences

### Positive
- Ministry can audit our code. Builds institutional trust.
- Peer governments / NGOs can fork and adapt. Aligns with the mission.
- Community contributions become possible — particularly for Provider implementations (per ADR 004), translations, accessibility fixes.
- AGPL ensures that downstream commercial users contribute back if they host the core.

### Negative
- AGPL scares some commercial integrators. We mitigate via the permissive Apache-2.0 Provider SDK so building Providers doesn't trigger AGPL obligations.
- Forking risk — someone could host a competing instance. We accept this; our edge is operations + AI + ecosystem.
- Maintaining a public repo carries its own work (issue triage, contributor management, security disclosure).

### Neutral
- Timing matters: open source pre-v1 means we ship rough code publicly. Post-v1 (after Phase 17 CI/CD + Phase 19 docs) is the right moment.

## Implementation Notes (deferred to Phase 18)

- Decide between repo-per-service vs monorepo for the public release. Likely monorepo to match the internal structure.
- Add `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, license files per module.
- Security disclosure policy: `security@eduzim.co.zw` mailbox + 90-day disclosure window.
- Migrate or mirror commits from the private repo to public. Decide whether to rewrite history to start with a clean v1 commit.
- Public CI must pass on the public repo — separate workflow from private internal CI.
- Time the public launch with a Ministry-pilot announcement for narrative impact.

## Alternatives Considered

### A — Closed source
**Rejected.** Trust deficit with Ministry. Slower adoption. Misaligned with the platform's national-infrastructure positioning.

### C — Fully open source
**Rejected.** Hard to monetise at the scale we need to fund development. Open core lets the commercial layer fund the open core.

## References

- Plan: §3 Debate 10 (resolved)
- Backlog: `task.md` §1 DEC-012, Phase 18
- Related ADRs: 004 (Provider SDK is the Apache 2.0 boundary)
