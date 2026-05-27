# EduZim Data Retention Policy (Draft v0.1 — Q-009)

> **Status**: Draft. Pre-pilot legal review required (ADR 005).
> **Last updated**: 2026-05-26
> **DPO contact**: dpo@eduzim.co.zw
> **Related**: Privacy Policy, ADR 007 (privacy-by-design), Phase 9 work items.

---

## Principle

We keep personal data only as long as it serves the purpose for which it
was collected, or as long as the law requires — whichever is longer. When
neither applies, we delete or anonymise.

Academic records have a longer retention than operational data because
historical transcripts have ongoing legal value (school applications,
employer verification) for many years after a student leaves.

## Retention table

| Data class | Retention | Trigger to delete / anonymise |
|---|---|---|
| **Live student record** (identity, enrollment, marks, attendance) | Duration of enrollment + 7 years after graduation / withdrawal | On the 7-year anniversary, identifying fields (name, DOB) are replaced with a hashed identifier; academic records (marks, transcripts) retained anonymised for statistical / verification use. |
| **Behavioural / disciplinary incidents** | 3 years after the incident OR until graduation, whichever is sooner | Deleted at the trigger. |
| **Health records** (allergies, vaccinations) | Duration of enrollment | Deleted on withdrawal / graduation. |
| **Live parent record** | Duration of any linked-child enrollment + 1 year | Deleted 1 year after last child leaves. |
| **Communications** (announcements, message threads) | 2 years | Auto-purged. Audit log retains the metadata (sender, recipient count, timestamp) longer. |
| **Notification outbox** entries | 90 days for delivered / failed; 7 days for cancelled | Pruned by a background job. |
| **Login audit (`login_audit` table)** | 1 year | Auto-purged. |
| **General audit log (`audit_log` table)** | 2 years | Auto-purged. |
| **Refresh tokens** | Until cookie max-age (30 days) OR explicit revoke | Hard-deleted on revoke. |
| **Password reset tokens** | 1 hour (TTL) | Hard-deleted after use or expiry. |
| **Photographs / file attachments** | Same as the record they're attached to | Cascade delete with the parent record. |
| **Financial: invoices** | 7 years (statutory) | Statutory floor — overrides school-level deletion requests. |
| **Financial: payments** | 7 years (statutory) | Same. |
| **Postgres backups** (snapshots from `pg-backup`) | 14 most recent snapshots (default; configurable per school tier) | Rolling deletion of older snapshots. |
| **Application logs** (structured JSON) | 90 days (Phase 6) | Loki retention policy when wired. |
| **Distributed traces** (when wired in Phase 17) | 7 days | Tempo retention. |

## Special cases

### Right to be forgotten
Where the law permits (i.e., outside the 7-year statutory floor for
financial records), a verified deletion request results in:

1. Identifying fields replaced with a hashed identifier (one-way) in the
   same row — academic relationships preserved but no longer linkable
   back to a person.
2. Photographs and free-text comments deleted hard.
3. Backups still containing the original data are not modified, but the
   next-but-one backup cycle (≤ 28 days) ensures the original is rolled
   out of the retained snapshot set.
4. The deletion is logged in `audit_log` for compliance evidence.

### Litigation hold
A school admin or the DPO can place a "litigation hold" on a record,
which suspends the retention timer until released. Implementation
deferred to Phase 17.

### School-level offboarding
When a school terminates its EduZim subscription:

1. School data is exported (the export endpoint produces a zip per ADR 009
   tenancy tier).
2. The school's primary admin acknowledges receipt.
3. After a 30-day grace period, the school's tenant data is hard-deleted
   from primary storage.
4. Existing backup snapshots roll out per the normal retention cycle.

## Open items

- Per-school configurable retention for non-statutory data (some schools
  may want longer or shorter than the defaults above) — Phase 9 PH9-2.
- Automated purge job (currently retention is documented but enforcement
  is manual) — Phase 9 PH9-3.
- Anonymisation logic for student records past the 7-year boundary —
  Phase 9 PH9-4.
- Audit-log retention enforcement (Q-016) — Phase 9.
