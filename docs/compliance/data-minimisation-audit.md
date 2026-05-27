# Data minimisation audit (PH9-2)

**Status**: Open. **PH9-2 is documented but DEFERRED-MAJOR**. The
checklist below is the structured review every field needs; executing
that review across all models is a multi-week sweep that depends on
product input (which fields are still being relied on by which UI
flow) and legal input (ZDPA / COPPA equivalents on each specific
field).

This document is the **forcing function**: it lists every PII-bearing
field today, marks the proposed disposition, and identifies who needs
to sign off before the change lands. Phase 9 closure does NOT depend
on completing the table below — only on having the structured plan +
the substrate (audit log, export endpoints, retention policy) in
place.

## Scope

ADR 007's "minimum-data" principle: don't collect what we don't
strictly need. The Phase-1 audit gave us a starting inventory; this
document is the live working version. As fields change, this doc is
the canonical record of WHY a field exists.

For each field below:

- **Today**: do we collect it?
- **Why**: what user-facing flow depends on it?
- **Proposed**: keep / drop / generalise / move-to-opt-in.
- **Owner**: who signs off (product / legal / engineering).
- **Status**: open / scheduled / closed.

## Students (`students` table)

| Field | Today | Why we collect | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `student_code` | yes | School-side identifier (school's existing roll). | Keep. | Eng | closed |
| `first_name` | yes | Required for the report card; needed for parent recognition; required by Ministry roll-up. | Keep. | — | closed |
| `last_name` | yes | Same. | Keep. | — | closed |
| `dob` | yes | Used to compute grade-band eligibility; required for some statutory reports. | **Generalise to year-month?** Day-of-birth used only in birthday-celebrate features we don't have yet. | Product + Legal | open |
| `gender` | yes | Required by Ministry statistics (gender-parity reports). | Keep. | — | closed |
| `admission_date` | yes | Required for transfer/leaving-certificate generation. | Keep. | — | closed |
| `status` | yes | Active vs withdrawn lifecycle. | Keep. | — | closed |
| `medical_notes` | NOT collected | (Field doesn't exist.) | Do NOT add unless a specific use case requires it; if added, default opt-in only. | Product + Legal | open (preemptive) |
| `photo` | NOT collected | (Not in schema.) | Same as medical_notes. | Product | open (preemptive) |

## Parents (`parents` table)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `first_name` | yes | Used in parent UI ("Hi, Jane"). Required for receipts. | Keep. | — | closed |
| `last_name` | yes | Same. | Keep. | — | closed |
| `phone` | yes | Required for SMS notifications (DEC-004 integration path). | Keep. Mask everywhere except in admin UI + the parent's own /parents/me view. | Product + Eng | scheduled |
| `email` | yes | Required for password reset + invoice receipts. | Keep. Apply same masking as phone. | Product + Eng | scheduled |
| `relationship_type` | yes | Used to disambiguate two-parent households. | Keep. | — | closed |
| `national_id` | NOT collected | — | Do NOT add. Schools may want to add it for receipts; resist unless legally required. | Legal | open (preemptive) |
| `address` | NOT collected (on parent) | — | Same. | — | open (preemptive) |

## Attendance (`attendance_records`)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `student_id`, `class_id`, `date`, `status` | yes | Core attendance record. | Keep. | — | closed |
| `marked_by_user_id` | yes | Audit trail (which teacher marked). | Keep — already used by the audit log. | — | closed |
| `device_id` | yes | Offline-sync deduplication. | Keep. Document that this is a device-fingerprint (not user-tracking). | Product | scheduled |
| `client_event_id` | yes | Idempotency key. | Keep. | — | closed |
| `notes` | NOT collected | (Field doesn't exist.) | Do NOT add. Free-text on attendance becomes a privacy hole fast (teachers writing "looked tired" / "smelled of alcohol"). If added, restrict to a fixed picklist. | Product + Legal | open (preemptive) |

## Marks (`marks`)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `assessment_id`, `student_id`, `marks`, `is_absent` | yes | Core grade record. | Keep. | — | closed |
| `remarks` | yes | Teacher comments. | **Audit**: is this used? If yes, keep with a content-policy banner ("don't write PII"). If not used, drop. | Product | open |
| `graded_by` | yes | Audit trail. | Keep — used by audit log. | — | closed |

## Identity / Users (`users` in identity service)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `email` | yes | Login + password reset. | Keep. | — | closed |
| `password_hash` | yes | Auth. | Keep. Verify Argon2/bcrypt strength annually. | Eng | scheduled-annual |
| `first_name`, `last_name` | yes | UI greeting. | Keep. | — | closed |
| `role` (single) | yes | RBAC. | Keep. | — | closed |
| `phone` | NOT in identity (only on parent) | — | Don't add. | — | closed |
| `last_login_at` | (verify) | Audit trail. | Keep if present; if not present, audit_log covers it. | Eng | scheduled |
| `failed_login_count` | (verify) | Lockout. | Keep if present; rate-limit covers most of it. | Eng | scheduled |

## Communications (announcements, messages)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `body` (free-text) | yes | Required for announcements. | Keep; content-moderation hooks deferred to Phase 11+. | Product | scheduled |
| `audience_class_id` | yes | Targeting. | Keep. | — | closed |

## Audit log (`audit_log`)

| Field | Today | Why | Proposed | Owner | Status |
|---|---|---|---|---|---|
| `ip_address` | yes (45-char) | Security forensics. | **Restrict to security events only** (login, role change, payment). Don't include on routine writes (student.created, etc.) — already enforced at call sites. | Eng | scheduled |
| `user_agent` | yes (255-char) | Same. | Same. | Eng | scheduled |
| `target`, `details` (JSON) | yes | Audit signal. | **Rule**: never include the full row. Capture IDs + which fields changed, not values. Enforced at call sites; review during PR. | Eng | scheduled-ongoing |

## How to mark a field "closed"

A row moves to `closed` when:

1. Product / Legal / Eng (whichever owner is listed) has explicitly
   signed off on the disposition.
2. Any required code changes have landed.
3. The PIA (`docs/compliance/pia-v1.md`) is updated to reflect the
   field's current state.

## When this audit gets re-run

* On every new model migration that adds a column. The PR author lists
  the new column here BEFORE merge; reviewers block until present.
* Annually, even without a migration — to catch drift in justification
  (a field that made sense for an unbuilt feature in v1 may no longer
  justify storage in v3).
* Post-incident — any privacy-relevant incident triggers a fresh
  sweep of the most-relevant table.

## Why this is DEFERRED-MAJOR

Each "open" row above represents real product + legal coordination,
not engineering work. Closing them requires:

1. Product saying "yes, we need / no, we don't need this field for the
   roadmap." Some answers depend on features that aren't yet specified
   (gender beyond binary, foster/guardian relationships, etc.).
2. Legal saying "ZDPA + Children's Act + (your destination markets')
   regulations allow this." We don't have lawyer time committed.
3. Engineering migration work + UI changes for any "generalise" or
   "drop" disposition.

The scaffolding (this document + the audit log + retention CLI) lets
that work happen incrementally without blocking the rest of the
platform. **Phase 9 closure does NOT depend on every row above
moving to `closed` — only on the structured plan being recorded.**
