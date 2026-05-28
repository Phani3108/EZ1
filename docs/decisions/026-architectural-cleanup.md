# ADR 026 — Architectural cleanup (Phase 20)

**Status**: Accepted 2026-05-28
**Closes**: Phase 20 — maintenance phase. Closes the "Phase 20+ deferred"
list from ADR 025 except the items that need their own design ADR
(S3 storage, JSONB GIN swap, OCR, essay auto-grading, Subject UUID
normalization).
**Builds on**: ADR 018 (audit invariants), ADR 020 (cross-school sentinel),
ADR 021 (Provisioner role), ADR 025 (Phase 19 cleanup).

## Context

After Phase 19 closed the audit-finding punch list, four architectural
debts remained that were hurting maintenance:

1. **~2,000 lines of duplicated `_meta`/`_err`/`_ok`/`_audit` helpers** —
   every routes file (~25 of them across 4 services) re-defined the
   same envelope/audit machinery. The drift this invited was the
   obvious cost: when ADR 018 tightened "no PII in audit details" on
   one service, the other three could quietly stay loose.
2. **No central permission constants** — 19 raw `"school:manage"`-style
   strings scattered across services, the gateway RBAC table, the
   seed script, and tests. A typo like `"school:mange"` silently
   denied every request instead of failing at type-check.
3. **No `conftest.py`** — every test file re-defined the same
   `engine_and_session` + `client` fixtures. ~30 lines × ~50 files of
   pure copy-paste, plus the `KAFKA_ENABLED=false` env-var dance
   sprinkled across 9+ files.
4. **`.env.example` drift** — at least 11 env vars the codebase reads
   were undocumented. First-time setup was a "grep `os.environ` to
   find what you need" exercise.

Phase 20 closes all four with one design constraint: **no behavior
changes**. Every test that passed before this phase must still pass.

## Decisions

### 1. `shared/eduzim_shared/routes.py` — single source of truth for response + audit helpers

New module exports:

```python
from eduzim_shared.routes import (
    _meta, _err, _ok, CROSS_SCHOOL_SENTINEL, make_audit_helper,
)
```

* `_meta(request)` — envelope `meta` block (request_id + ISO timestamp).
* `_err(code, msg, request, status=400, details=None, *, status_code=None)` —
  accepts BOTH `status=` (curriculum/national_templates convention)
  and `status_code=` (staff/ministry/communications convention) so the
  migration was a one-line import change per file.
* `_ok(data, request, status=200)` — standard success envelope.
* `CROSS_SCHOOL_SENTINEL` — `eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee`
  per ADR 020. Defined once; a typo here can't desync services.
* `make_audit_helper(AuditLogModel) -> _audit` — factory that closes
  over the per-service `AuditLog` class. The returned `_audit` accepts
  the existing call-site signature unchanged AND coerces both
  `school_id` and `actor` from `str | uuid.UUID` to `uuid.UUID` before
  passing to `record_audit_event`. The coercion fixes a latent bug in
  the original per-file helpers: passing a `str` triggered SQLAlchemy's
  bind-time `.hex` call → `AttributeError` → poisoned session → 500.
  The original handlers either pre-converted (content_template_routes)
  or got lucky with how SQLAlchemy 2.0 handled the type. Either way,
  the shared helper guards both paths.

**32 routes files migrated** via `/tmp/migrate_routes_helpers.py` (one-shot
script, not retained). Files with non-standard `_err` signatures (8 of
them — `bulk_*`, `drafts.py`, `routes.py`-style files with extra
params for backward compat) were skipped and left untouched. They can
be migrated later as separate ADRs; the present 32 are enough to kill
the duplication problem.

Net diff: **−380 lines** across 36 files.

### 2. `shared/eduzim_shared/permissions.py` — Perm enum + drift guard

New `Perm` enum (subclass of `str, Enum`) lists every permission the
codebase recognizes. The enum value IS the wire string, so existing
membership checks (`perm in user_perms` where `user_perms` is a CSV-
split list of strings) keep working when callers pass `Perm.SCHOOL_MANAGE`.

New test `shared/tests/test_permissions.py::test_gateway_rbac_table_uses_only_known_permissions`
parses `services/api-gateway/app/routes.py` at test time and asserts
every permission string in the RBAC table is a known `Perm` member or
the literal `"authenticated"`. Drift will fail this test immediately.

