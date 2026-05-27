# EduZim Privacy Policy (Draft v0.1 — Q-009)

> **Status**: Draft. Pre-pilot legal review required (see ADR 005 — Zimbabwean lawyer engagement on ZDPA + the Children's Act). This document is the working source and goes through legal review before being linked from the footer in production.
> **Last updated**: 2026-05-26
> **DPO contact**: dpo@eduzim.co.zw

---

## Who we are

EduZim is a school management platform operated by the EduZim project. We
process personal data on behalf of schools (the "data controllers") who use
EduZim to run their academics, attendance, fees, and communications.

## What data we process

### About students
- Identity: name, date of birth, gender, admission number, photograph (when school enables it)
- Family: linked parents / guardians, relationship
- Academic: enrollments, attendance, marks, assignments, lesson plans
- Behavioural: discipline incidents (when school enables it)
- Health: allergies, emergency contacts, vaccinations (when school enables it — PIA-gated)

### About parents
- Identity: name, email, phone
- Linked children (one or more)
- Communications: announcements received, messages sent/received (when threads enabled)
- Financial: invoices, payments

### About teachers and staff
- Identity: name, email, phone, role
- Employment: class assignments, subject assignments
- Activity: login history, actions performed (audit log)

### About administrators
- Identity: name, email, phone, role, school
- Activity: configuration changes, audit-log entries

### What we deliberately do NOT collect
- Biometric data is **not** collected by default. If a school opts into
  biometric attendance, the biometric template stays on-device; we store
  only the resulting "present/absent" state.
- Location data of students is not collected (transportation tracking is
  opt-in per school; the bus is tracked, not the student).
- We do not sell, rent, or share personal data with third parties for
  marketing.

## Why we process it (lawful basis)

Per ZDPA and the Children's Act:

1. **Performance of contract** (between the school and the parent):
   academic record-keeping, attendance, fee invoicing, communications.
2. **Legal obligation** (for the school): retention of academic records,
   compliance reporting to the Ministry of Primary and Secondary Education.
3. **Legitimate interest** (the school's): operational efficiency, dropout
   risk identification, safeguarding.
4. **Consent** (specifically for minors): parental consent for any optional
   feature (e.g., health records, photographs, performance comparison).

## Children's data (Children's Act + COPPA-equivalent)

- Student data is sensitive by definition (data subject is a minor).
- Parental consent is captured at enrollment for the core data set.
- Optional features (photographs, health, performance comparison, public
  reports) require explicit, separate consent.
- A student over 16 may exercise data subject rights directly; under 16,
  rights are exercised by the parent.

## Your rights

Under ZDPA + GDPR-aligned norms you may:

- **Access**: see what we hold about you / your child.
- **Correct**: fix mistakes.
- **Delete**: request deletion (subject to legal retention — see retention
  policy).
- **Portability**: receive your data in a machine-readable format.
- **Object**: opt out of any non-essential processing.
- **Restrict**: pause processing while a complaint is resolved.

To exercise any of these: contact the DPO at `dpo@eduzim.co.zw`. We
respond within 30 days.

## Where data lives

Per ADR 005 (data residency):

- **v1**: AWS Africa (Cape Town, af-south-1)
- **Year 2 target**: a Zimbabwean cloud provider (Liquid Intelligent or
  Dandemutande)
- Backups are encrypted and stored within the same region.

Cross-border transfer of children's data has been reviewed against ZDPA
and the Children's Act; v1 hosting in Cape Town relies on contractual
safeguards rather than an adequacy decision.

## Security

- TLS in transit (HTTPS at the gateway).
- Multi-tenant data isolation: every row carries `school_id`; cross-school
  access is enforced at the gateway and verified by automated tests.
- Strong secrets (JWT, internal-service tokens) generated per-environment
  via `scripts/bootstrap-secrets.sh`; rotated per `docs/runbooks/secrets-rotation.md`.
- Daily Postgres backups; 14-snapshot retention (see backup-restore runbook).
- Audit log of PII writes (Phase 9 work item — `audit_log` table in
  identity service).

## Sharing

We share personal data only with:

- The school the data belongs to (always).
- Service-providers configured per-school (e.g., Paynow for payments,
  Africa's Talking for SMS). See ADR 004 — provider selection is opt-in
  per school per integration point.
- Authorities, when required by law.

## Retention

See the separate **Data Retention Policy** at `docs/compliance/retention-policy.md`.

## Changes to this policy

We post material changes here and via in-app notification. The DPO
contact is the authoritative channel for questions.

## Open items (documented per ADR 007 / Phase 9)

- Final legal review (ADR 005 lawyer engagement) — **required before any pilot**.
- Cookie banner (currently we use httpOnly refresh cookie only — no third-party trackers — so a strict cookie banner is arguably unnecessary; legal review confirms).
- PIA formalisation in `docs/compliance/pia-v1.md` (this file).
- Data export endpoint (Phase 9 PH9-3) wiring.
- Right-to-delete endpoint (Phase 9 PH9-4) wiring.
