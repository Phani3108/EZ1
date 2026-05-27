# PH2-10 Cutover Runbook

> **Scope**: the operational steps to flip gateway traffic from the four pre-consolidation academic services (school-service, student-service, attendance-service, assessment-service) onto the consolidated `academics` service. Code-level changes are already landed (see `task.md` §12 PH2-10 entry); this runbook describes the *operational* event.
>
> **Related**: ADR 006 + addendum, PH2-6 → PH2-9 entries in `task.md`, `scripts/migrate-to-academics.sh`, `docs/runbooks/backup-restore.md`.
> **Status**: code-ready as of 2026-05-26. Execution happens on staging first, then production behind a maintenance window.

---

## Before you start

- [ ] Read this whole runbook.
- [ ] Confirm a `pg_dump` snapshot of all five academic DBs is < 24 hours old. (`scripts/migrate-to-academics.sh --dry-run` shows current row counts.)
- [ ] Confirm staging mirror has been burning in for ≥ 1 week with both old + new services running and gateway still routed at the old ones.
- [ ] Announce a maintenance window. The cutover itself is < 5 minutes if everything goes right; allow 30 minutes for rollback if it doesn't.
- [ ] Have one engineer on call for rollback (see §6).

## 1. Pre-flight — confirm state

```bash
# 1a. Verify all four old services are healthy.
for svc in school-service student-service attendance-service assessment-service; do
  curl -fs "http://${svc}:8000/health" || echo "  ✗ ${svc} unhealthy"
done

# 1b. Verify academics is healthy and reports the PH2-9 phase.
curl -fs http://academics:8000/health
curl -fs http://academics:8000/health/phase | jq .phase
# Expected: "PH2-9 — all four academic-domain services ... folded in. PH2-10 cutover next."

# 1c. Verify academics_db is empty (no traffic has reached it during burn-in).
./scripts/migrate-to-academics.sh --dry-run
# Should report "Target academics_db has 0 total rows before migration."
```

If any pre-flight fails, **abort**.

## 2. Pause writes

The goal: stop all writes to the four old DBs so the data we're about to copy is the final state.

```bash
# Option A (simplest): bring down the four old service containers.
docker compose stop school-service student-service attendance-service assessment-service

# Option B (less disruptive — gateway returns 503 but services stay up):
# scale gateway to 0, copy data, flip routes, scale gateway back. Skip if
# you're confident in Option A.
```

The gateway is still routed at the four old containers (per PH2-9 state). Any client requests during this window get connection errors. That's the cost of the cutover; keep it short.

## 3. Migrate data

```bash
# 3a. Run the one-time data migration. Idempotency is NOT guaranteed —
# the dest must be empty, OR you pass --truncate-first (destructive).
./scripts/migrate-to-academics.sh

# Expected output (per source DB):
#   Migrating school_db (8 tables) → academics_db
#     school_db → academics_db: done
#   Migrating student_db (4 tables) → academics_db
#     ... etc
#   ✓ Row counts match. Migration complete.

# 3b. Spot-check parity.
psql ... -d academics_db -c "SELECT count(*) FROM schools"
psql ... -d school_db    -c "SELECT count(*) FROM schools"
# These must be equal.
```

If row counts don't match, **abort**: bring the four old services back up, do not flip the gateway, investigate the warning the migration script printed.

## 4. Flip the gateway

The gateway routing config is already updated in `services/api-gateway/app/routes.py` (PH2-10 change in `SERVICE_ROUTES`). It only takes effect on the next gateway start.

```bash
# Restart the gateway so it picks up the routes change.
docker compose restart api-gateway

# Verify new routing is in effect.
curl -fs http://gateway:8000/system/status | jq '.services'
# Expected: contains "academics" entry; "school-service", "student-service",
# "attendance-service", "assessment-service" no longer appear as separate
# downstream services (they consolidated into "academics").

# Verify a real route resolves.
curl -fs -H "Authorization: Bearer <admin-token>" \
     http://gateway:8000/api/v1/schools | jq '.data | length'
```

## 5. Smoke test

Hit one read endpoint per academic domain and confirm 200 with real data.

```bash
TOKEN="<admin-jwt>"
H="Authorization: Bearer ${TOKEN}"

curl -fs -H "$H" http://gateway:8000/api/v1/schools         # was school-service
curl -fs -H "$H" http://gateway:8000/api/v1/classes         # was school-service
curl -fs -H "$H" http://gateway:8000/api/v1/subjects        # was school-service
curl -fs -H "$H" http://gateway:8000/api/v1/students        # was student-service
curl -fs -H "$H" http://gateway:8000/api/v1/enrollments     # was student-service
curl -fs -H "$H" "http://gateway:8000/api/v1/attendance/daily?date=2026-05-26"   # was attendance-service
curl -fs -H "$H" http://gateway:8000/api/v1/assessments?class_id=...&term_id=...  # was assessment-service
curl -fs -H "$H" http://gateway:8000/api/v1/provinces       # NEW — was orphaned at gateway
```

Each must return 200. If any returns 5xx, **rollback** (see §6).

## 6. Rollback (if needed)

The cutover is reversible by gateway routing only. The data on academics_db is harmless if not used.

```bash
# 6a. Revert SERVICE_ROUTES in services/api-gateway/app/routes.py (git revert
#     the PH2-10 commit, OR set the four URL env vars in compose to point
#     back at the old containers).

# 6b. Restart the four old service containers.
docker compose start school-service student-service attendance-service assessment-service

# 6c. Restart the gateway.
docker compose restart api-gateway

# 6d. Verify routing is back at the old shape.
curl -fs http://gateway:8000/system/status | jq '.services'

# 6e. The data we copied into academics_db is now stale. Either:
#     - Leave it (no traffic reaches academics, so it's inert), OR
#     - Truncate: psql ... -d academics_db -c "TRUNCATE TABLE ... CASCADE"
#       so the next cutover attempt is clean.
```

## 7. Post-cutover

Burn-in for 1 week with academics serving real traffic and the four old service containers still running but receiving no traffic. Watch:

- p95 latency on the academic-domain routes — should NOT regress (in-process authz should improve it).
- Error rate on the same routes — should not increase.
- Kafka consumer lag — should not increase.
- The four old services' connection counts — should drop to ~0 (only health-check polling).

After the burn-in:

- **PH2-11** rewrites reporting-service as a Kafka-only consumer.
- **PH2-12** deletes the four old service folders + their compose entries.

## What's NOT in this runbook (documented elsewhere)

- Backup procedure: `docs/runbooks/backup-restore.md`.
- Secret rotation: `docs/runbooks/secrets-rotation.md`.
- Observability dashboards: `docs/runbooks/observability.md`.

## References

- ADR 006 + addendum: `docs/decisions/006-addendum-module-call-graph.md`
- Backlog: `task.md` § Phase 2 — PH2-10 closure entry
- The 13 prefixes flipped: `services/api-gateway/app/routes.py` (search for "PH2-10 cutover")
