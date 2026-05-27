# ADR 004 — Integration-Only via Provider Interfaces

- **Status**: Accepted (revised 2026-05-26 from earlier "build native everything")
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: architecture, integrations, scope, ecosystem
- **Supersedes**: an earlier (informal) commitment to build native payments, native SMS, native content delivery

## Context

The build-vs-integrate question was debated three ways:

- A — Build everything natively. Full control, no vendor lock-in.
- B — Integrate at the edges, build the core. Focus on the unique Zimbabwe-education problem; lean on best-in-class for solved problems (SMS, payments, content).
- C — Federated ecosystem. Schools pick whichever vendor for whichever capability.

An initial founder reaction landed on "Build everything + expose APIs + MCP." On further reflection (and after the audit surfaced the scope cost), the founder revised:

> "DEC-004 will be integration only, we will just have placeholders for external tool integration, or do handover after the connection is established."

## Decision

EduZim does **not build native implementations** of:

- Payment processing
- SMS / push / WhatsApp / email delivery
- Content libraries (curriculum video, exam practice, etc.)
- Mapping / geocoding
- E-signature

Every such external touchpoint is encoded as an **abstract `Provider` interface** inside the relevant service, with:

1. **At least one reference implementation** wiring an existing vendor (Paynow, Africa's Talking, FCM, SendGrid, Khan Academy Lite, OpenStreetMap, DocuSign-equivalent).
2. **A manual-handover stub** (`ManualHandoverProvider`) for schools that handle the function off-platform; EduZim records the intent + reference so reporting stays accurate.
3. **Per-school provider selection** stored on `school.providers` JSON, configured in admin-web settings.

What EduZim *does* build natively:

- The domain itself: students, classes, attendance, marks, fees (records, not payment rails), announcements, lesson plans, quizzes, dropout intelligence, reporting.
- The Provider interfaces and reference implementations of them.
- A **Provider SDK** (Python + TypeScript) so third parties can implement custom Providers (regional banks, local SMS aggregators, custom content libraries).
- Public REST APIs and MCP servers (see ADR / Phase 16) — the integration substrate.

## Consequences

### Positive
- Drastic scope reduction. Phases 12b (payments), 12c (notifications), and parts of 15 (content) become Provider-interface design + wiring + reference impl — not full sub-products.
- Schools keep their existing ecosystem relationships (EcoCash, particular SMS aggregator, particular bank). We do not threaten anyone's existing economics.
- Smaller maintenance surface. Fewer regulatory exposures (we're not a payment institution; we're an integrator).
- Faster path to pilot.
- Phase 16 (Open APIs + MCP + Provider SDK) becomes the centrepiece of the integration story — the "real" platform-economy moment.

### Negative
- We lose direct visibility into transaction failure modes for non-native providers. Provider quality varies; school experience can vary too.
- Stickiness shifts: we're less stickier on the integration side (a school can swap providers). Our stickiness must come from the domain (ERP, intelligence, learning data).
- Custom-provider work for under-served regions is a community / partner contribution path, not built-in.

### Neutral
- Africa's Talking, FCM, SendGrid, Paynow keys already exist in `.env.example`. The audit found these were never wired. This decision says: wire them now, but only as one of multiple reference Providers — not as the platform's sole option.

## Compliance & Privacy Notes

- PII flowing through a Provider is governed by the Provider's privacy posture. We document each reference Provider's data handling in `docs/providers/<provider>/privacy.md` and require schools to acknowledge before selecting.
- For ZDPA cross-border data transfer, ManualHandoverProvider remains the data-sovereign default.
- A school selecting a Provider also explicitly consents (audit-logged) to that Provider's data handling.

## Implementation Notes

- Provider interfaces live in `services/<service>/providers/<capability>/base.py` (Python) and `packages/api-client/src/providers/` (TypeScript types).
- Reference implementations: `services/<service>/providers/<capability>/<vendor>.py`.
- Selection: `school.providers = { "payment": "paynow", "sms": "africastalking", "push": "fcm", "content": "manual_upload", ... }`.
- Phase 16 ships the Provider SDK + docs (`docs/providers/`) so partners can implement custom Providers without modifying EduZim core.

## Alternatives Considered

### A — Build everything natively
**Rejected.** Scope explosion. Threatens regional ecosystems. We become a payment + telecom + content company, none of which is our problem.

### B — Build core + integrate edges + own no native of edges
**This is what we chose** (with the strict no-native-build addition).

### C — Federated marketplace, schools pick from a registry
**Rejected.** Adds discovery + reputation + curation surface. The Provider interface gives us the integration freedom without the marketplace overhead. We can move toward a registry later if there's pull.

### Earlier framing — "Build everything + expose APIs"
**Superseded.** It was internally inconsistent: we'd build natively *and* permit replacement, doubling the surface. The revised position is cleaner.

## References

- Plan: §3 Debate 2 (revised)
- Backlog: `task.md` §1 DEC-004, §2 RULE-7/8/9, Phase 12b, Phase 12c, Phase 15, Phase 16
- Related ADRs: 003 (thin learning layer), 011 (charts split), all phase 16 work