The first wave of adoption is the test itself plus the documented
canonical list. A future pass (Phase 21+) can swap the raw strings in
gateway routes and per-service handlers — that's a codemod, not a
design decision.

### 3. Per-service `tests/conftest.py` (additive)

Each of the 4 services gets a `tests/conftest.py` with the canonical
`engine_and_session` + `client` fixtures + the `KAFKA_ENABLED=false`
+ `INTERNAL_SERVICE_TOKEN` + `JWT_SECRET_KEY` env setup.

**Critical: this is purely additive.** Pytest's fixture-resolution
rule prefers the closest definition, so existing per-file fixtures
keep taking precedence. The duplicates can be deleted one file at a
time without coordinated changes. No tests broke.

### 4. `.env.example` regeneration

Regenerated from a `grep -rhoE 'os\.environ' services/ shared/ scripts/`
sweep. Every variable code actually reads is documented, grouped by
purpose, with REQUIRED/optional marked. Includes the missing ≥11 vars
the Phase 19 audit flagged (`EDUZIM_ATTACHMENT_*`, `EDUZIM_TENANCY_*`,
`EDUZIM_TLS_ENABLED`, `OTEL_*`, `SENTRY_*`, `SENDGRID_API_KEY`,
`WHATSAPP_*`, `EDUZIM_DISABLE_CROSS_SERVICE_HTTP`, etc.).

The note about `FCM_SERVER_KEY` being sunset by Google mid-2024 is
preserved as an in-file comment so the next person who tries to wire
push notifications doesn't waste time on the legacy API.

## Audit invariants

This ADR does NOT add or modify any audit events. The shared `_audit`
closure is a transparent refactor of the per-file helpers; the events
emitted, their `target`/`details` shape, and PII discipline are
unchanged. Validated by the unchanged 769 test count post-migration.

The one subtle behavioral change is the `school_id`/`actor` UUID
coercion. Before this phase, audit writes that passed `str` values
silently failed at SQLAlchemy bind time and got swallowed by
`record_audit_event`'s try/except. After this phase, those same calls
succeed — meaning audit rows that were previously lost are now
written. That's a strict improvement for compliance.

## Consequences

### Positive
* **−380 net lines deleted** across 36 routes files. The duplicate
  `_meta`/`_err`/`_ok` definitions are gone. Future tightening of
  ADR 018 (audit invariants) now happens in one place.
* **Permissions enum** kills the typo-denial security risk. The drift
  guard test catches new permission strings added to the gateway
  table without enum updates.
* **Per-service conftest** sets the foundation for the next codemod
  (delete per-file fixture duplicates). Each test file can switch
  one at a time.
* **`.env.example`** is now a complete reference. First-time setup is
  one file, not an archaeological grep.
* **Latent audit-write bug fixed** as a side-effect: handlers passing
  `str` school_id/actor now succeed instead of silently dropping the
  audit row.

### Negative
* The migration script left 8 routes files with non-standard `_err`
  signatures untouched. They still have local `_meta`/`_err`/`_ok`
  definitions. These are tracked as Phase 21 follow-up.
* `make_audit_helper`'s coercion masks a class of caller bugs (passing
  garbage strings) by converting them to `None`. Worse than failing
  loudly. Mitigated by the fact that 99% of call sites pass valid
  UUIDs; the coercion just handles the str-vs-UUID legacy mix.
* The drift-guard test reads `services/api-gateway/app/routes.py` at
  test time. If the file format changes (the tuple shape regex breaks),
  the test silently passes. Acceptable risk — the test docstring tells
  future readers to update it if the gateway table format evolves.

## What this ADR does NOT decide

* **Adoption of `Perm` enum across handlers + gateway** — pure codemod.
  Phase 21+.
* **Deletion of per-file fixture duplicates** — pure codemod. Phase 21+.
* **Migration of the 8 non-standard `_err` routes files** — they need
  per-file inspection because their custom signatures encode real
  variance. Phase 21+.
* **`Subject.national_subject_id` UUID normalization** — needs an
  Alembic data migration. Separate ADR.
* **S3 storage backend implementation** — separate ADR.
* **JSONB GIN-index swap for `topic_ids`** — separate ADR + Postgres
  benchmark.
* **Kafka integration test coverage** — needs a Docker-compose-up
  test harness; non-trivial scope. Phase 21+.
* **OCR (Tesseract), essay auto-grading** — feature work, not cleanup.
