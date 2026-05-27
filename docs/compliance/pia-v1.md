# Privacy Impact Assessment (PIA) v1 — EduZim

> **Status**: PH9-1 draft. Skeleton with the PII inventory; full PIA review (risk ratings, mitigation tables) and lawyer sign-off happen pre-pilot per ADR 005.
> **Last updated**: 2026-05-26
> **Owner**: DPO (`dpo@eduzim.co.zw`)
> **Related**: ADR 007 (privacy-by-design), Privacy Policy, Retention Policy.

---

## 1. Purpose

This PIA documents every PII field EduZim collects, why we collect it, how
long we keep it, who can access it, and the inherent risk. The
minimum-data principle (ADR 007) is enforced through this table: any new
field added in any phase must be added here, with the same level of
detail, before the PR merges.

## 2. PII inventory

### 2.1 Identity service (`identity_db` / `users` table)

| Field | Purpose | Sensitivity | Retention | Access scope |
|---|---|---|---|---|
| `email` | Login + transactional comms | Medium | While account active + 7 years | Owner + school admin + DPO |
| `full_name` | UI display, audit trail | Medium | Same | Same |
| `password_hash` | Auth | High (sensitive credential) | Until rotated / deleted | None (hashed, never read in clear) |
| `school_id` | Multi-tenant scope | Low | Forever (schema-mandatory) | All same-school users |
| `roles` | RBAC | Low | Until role changes | Owner + school admin |

### 2.2 Identity — login audit (`login_audit`)

| Field | Purpose | Retention | Risk |
|---|---|---|---|
| `email`, `school_id` | Identify the actor | 1 year | Medium — login email is PII |
| `ip_address` | Anti-abuse forensics | 1 year | Medium — IP is treated as PII in GDPR/ZDPA |
| `user_agent` | Device fingerprinting (defensive) | 1 year | Low |
| `success`, `failure_reason` | Audit trail | 1 year | Low |

### 2.3 School service (now → academics_db post-PH2-6)

| Table | Fields | Sensitivity | Retention |
|---|---|---|---|
| `schools` | name, address, phone, principal_name | Low (institutional, not personal) | Indefinite |
| `academic_years` / `terms` | dates only | None | Indefinite |
| `classes` / `subjects` | name, section, capacity | None | Indefinite |
| `class_teacher_assignments` | `teacher_user_id` (FK to identity), `class_id` | Low | Until reassignment |

### 2.4 Student service (post-PH2-7 → academics_db)

| Field | Purpose | Sensitivity | Retention | Children's Act flag |
|---|---|---|---|---|
| `first_name`, `last_name`, `dob`, `gender` | Identity | **High (minor's identity)** | Enrollment + 7 years; then hashed | YES |
| `admission_number` | School-side ID | Medium | Same | YES |
| `student_code` | Internal stable identifier | Low (opaque) | Same | — |
| `guardian_primary_phone` | Emergency contact (denormalised from `parents`) | High (PII of an adult, but child-relationship) | Same | YES |
| `status` (active / withdrawn) | Lifecycle | Low | Same | — |

### 2.5 Parent records

| Field | Purpose | Sensitivity | Retention |
|---|---|---|---|
| `first_name`, `last_name` | Identity | Medium | Until last linked child leaves + 1y |
| `phone`, `email` | Contact | Medium | Same |
| `relationship_type` | Family context | Low | Same |

### 2.6 Attendance

| Field | Purpose | Sensitivity | Retention |
|---|---|---|---|
| `student_id`, `class_id`, `date`, `status` (P/A/L) | The core feature | Medium (movement-of-minor) | Enrollment + 7 years |
| `marked_by_user_id` | Audit | Medium | Same |
| `device_id` | Offline-sync provenance | Low | Same |

### 2.7 Assessment marks

| Field | Purpose | Sensitivity | Retention |
|---|---|---|---|
| `assessment_id`, `student_id`, `marks_obtained`, `is_absent`, `remarks` | Academic record | Medium-high | 7 years (statutory transcript) |

### 2.8 Financial (fees-service / finance)

| Field | Purpose | Sensitivity | Retention |
|---|---|---|---|
| `invoice` (student_id, amount, status) | Billing | Medium | **7 years (statutory)** |
| `payment` (amount, method, reference) | Payment record | Medium | **7 years (statutory)** |
| `paynow_transaction` (reference, paynow_reference, error) | Reconciliation | Medium | **7 years (statutory)** |

### 2.9 Communications

| Field | Purpose | Sensitivity | Retention |
|---|---|---|---|
| `announcements.body` | Operational | Low-medium | 2 years |
| `notification_outbox` (user_id, channel, status) | Delivery audit | Medium | 90 days |
| WhatsApp / SMS message bodies | Communications | Medium | 2 years |

### 2.10 Cross-cutting

| Field | Notes |
|---|---|
| `X-Request-Id` | Logged but never tied to identifying claims in the application logs. |
| `created_by_user_id` / `updated_by_user_id` columns | Wherever they exist, treated as PII (an actor identity). |
| Photographs (when school enables) | Sensitive. Stored in object storage with per-school ACL. Retention: same as the parent record. |

## 3. Risk register (skeleton — formalise pre-pilot)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cross-tenant data leak via a bug | Low (today; tests asserted in Phase 1) | High | Mandatory cross-tenant tests Q-006; gateway-headers auth post-Phase 3. |
| Provider data leak (Paynow / Africa's Talking / FCM) | Low-medium | Medium | Per-school opt-in; only data needed for the operation is forwarded; provider TOS reviewed. |
| Backup snapshot leak | Medium | High | Snapshots encrypted at rest (Phase 9 follow-up); off-host backup encrypted in transit. |
| Compromised JWT_SECRET_KEY | Low | Catastrophic | Rotation procedure in `docs/runbooks/secrets-rotation.md`; gateway refuses known-bad secrets. |
| Parent receives wrong child's data | Low | High | Parent-child authz internal endpoint (Phase 1 hardened); audit log on access. |
| Subject access request mishandled | Medium | Medium | DPO trained; 30-day SLA documented. |

## 4. Outstanding work (Phase 9 follow-up)

- PH9-2: data-minimisation audit — go through this table and remove or anonymise fields we don't strictly need.
- PH9-3: per-parent and per-school data-export endpoints.
- PH9-4: right-to-delete endpoint with consent-aware tombstone behaviour.
- Q-016 / INFRA-018: audit log table fully wired; admin UI to browse it.
- ADR 005: Zimbabwean lawyer review.

## 5. Version history

- **v0.1 (2026-05-26)**: skeleton PIA. Fields inventoried, risk register stubbed. PH9-1 closed; PH9-2 → PH9-4 pending.
