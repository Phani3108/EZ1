# Phase 4 — Data hygiene rollout runbook

This runbook covers the four Phase-4 deliverables when they land in
staging / prod:

  1. **Q-006** cross-tenant isolation tests — already merged (academics 23 new tests).
  2. **Q-007** concurrency tests + BUG-010 CAS fix — already merged
     (finance 6 new tests, academics 5 new tests).
  3. **BUG-009** route-level `(_err(...), status)` tuple bug — already fixed;
     27 call sites converted to `JSONResponse(..., status_code=N)`.
  4. **INFRA-002** pgbouncer + **BUG-008** dedicated migrations container —
     scaffolded in compose; this runbook covers the operational rollout.

## What changed in the runtime topology

**Pre-Phase-4:**
```
client → gateway → service → postgres (direct, 5432)
                   ↑
                   service runs alembic on every cold start
```

**Post-Phase-4:**
```
client → gateway → service → pgbouncer (6432) → postgres (5432)
                                                  ↑
                                                  one-shot `migrations`
                                                  container runs alembic
                                                  for all 5 services then
                                                  exits cleanly
```

## Per-deploy actions

### 1. First-time staging deploy

```bash
# Pre-flight: secrets exist
test -n "$JWT_SECRET_KEY" || (echo "missing JWT_SECRET_KEY" && exit 1)
test -n "$INTERNAL_SERVICE_TOKEN" || (echo "missing INTERNAL_SERVICE_TOKEN" && exit 1)

# Build the new migrations image
docker compose -f docker-compose.prod.yml build migrations

# Start the data-plane (postgres + pgbouncer), wait for healthy
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml up -d pgbouncer
sleep 5
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U eduzim

# Run migrations container — should exit 0
docker compose -f docker-compose.prod.yml up migrations
docker compose -f docker-compose.prod.yml ps migrations    # state: exited(0)

# Start the rest of the stack
docker compose -f docker-compose.prod.yml up -d
```

### 2. Subsequent deploys (post-schema-change)

```bash
# Rebuild the migrations image (carries the new alembic revisions)
docker compose -f docker-compose.prod.yml build migrations

# Run it in isolation against the existing DB
docker compose -f docker-compose.prod.yml run --rm migrations

# Roll services with the new image tag
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### 3. Smoke tests post-deploy

```bash
# pgbouncer is accepting connections
docker compose -f docker-compose.prod.yml exec pgbouncer psql \
    "postgres://eduzim:$DB_PASSWORD@127.0.0.1:6432/pgbouncer" -c "SHOW STATS;"

# Migrations applied cleanly
docker compose -f docker-compose.prod.yml exec academics alembic current
docker compose -f docker-compose.prod.yml exec finance alembic current
docker compose -f docker-compose.prod.yml exec communications alembic current
docker compose -f docker-compose.prod.yml exec identity alembic current

# Sanity: gateway healthz still 200
curl -fsS https://api.eduzim.co.zw/healthz

# Sanity: a real read endpoint (auth token required)
curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" \
    https://api.eduzim.co.zw/api/v1/reports/dashboard | jq .data
```

## Rollback

### Rollback pgbouncer

If pgbouncer misbehaves, revert services to direct postgres connections:

```bash
# In docker-compose.prod.yml, change each service's DATABASE_URL from
# postgresql://...@pgbouncer:6432/... back to @postgres:5432/...
# Then:
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml stop pgbouncer
```

### Rollback the migrations container

If the migrations container fails on a deploy:

```bash
# Read the exit log to identify which service's migration failed
docker compose -f docker-compose.prod.yml logs migrations

# Manually run alembic for just that service against the existing DB:
docker compose -f docker-compose.prod.yml run --rm \
    -e DATABASE_URL="postgresql://eduzim:$DB_PASSWORD@postgres:5432/<dbname>" \
    --entrypoint "bash -c" migrations \
    "cd /migrations/services/<svc> && alembic upgrade head"
```

### Rollback Q-006 / Q-007 / BUG-009 (these are code-only)

`git revert` the respective commits. The bug fixes are defence-in-depth;
reverting BUG-009 restores the prior (broken) behavior where 404s
silently came back as 200s.

## Known caveats

* **pgbouncer transaction mode** is incompatible with prepared statements
  and session-level advisory locks. We don't use either. If a future
  feature does, switch that one query path back to a direct postgres
  connection (or move to session mode for the affected service).
* **The migrations container** does NOT run on every service restart —
  only when `docker compose up migrations` is invoked or the stack
  starts cold. If you change a model, you MUST rebuild + re-run it.
* **Q-006/Q-007 tests use SQLite + StaticPool**. They prove correctness
  on the application-layer invariants (per-tenant scoping, CAS
  predicates, idempotency dedup) but cannot exercise true row-level
  locking — that path is covered by Postgres at runtime via FOR UPDATE
  (BUG-010 CAS is defence-in-depth on top).
