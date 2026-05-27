# ADR 024 — Cross-tenant template sharing + curriculum upgrade diff view (Phase 18)

**Status**: Accepted 2026-05-27
**Closes**: Phase 18 — "Cross-tenant sharing + curriculum diff" follow-ups from ADR 023
**Builds on**: ADR 020 (cross-school sentinel + Ministry-inside-admin-web), ADR 021 (Provisioner / EduZimOps), ADR 022 (Phase 16 curriculum + question bank + templates), ADR 023 (Phase 17 content-layer polish)

## Context

ADR 023 explicitly deferred two items to Phase 18:

1. **Curriculum diff view** — when the Ministry republishes a ZIMSEC subject, a HoD should see "what will change?" before committing the upgrade. Phase 17d shipped the upgrade endpoint but the only way to find out what it would do was to run it.
2. **Cross-school template sharing** — the Phase 16d HomeworkTemplate / LessonPlanTemplate tables are per-school. NGOs and Ministry curriculum specialists want to publish canonical patterns into a global catalog that any school can adopt — the same publish/adopt pattern Phase 16a used for ZIMSEC subjects, applied to templates.

Phase 18 closes both. Scoped narrow on purpose: bigger items (OCR, essay auto-grading, S3 storage, JSONB GIN-index swap) stay deferred.

## Decisions

### 1. Curriculum upgrade preview as a read-only sibling of `/curriculum/upgrade-subject`

New endpoint `GET /api/v1/curriculum/upgrade-subject/preview?school_subject_id=X` returns the diff that the existing `POST /curriculum/upgrade-subject` would apply, without mutating anything:

```jsonc
{
  "subject_id": "...",
  "from_version": 1,
  "to_version": 2,
  "no_op": false,
  "units_to_add":    [{ "national_unit_id", "code", "name", "grade_level", "sequence_order" }],
  "units_to_update": [{ "local_unit_id", "national_unit_id", "code", "changed_fields": ["name", ...] }],
  "topics_to_add":   [{ "national_topic_id", "code", "name", "sequence_order" }],
  "topics_to_update":[{ "local_topic_id", "national_topic_id", "code", "changed_fields": ["learning_outcomes", ...] }],
  "local_custom_units_preserved_count": 0,
  "local_custom_topics_preserved_count": 1,
  "local_nationally_orphaned_units_count": 0,
  "local_nationally_orphaned_topics_count": 0
}
```

`changed_fields` is the list of column names whose value differs between the school-local row and its national counterpart on the new version. The endpoint is safe to call repeatedly — the audit row (`curriculum.subject.upgrade_previewed`) carries only counts, not content.

Code path is intentionally a separate function rather than a flag on `upgrade_subject`, because the mutation logic and the diff logic share enough but not all of the same SQL; sharing through a flag risks accidentally committing a "preview" run.

**UI**: `apps/admin-web/(admin)/curriculum/[subjectId]/upgrade-preview/page.tsx` shows the diff in two columns (adds vs. updates) with counters at the top. The main `/curriculum` page shows a "Review upgrade" CTA in an alert whenever `is_stale === true`.

### 2. Ministry-distributed template library (`NationalHomeworkTemplate` / `NationalLessonPlanTemplate`)

Two new global tables, parallel to `NationalSubject`:

* `national_homework_templates` — `(id, code, title, description, subject_code, topic_codes[json], grade_levels[json], default_due_days, published_at, archived_at, created_by_user_id, created_at, updated_at)`. `code` is the natural unique key.
* `national_lesson_plan_templates` — same shape, replacing `description`/`default_due_days` with `objectives` / `activities` / `resources` / `suggested_period_number`.

No `school_id` on either — they are global. Write access gated `school:create` (Provisioner / EduZimOps / Ministry); read access on the school-side browse endpoint gated `school:manage` (so any HoD / SchoolAdmin can scout the catalog).

**Subject + topic references by code, not ID.** A national template doesn't know about per-school Subject IDs (they differ per tenant). It stores the national `subject_code` and a list of national `topic_codes`, and the adopt path resolves them per-school at adopt-time.

**Phase 18b deliberately does NOT carry attachments cross-school.** The existing Phase 17a `/comm/attachments/clone-bulk` endpoint is tenant-scoped (source must belong to the caller's school). Bypassing that for `national_*` owner_kinds is doable but adds non-trivial surface (tenant gate becomes conditional, audit semantics need updating). National templates are text-only in v1; HoDs add their own attachments to the adopted local copy. Cross-tenant attachment sharing is documented as a Phase 19 follow-up.

### 3. Adopt path — extends existing per-school template tables

Each per-school template table gets a new nullable `source_national_template_id` column. `POST /national-templates/homework/{id}/adopt`:

1. Look up the national template; reject if not published or archived (`NOT_ADOPTABLE`).
2. Check for an existing local row with `(school_id == X AND source_national_template_id == national_id)` — if found, return it with `idempotent: true`. (Adopt is idempotent for the same reason `adopt-subject` is: schools may click twice or run a setup script repeatedly.)
3. Resolve `subject_code` → school's local `Subject` by matching `(school_id, code)`. Optional — when not found the local template is created with `subject_id = null` and `subject_resolved: false` returned so the HoD knows.
4. Resolve each `topic_code` → school's local `Topic` by matching `(school_id, code)` within the resolved subject (or any subject if subject didn't resolve). Each unresolved code is dropped from the local copy's `topic_ids` and reported back in `unresolved_topic_codes`.
5. Insert a new row in the per-school table with `maintained_by_user_id = adopter`, `is_published_school_wide = false` (HoD decides whether to publish), `source_national_template_id = national_id`.

