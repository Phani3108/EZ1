# ADR 021 — Onboarding flow + Provisioner role (Phase 15)

**Status**: Accepted 2026-05-27
**Closes**: Phase 15 / I-001..I-007, drafts (D-001..D-006), onboarding readiness (O-001..O-002), Go Live gate (O-003)
**Amends**: ADR 020 (Ministry inside admin-web; default role read-only)
**Pairs with**: ADR 018 (audit invariants)

## Context

The platform has 14 phases of features but no "first time" experience: a school can't get from "we just signed up" to "parents are logging in" without manual database surgery. Specifically:

* `POST /schools` was open to any authenticated user — there was no provisioning gate.
* The `User` model required `password_hash NOT NULL`, so admins had no way to pre-stage accounts that the recipient would later activate.
* No bulk teacher import; the only bulk path was for students.
* No "send invite" pipeline; only the password-reset flow used a token.
* No readiness checklist or Go Live concept.

Phase 15 adds:

1. A token-based **Invitation** system in identity (`POST /invitations` + token preview/accept/by-code/resend).
2. A **draft-and-approve** queue in academics for teacher-submitted student/parent records.
3. **Bulk teacher import** in academics + **bulk fee-structure import** in finance.
4. An **InviteDispatcher** + `InviteOutbox` in communications that picks a channel from the per-school `SchoolNotificationConfig` (Phase 12c) and falls back to a 6-digit manual code.
5. An **onboarding readiness API** + a **`School.is_live` gate** that flips once every check is green.
6. A new **`Provisioner`** role (additive to `Ministry`) and an **`EduZimOps`** super-role, both holding `school:create + invite:write`. Lets Ministry users + EduZim staff onboard new schools without contradicting ADR 020's "Ministry default role is read-only."
7. A `(admin)/setup/**` wizard in admin-web and `invite/[token]` landing pages in parent-web + teacher-web.

## Decisions

### 1. School creation gate

`POST /api/v1/schools` is now gated on `school:create`. Default-grants:

* **`Provisioner`** — additive to `Ministry`. A user must hold BOTH roles to provision; "Ministry+Provisioner" is the standard label. The user's regular Ministry-role default surfaces stay read-only.
* **`EduZimOps`** — internal EduZim Operations role. Holds `school:create + invite:write + ministry:read` (cross-tenant read view). Reserved for the EduZim platform team.

Both choices are seeded by `scripts/seed-baseline.sh`. The user explicitly chose "both" in the Phase 15 decision interview.

### 2. Invitation model + token

* New `invitations` table in identity_db. Columns: `(school_id, token_hash, manual_code, role, user_id, target_resource_id, target_resource_type, contact_email, contact_phone, channel_attempted, channel_sent_at, expires_at, accepted_at, attempts, last_error, created_by_user_id)`.
* Token is `secrets.token_urlsafe(48)`, hashed with sha256 — same crypto as `PasswordResetToken`. Raw token returned only on create + resend.
* Manual code is 6 digits (`secrets.choice(string.digits)` × 6). Returned every time. Admin reads it out over the phone when SMS / WhatsApp / Email aren't available.
* `User.password_hash` is now nullable. Login fail-closes when password_hash is null. The `auth.login.failed` event still records `invalid_credentials` — does NOT reveal that the user is in invited-but-not-activated state (no email enumeration).
* Idempotency: `POST /invitations` returns the existing row + a freshly-rotated token if `(school_id, role, contact_email||contact_phone)` already has a pending invite. Rotating the token on every idempotent re-call means a leaked old token cannot outlive the caller's intent.

### 3. Teacher drafts + admin approval

Teachers hold the new `student:draft` permission. They submit `StudentDraft` rows via `POST /api/v1/drafts/students`. Admins (with `school:manage`) approve via `POST /api/v1/drafts/students/{id}/approve` — this creates the real `Student` + optional `Enrollment` rows, and if parent contact info was captured, auto-spawns a `ParentDraft` (which the admin reviews next).

Rejection reasons are the only place in the platform where ADR-018 audit details legitimately include admin-supplied free text. The `rejection_reason` field is capped at 200 chars.

### 4. Bulk imports

* **Teachers** (`POST /api/v1/bulk/teachers` in academics) — CSV multipart, 1000-row cap, dry-run, idempotency by `(school_id, email)`. Persists `InviteRequest` queue rows in academics; admin-web's dispatcher posts each row to identity's `POST /invitations` then calls back to academics's `POST /bulk/invite-requests/{id}/mark-dispatched`.
* **Fee structures** (`POST /api/v1/bulk/fee-structures` in finance) — CSV groups rows by `structure_name`. Idempotent on `(school_id, academic_year_id, structure_name)` — re-running replaces the item list.
* **Students** — the existing `POST /api/v1/students/import` was extended to also queue an `InviteRequest` for the parent when a `parent_phone` or `parent_email` column is present.

