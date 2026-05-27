# ADR 023 — Content-layer polish: clone, thumbnails, versioning (Phase 17)

**Status**: Accepted 2026-05-27
**Closes**: Phase 17 — deferred follow-ups from Phase 16
**Builds on**: ADR 018 (audit invariants), ADR 020 (cross-school sentinel + Ministry-inside-admin-web), ADR 022 (Phase 16 curriculum + question bank + templates)

## Context

Phase 16 closed the academic-content layer (curriculum + question bank + templates) but explicitly tagged four follow-ups for a later phase:

1. **Attachment cloning on template instantiation** — Phase 16d's `POST /homework-templates/{id}/instantiate` and `POST /lesson-plan-templates/{id}/instantiate` always returned `attachments_cloned: 0`. Operators had to re-attach files manually on every instance.
2. **Server-side image thumbnails** — Attachments are served at full size, expensive on mobile data when an admin scrolls a long announcement feed.
3. **Curriculum versioning** — When the Ministry republishes a ZIMSEC subject after a syllabus review, schools that adopted v1 have no signal that a newer version exists and no path to pull updates while preserving local customisations.
4. **Ministry `/curriculum/import` UI** — The bulk CSV import endpoint existed (`POST /api/v1/ministry/bulk/national-curriculum`) but had no admin-web page wired to it.

Phase 17 closes all four. It is intentionally narrow: bigger items (OCR, cross-school template sharing, essay auto-grading) stay deferred to Phase 18.

## Decisions

### 1. Attachment cloning via a dedicated communications endpoint

Two new endpoints in communications:

* `POST /api/v1/comm/attachments/clone` — clones a single attachment to a new `(owner_kind, owner_id)`. Tenant-scoped: the source attachment must belong to the caller's school. Returns the new Attachment row.
* `POST /api/v1/comm/attachments/clone-bulk` — clones every non-deleted attachment for a given source owner to a new owner. Used by template instantiation; returns `{cloned_count, source_attachment_count, cloned_attachment_ids}`.

The academics service calls these via a small `services/academics/app/services/attachment_client.py` wrapper (`clone_attachments_for_owner`). The call is **best-effort**:

* If communications is unreachable (dev / tests / transient network), template instantiation still succeeds with `attachments_cloned: 0`. The audit row records the actual count.
* Set `EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1` to short-circuit the call in tests without hitting the network.

The clone copies bytes by reading `source.storage_uri` via `storage.open()` and writing a fresh URI via `storage.save()`. The new Attachment row has its own `id`, `storage_uri`, and `created_at`; the source row is untouched. This isolation is important: when a teacher edits the template's attachments later, instances created earlier don't change.

### 2. Image thumbnails via Pillow

New `services/communications/app/services/thumbnails.py`:

* Generates a JPEG thumbnail (max 256×256, quality 80, progressive) when the source MIME is `image/*` and the source decodes successfully.
* Skips animated GIFs and non-image MIMEs.
* Respects EXIF orientation (`ImageOps.exif_transpose`) so portrait photos render upright.
* Flattens transparent PNGs onto white before encoding to JPEG.
* Falls back to `None` (no thumbnail) when Pillow is missing or the image is malformed. The upload endpoint never fails because of a thumbnail issue.

Schema additions:

* `Attachment.thumb_uri` — nullable Text column. Set at upload time when a thumbnail was generated; null otherwise.
* The serializer exposes `has_thumbnail: bool` as a UI hint.

New endpoint: `GET /api/v1/comm/attachments/{id}/thumbnail` — serves the JPEG with `Cache-Control: private, max-age=3600`. Returns 404 (`NO_THUMBNAIL`) when the attachment isn't an image or pre-dates the Phase 17b wiring.

### 3. Curriculum versioning + upgrade path

Schema additions:

* `national_subjects.version` (int, default 1).
* `subjects.adopted_national_version` (int, nullable). Null for custom subjects; set to `NationalSubject.version` at adopt-time for nationally-adopted subjects.

Endpoints:

