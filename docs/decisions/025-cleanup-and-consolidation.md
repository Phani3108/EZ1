# ADR 025 — Cleanup & consolidation (Phase 19)

**Status**: Accepted 2026-05-28
**Closes**: Phase 19 — bugs, silent risks, doc drift identified in the post-Phase-18 audit
**Builds on**: ADRs 018 (audit invariants), 020 (cross-school sentinel), 021 (Provisioner role), 022/023/024 (Phase 16/17/18 work)

## Context

After Phase 18 closed cross-tenant template sharing and the curriculum upgrade preview, a 3-agent audit found that ~80% of Phase 16-18 work was technically shipped but practically unreachable. The audit returned a punch list of 6 critical bugs, 9 high-severity silent risks, 7 medium polish items, and 8 logical/architectural drift items.

This phase does not add features. It closes the gap between "shipped" and "usable" so the next feature phase starts from a clean base.

## Decisions

### 1. Make the work visible (audit Critical-1)

`apps/admin-web/src/lib/nav.ts` gained four new sections: **Setup** (Phase 15), **Curriculum** (Phase 16-18) with Overview / Coverage / Adopt ZIMSEC, **Question Bank** (Phase 16c) review queue, and **Templates** (Phase 16d + 18b) with school library + Ministry/NGO catalog.

`apps/admin-web/src/app/(ministry)/layout.tsx` gained two new entries: **Curriculum import** (Phase 17c) and **Templates catalog** (Phase 18b/c).

Without these, the only way to reach the Phase 16-18 pages was URL-typing. The features existed; they were invisible.

### 2. Fix RBAC trap on template instantiate (audit Critical-2)

The Phase 16d gateway rule `("POST", "/api/v1/homework-templates/", "school:manage")` matched everything under that prefix, including `/{id}/instantiate` — the very flow built for plain teachers. Same trap on `/lesson-plan-templates/`.

The fix is two-layer:
* **Gateway** — opened the prefix to `authenticated`. Any teacher can call instantiate or sync-from-template.
* **Backend** — `content_template_routes.py` now asserts `school:manage` in-process for `publish-school-wide` + `unpublish` handlers. A plain teacher hitting them gets `403 INSUFFICIENT_PERMISSION` from the route handler.

New tests in `test_content_templates.py`:
* `test_teacher_without_school_manage_can_instantiate` — proves the fix
* `test_teacher_without_school_manage_cannot_publish_school_wide` — proves the defence-in-depth
* `test_lesson_plan_template_same_gate` — same shape for LP

The `_has_perm()` helper accepts both `ActorContext` (new dataclass) and the legacy dict form, so the check works across the codebase.

### 3. Identity admin reachable through gateway (audit Critical-3)

`POST /users`, `/users/{id}/reset-password`, `POST /roles`, `/roles/{id}/permissions`, `GET /permissions`, `/preferences`, `/forgot-password`, `/reset-password` were registered in identity routers but had no `SERVICE_ROUTES` entry. Either admin-web was broken or identity was reached via a direct port (RBAC bypass risk).

Added six new prefixes to `SERVICE_ROUTES` and 11 new RBAC entries (password-reset flows public; user/role admin behind `school:manage`; self-service preferences `authenticated`).

### 4. Stop tracking SQLite test artifacts (audit Critical-6)

`git rm --cached` on 18 `test_*.db-shm` + `test_*.db-wal` files. `.gitignore` already matched them; the files had been committed before the rule.

### 5. Phase 17b thumbnails actually rendered (audit Critical-5)

New primitive `packages/ui/src/components/attachment-image.tsx` (`<AttachmentImage>`) takes an `attachmentId` + `hasThumbnail` + `gatewayBase` and renders either the 256×256 JPEG from `/comm/attachments/{id}/thumbnail` (lazy-loaded, clickable through to full bytes) or a labelled placeholder pill when there's no thumbnail.

The endpoint had existed since Phase 17b with zero usage. The primitive's existence + export from `@eduzim/ui` lets all three apps adopt it incrementally without a coordinated migration. First consumers (announcement feed, curriculum tree) tracked as Phase 20 follow-ups.

### 6. Adopt-template race protection + visible-failure (audit High-1, High-2, High-3)