### 5. InviteDispatcher

`services/communications/app/services/invite_dispatcher.py` is stateless. Given an invitation, it picks the first matching configured channel from `SchoolNotificationConfig` in this order:

```
sms → whatsapp → email → manual
```

`sms` requires a non-empty contact_phone; `whatsapp` same; `email` requires contact_email. `manual` always matches. Manual mode writes the outbox row with status `manual_pending` + the 6-digit code visible — the admin reads it out over the phone.

Templates live in `services/communications/app/templates/invite.py` — one (role × channel) pair each. SMS is capped to 160 chars; WhatsApp to 1000. The admin can re-read the rendered body at any time via `GET /comm/invite-outbox`.

### 6. Readiness checklist + Go Live

`GET /api/v1/onboarding/status` returns 7 academics-side checks (school_profile, classes, subjects, teachers, students, parents_invited, first_attendance). Each is `green | amber | red` with evidence. Fee-structure and first-announcement checks live in finance + communications respectively and are overlaid client-side by admin-web — that keeps the readiness API single-service and easy to test.

`POST /api/v1/onboarding/go-live` asserts every step is green, then sets `School.is_live = true` and audit-logs `school.went_live` with `details = {"checklist_snapshot_hash": <sha256[:16]>}` so the moment can be re-derived later.

## Audit invariants (per ADR 018, reaffirmed)

| Event | Target | Details |
|---|---|---|
| `user.invited` | `{resource, id, role, school_id}` | `{channel_attempted}`. No email, no phone, no name. |
| `user.activated` | `{resource, id}` | `{role}`. No email, no password. |
| `student.draft.submitted` | `{resource, id, school_id}` | `{class_id, has_parent_contact}`. No names. |
| `student.draft.approved` | `{resource, id, school_id, student_id}` | `{approved_by}`. No names. |
| `student.draft.rejected` | `{resource, id, school_id}` | `{approved_by, rejection_reason}`. The free text reason IS logged (admin-supplied, 200-char cap). |
| `invitation.dispatched` | `{resource, id, school_id, channel}` | `{provider_name, status}`. No email, phone, body. |
| `school.went_live` | `{resource, id}` | `{checklist_snapshot_hash}`. No counts. |

Test coverage in each domain enforces these via string-membership grep against the test seed's PII tokens.

## Architecture trade-off — InviteRequest queue in academics

We deliberately did NOT make the bulk endpoints call identity over HTTP synchronously. Instead, bulk imports write `InviteRequest` rows in academics; admin-web reads them and orchestrates the cross-service calls (`POST /invitations` to identity, then `POST /comm/invitations/dispatch` to communications).

Pros:
* Bulk endpoint is single-service and single-transaction.
* Tests are tenant-isolated and fast (no cross-service mocking).
* Retry semantics are explicit (each row has `request_status + last_error`).

Cons:
* Admin-web has to know about the orchestration sequence.
* A worker-style automation isn't wired yet — admin-web makes the calls inline.

The worker is a follow-up. For v1 the inline admin-web orchestration is enough.

## Cross-school sentinel constraint (continued from ADR 020)

Audit rows for cross-school events (Ministry, EduZimOps onboarding actions) use the sentinel UUID `eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee` — same value introduced in ADR 020. Phase-15-specific Ministry write events that span tenants (e.g., `school.created` triggered by `EduZimOps`) use the sentinel as `school_id`; downstream audit dashboards filter it out.

## Consequences

### Positive
* A new school can be onboarded entirely through the admin-web wizard.
* The "is the school ready to go live?" question is auto-evaluated with deterministic per-step evidence.
* Parents and teachers receive an invitation message they can act on without IT support.
* The manual-code fallback means EduZim works in Zimbabwe even when SMS / WhatsApp / Email aren't configured.

### Negative
* `Provisioner` is a new role with a write capability. It's narrow — only `school:create + invite:write` — but it's still a deviation from ADR 020's "Ministry default role is strictly read-only." We mitigate by:
  1. Naming the role explicitly so audit logs make the carve-out visible.
  2. Making it additive — a user must hold BOTH `Ministry` + `Provisioner` to wield it.
  3. Audit-logging every school create + invite dispatch with the actor's roles.
* Cross-service orchestration moves to admin-web. A failed dispatch needs admin intervention. A retry worker is in the follow-up backlog.

## What this ADR does NOT decide

* Excel server-side parsing — Phase 15 accepts CSV only; admin-web's SheetJS can convert Excel → CSV client-side. Server-side .xlsx parsing lands later.
* OCR / PDF parsing of scanned class lists — `BulkUpload` accepts PDFs but server-side OCR is not wired. Tagged for a follow-up.
* Channel-config UX — Phase 12c endpoints exist; a `setup/notifications/page.tsx` is a follow-up.
* Phone-number normalisation to ZW E.164 — out of scope for v1.