* `POST /api/v1/ministry/national-curriculum/subjects/{id}/republish` — bumps `version` + re-stamps `ministry_published_at`. Audit logs both `{from_version, to_version}`.
* `POST /api/v1/curriculum/upgrade-subject` — re-clones the latest NationalSubject tree into the school's local Unit/Topic tree:
  * For every NationalUnit/NationalTopic on the new version, upsert the corresponding school-local row by `national_*_id`. Updates name + sequence + learning_outcomes + grade_level if they changed.
  * For new National rows (added in the new version), create new local rows.
  * For local Unit/Topic rows where `national_*_id IS NULL` (school custom additions), **preserve untouched**.
  * For local rows whose national counterpart was removed in the new version, **keep them** (don't auto-delete content the school may rely on). The HoD can manually archive these via the standard `archived_at` flow.
* `GET /api/v1/curriculum/subjects` now returns `adopted_national_version`, `national_current_version`, and `is_stale` per row. The teacher-web and admin-web UIs render a "Ministry has published a newer version" indicator off `is_stale`.

The upgrade is idempotent: running it when `from_version >= to_version` returns `no_op: true` with zero changes.

### 4. Ministry `/curriculum/import` UI page

New `apps/admin-web/src/app/(ministry)/ministry/curriculum/import/page.tsx`. Drag-drop CSV upload that calls `POST /api/v1/ministry/bulk/national-curriculum` with `dry_run=true` first (shows preview counts + first-5 errors), then `dry_run=false` on confirm. Gated on the `school:create` permission — plain Ministry users see a "you need school:create" placeholder.

The page links to the canonical CSV template (`/api/v1/templates/national-curriculum.csv`) so EduZim Operations can download a starter file with the right column headers.

## Audit invariants (per ADR 018, reaffirmed)

| Event | Target | Details |
|---|---|---|
| `attachment.cloned` | `{school_id, attachment_id, owner_kind, owner_id, source_id}` | `{mime_type, size_bytes}`. Filename NOT logged (same rule as `attachment.uploaded`). |
| `attachment.cloned_bulk` | `{source_owner_kind, source_owner_id, new_owner_kind, new_owner_id}` | `{cloned_count}`. |
| `national_curriculum.subject.published` | `{national_subject_id}` | `{version}`. |
| `national_curriculum.subject.republished` | `{national_subject_id}` | `{from_version, to_version}`. |
| `curriculum.subject.upgraded` | `{school_id, subject_id, national_subject_id}` | `{from_version, to_version, units_added, units_updated, topics_added, topics_updated}`. NO topic/unit names. |

All Phase 16 audit invariants continue to hold. Confirmed by `test_curriculum_versioning::TestAuditVersioning` — version transitions + counts are logged but no syllabus content text reaches `target`/`details`.

## Consequences

### Positive
* A HoD can publish a homework template school-wide, and every teacher's instance comes with the full PDF / image / audio bundle the template owned — without anyone re-uploading anything.
* Mobile-friendly image rendering: the admin-web feed serves 256×256 JPEGs instead of full-size camera-roll PNGs. Significant payload reduction on Zimbabwe-typical 3G connections.
* The "stale curriculum" indicator surfaces the most common HoD workflow gap — a ZIMSEC review happened, did our school pull the changes? — in one glance on `/curriculum`.
* EduZim Operations no longer has to use raw `curl` to import ZIMSEC; the bulk-upload UI mirrors the school-side wizard.

### Negative
* The cross-service HTTP hop (academics → communications for clone) adds latency to template instantiation. Mitigated by the best-effort + degraded-on-failure pattern; instantiation never blocks on clone.
* Pillow is now a hard runtime dependency of the communications service. Adds ~10 MB to the container image. Falls back gracefully when missing but real installations should ensure it.
* `Attachment.thumb_uri` storage is additional disk. Estimated overhead: ~10% of original image storage. Acceptable.
* Curriculum versioning preserves locally-removed-but-still-present rows — schools that re-adopted v2 may carry deprecated topic rows until manually archived. This is the conservative choice (no data loss); future Phase 18 could add an opt-in "prune removed nationals" flag.

## What this ADR does NOT decide

* **OCR for scanned PDFs / images** — Tesseract integration. Real value for old past papers + handwritten worksheets but needs a system-level binary dependency. Deferred to Phase 18.
* **JSONB GIN-index swap** for `topic_ids` on Postgres — the current LIKE-substring query works fine at v17 scale; swap is a Phase 18 perf task.
* **Curriculum diff view** — when the Ministry republishes, a teacher might want to see "what changed?" before clicking upgrade. The current implementation just upgrades; a diff endpoint is Phase 18.
* **Cross-school template sharing** for NGO use-cases — Phase 18.
* **Essay auto-grading** (rubric- or LLM-assisted) — Phase 18.
* **Storage backend swap to S3** — `S3Storage` is still a stub. Production deployments use the LocalDiskStorage today. Phase 19 infra task.