* **DB uniqueness**: new Alembic migration `2026_05_28_024_template_adopt_uniqueness.py` adds `UniqueConstraint(school_id, source_national_template_id)` on both `homework_templates` and `lesson_plan_templates`. The constraint is partial-in-spirit (only matters for rows with non-null source — NULLs are distinct on both Postgres and SQLite).
* **Race-safe handler**: `national_templates_routes.py` adopt paths now wrap `db.flush()` in a `try/except IntegrityError`. On conflict the handler rolls back, refetches the existing row, and returns it as `idempotent: true`. Two concurrent adopts now reliably converge on one local clone.
* **CloneResult dataclass**: `attachment_client.py` changed return type from `int` to a `CloneResult` carrying `cloned_count`, `error_kind` (`disabled_env` / `http_status` / `transport` / `parse` / `None`), and a 1-line `error_detail`. The dataclass is truthy when count > 0 and exposes `__int__` so old `attachments_cloned: int` audit fields keep working.
* **Visible failure**: both `template.instantiated` audit events now carry `attachment_clone_error` alongside `attachments_cloned`. A HoD's audit log will no longer show a green checkmark on a template where every attachment silently failed to copy. The reporting consumer can grep for non-null `attachment_clone_error` to surface a banner.
* **Warn-once**: the `EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1` short-circuit now logs once per process when first triggered, so a developer who sets it locally sees one line confirming attachments will be skipped.

### 7. Audit invariant tightening (audit High-4, Medium-1, Medium-2, Medium-4)

* `payment.initiated.manual` now carries `amount` in `details`, matching the other money-move events (ADR 018 carves out amounts for money-move story).
* `announcement.created` no longer logs `title` (free text — was leaking "Re: J. Sithole disciplinary"-style PII). Replaced with `title_length`.
* `contract.issued` no longer logs `role_title` (free String — admins were typing names into it). Only `salary_band` survives.
* `_resolve_topics_for_school` dedupes `topic_codes` preserving order. A Ministry author listing the same code twice would otherwise pollute the adopted local template's `topic_ids` JSON with duplicates.

### 8. LinkButton primitive (audit Critical-4)

New `packages/ui/src/components/link-button.tsx` wraps `buttonVariants` around a real `<a>`. Eight `<Button><Link>` sites migrated:
* `(admin)/curriculum/page.tsx` ×3
* `(admin)/curriculum/[subjectId]/upgrade-preview/page.tsx` ×1
* `(ministry)/ministry/curriculum/page.tsx` ×1
* `(ministry)/ministry/curriculum/import/page.tsx` ×1
* `(ministry)/ministry/templates/page.tsx` ×1
* `(admin)/setup/page.tsx` ×2
* `(admin)/setup/school/page.tsx` ×1
* `(admin)/setup/classes-subjects/page.tsx` ×2

This fixes invalid `<button><a>` markup, restores keyboard navigation (Enter/Space follows the link), and unbreaks the accessibility tree.

### 9. Identity sentinel UUID aligned with ADR 020 (audit High-8)

`services/identity/app/api/auth.py` used `00000000-…-0` as the unknown-school sentinel for failed-login audit rows. ADR 020 standardized on `eeeeeeee-…-eeeeeeeeeeee` across services. Identity is now consistent. Audit table has one cross-school sentinel value.

### 10. Teacher-web staleness indicator (audit High-5)

`apps/teacher-web/src/lib/curriculum-api.ts` `SchoolSubject` now exposes `adopted_national_version`, `national_current_version`, `is_stale`. The teacher curriculum sidebar renders a yellow `stale` badge + ZIMSEC version line when the HoD has a pending upgrade. The "Review upgrade" button stays admin-only (Phase 18a); teachers just know it's pending.

### 11. Invite-landing error UX (audit High-7)

The three invite-landing pages (`apps/parent-web/invite/[token]`, `apps/parent-web/invite/code`, `apps/teacher-web/invite/[token]`) previously surfaced a generic "Sorry: <backend message>" for every fetch failure. Each now uses a per-status `_friendlyInviteError(status, body)` helper that returns specific copy for 404 (link invalid), 410 (expired), 409 (already activated), 429 (rate-limited), and 5xx (server). Network errors get a single "Check your internet" line instead of a stringified Error.

### 12. Ministry layout mobile nav (audit Medium-5)

`apps/admin-web/src/app/(ministry)/layout.tsx` was `hidden lg:flex` — Ministry users on phone saw no nav at all. Phase 19d adds a sticky `<lg` mobile header with a hamburger that slides the existing sidebar in as an overlay; tapping any link dismisses the overlay. Desktop behavior unchanged.