The school-side browse endpoint (`GET /api/v1/national-templates/homework`) enriches each row with `adopted_local_template_id` so the UI can render "Adopted" vs "Adopt" without a second round-trip.

### 4. Gateway routes added

Phase 17d's curriculum upgrade routes were not in the explicit RBAC list (defaulted to `authenticated`). This ADR closes that defence-in-depth gap:

```
GET  /api/v1/curriculum/upgrade-subject/preview        → school:manage
POST /api/v1/curriculum/upgrade-subject                → school:manage
GET  /api/v1/ministry/national-templates               → authenticated
POST /api/v1/ministry/national-templates/              → school:create
GET  /api/v1/national-templates                        → school:manage
POST /api/v1/national-templates/                       → school:manage
```

Service routing (prefix → service) extended for `/api/v1/ministry/national-templates` and `/api/v1/national-templates`, both → academics.

## Audit invariants (per ADR 018, reaffirmed)

| Event | Target | Details |
|---|---|---|
| `curriculum.subject.upgrade_previewed` | `{school_id, subject_id, national_subject_id}` | `{from_version, to_version, units_to_add_count, units_to_update_count, topics_to_add_count, topics_to_update_count, local_custom_units_preserved_count, local_custom_topics_preserved_count}`. NO names. NO codes. |
| `national_template.created` | `{template_id, kind}` (cross-school sentinel for school_id) | `{subject_code, topic_codes_count, has_grade_levels}`. NO title. NO body. |
| `national_template.published` | `{template_id, kind}` (sentinel) | `{}` |
| `national_template.archived` | `{template_id, kind}` (sentinel) | `{}` |
| `national_template.adopted` | `{school_id, national_template_id, local_template_id, kind}` | `{topics_resolved, topics_unresolved, subject_resolved}`. NO names. |

All Phase 16 / 17 audit invariants continue to hold. Confirmed by:
* `test_curriculum_versioning::TestUpgradePreview::test_preview_audit_carries_counts_not_names`
* `test_national_templates::TestAudit::test_audit_carries_no_titles_or_bodies`

## UI changes

* `apps/admin-web/(admin)/curriculum/page.tsx` — subject-list buttons now show stale badge + ZIMSEC version; "Review upgrade" alert appears at the top of the tree when the active subject is stale.
* `apps/admin-web/(admin)/curriculum/[subjectId]/upgrade-preview/page.tsx` — diff page with counter cards + two-column add/update lists + orphan warning + Confirm CTA.
* `apps/admin-web/(admin)/templates/national/page.tsx` — HoD-facing browse + adopt catalog.
* `apps/admin-web/(ministry)/ministry/templates/page.tsx` — Ministry catalog with publish + archive toggles.
* `apps/admin-web/(ministry)/ministry/templates/new/page.tsx` — kind-switching form for new homework or lesson-plan template.

## Consequences

### Positive
* HoDs see the consequences of `POST /curriculum/upgrade-subject` before pressing the button. Three weeks ago the only way to know "did this change anything?" was to run it and inspect counts post-hoc — the preview turns it into a glance.
* NGOs and the Ministry can publish canonical templates once and every school can pull them in with one click. The adopt path is idempotent (safe to rerun in setup scripts) and reports unresolved topic codes so HoDs can patch their curriculum tree without guessing.
* The `source_national_template_id` back-ref lets the UI render "Originally from Ministry" / "Originally from <NGO>" on the school's local template page (Phase 19 surface — column exists, UI is a small follow-up).

### Negative
* v1 has no attachment-sharing cross-school. National templates are text-only. Documented above; tracked as a Phase 19 task. In practice, attachments are typically scanned past papers / PDFs that the Ministry would distribute through a separate channel anyway — this isn't a blocker for the NGO use-case.
* Adopt resolves topic codes by exact-match on `(school_id, code)` — if the school renamed a topic's code locally, that code will fail to resolve and end up in `unresolved_topic_codes`. The UI surfaces the list so the HoD can patch their tree, but there's no automatic fuzzy-match. Acceptable.
* The Ministry catalog could become large over time (hundreds of templates). v1 doesn't paginate the browse — all published rows return in one list. Pagination is a Phase 19 follow-up.

## What this ADR does NOT decide

* **Cross-tenant attachment sharing** — `national_*_template` rows currently can't carry PDFs / images. Phase 19.
* **Diff view for the broader Ministry republish flow** — only the subject-level diff is in scope. Per-question-bank or per-template diff (when those become versioned) is a Phase 19+ task.
* **Template versioning** — `NationalHomeworkTemplate` has no `version` column. The Ministry edits in place via PUT, and adopted school copies don't auto-update. Versioned national templates with a similar upgrade flow are a Phase 19+ task.
* **Bulk CSV import of national templates** — only one-at-a-time create today. Bulk-CSV mirrors the Phase 16a/17c pattern; deferred to Phase 19.
* **NGO publisher onboarding flow** — an NGO publishes today by being granted the `EduZimOps` role (per ADR 021). A dedicated "Publisher" tier with audit segregation is a Phase 19+ governance question.
* **OCR for scanned PDFs / images** (Tesseract) — Phase 19+.
* **Essay auto-grading**, **JSONB GIN-index swap**, **S3 storage backend** — Phase 19+.