### 13. STATUS.md / task.md / Makefile / scripts dead-service refs (audit High-9, Medium-7+)

* STATUS.md "Known backend bugs" table no longer cites deleted `services/attendance-service/`, `services/auth-service/`, `services/fees-service/` paths. Each row marked closed with the actual Phase that closed it (Phase 1 for the secret-defaults, Phase 2 for the migrations race, Phase 4 for the silent-except blocks).
* task.md had duplicate `BUG-008` and `BUG-009` IDs. Renumbered the i18n-translation row to `BUG-011`.
* `Makefile`'s `test` target referenced four deleted services. Now lists the four surviving services + reporting-consumer + api-gateway.
* `scripts/init-tables.py` marked deprecated with `sys.exit(2)` early-out + module docstring pointing at `alembic upgrade head`. The legacy `SERVICES` map is preserved below the exit for any operator who reads the file.
* `scripts/import_master.py` docstring now annotates the pre-PH2 DB URL names with their post-consolidation collapse target (`→ academics_db`).

## Audit invariants

This ADR tightens but does not change ADR 018. The four affected events:

| Event | Before | After |
|---|---|---|
| `payment.initiated.manual` | `{provider}` | `{provider, amount}` |
| `announcement.created` | `{title, audience_type, channel_count, recipient_count}` | `{title_length, audience_type, channel_count, recipient_count}` |
| `contract.issued` | `{role_title, salary_band}` | `{salary_band}` |
| `template.instantiated` | `{template_type, class_id, attachments_cloned}` | `{template_type, class_id, attachments_cloned, attachment_clone_error}` |

`attachment_clone_error` is a small enum (`disabled_env` / `http_status` / `transport` / `parse` / null). No free-text leaks.

## Consequences

### Positive
* Sidebar entries exist for every Phase 15-18 admin & Ministry surface. The completion gap between "code shipped" and "user can reach it" is closed.
* Teachers can instantiate templates again (was 403'd by the gateway prefix bug).
* SchoolAdmin user/role admin reachable through gateway → admin-web works end-to-end without direct-port access.
* HoDs see when attachment clones partially failed instead of accepting a false-green audit row.
* Concurrent adopt requests no longer create duplicate local templates.
* Eight sites no longer ship invalid `<button><a>` markup; keyboard nav restored.
* Ministry users on phone can now reach navigation.
* Audit invariants tightened — `title`, `role_title`, and free-text leaks removed without losing operational signal.

### Negative
* The new `_has_perm` helper duplicates logic that arguably belongs in a `require_permission` FastAPI dependency. Justification: keeping it inline in the handler makes the contract loud at the call site. A future architectural cleanup could promote it to a dependency.
* `CloneResult` is a backward-incompatible return type. Only two call sites use it (homework + lesson-plan instantiate); both migrated. Any third-party caller (none exist today) would need to migrate.
* The mobile ministry nav uses local component state, not a global navigation store. Fine at current scale; if more Ministry mobile features land we'd want a shared `useMobileNav` hook.

## What this ADR does NOT decide

* **`eduzim_shared.response` / `eduzim_shared.routes` extraction** — the audit flagged ~2,000 lines of duplicated `_meta/_err/_ok/_audit/CROSS_SCHOOL_SENTINEL` across services. Useful cleanup, deferred to Phase 20 because the migration touches every routes file and would balloon this commit.
* **`services/*/tests/conftest.py` shared fixtures** — 38 academics test files re-define `engine_and_session` + `client`. Same story: deferred to Phase 20.
* **Permission enum in `shared/eduzim_shared/permissions.py`** — 223 raw permission strings across services with no typo protection. Phase 20 codemod.
* **`Subject.national_subject_id` type normalization** — the String(36) vs UUID mismatch is annoying but the Python-side iteration workaround works. One ALTER COLUMN migration in Phase 20.
* **Kafka integration coverage** — `KAFKA_ENABLED=false` in tests gives zero coverage of the real event path. Phase 7's staging gate is still the only exercise.
* **`.env.example` regeneration** — at least 11 env vars are read but not documented. Phase 20 chore.
* **OCR, S3 storage, essay auto-grading, JSONB GIN swap** — still deferred per ADR 023/024.
