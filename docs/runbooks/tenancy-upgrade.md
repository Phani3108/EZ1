# Tenancy upgrade — promote a school from `shared` → `dedicated`

This runbook covers the **PH8-3** workflow: moving a single school's
data out of the cluster-wide `academics_db` into its own dedicated DB,
and switching the application's routing layer to use it.

Pre-Phase-8, every school's data lives row-level-scoped in the shared
`academics_db`. Per ADR 009 + DEC-009, large or sensitivity-sensitive
schools can be promoted to a dedicated DB. The shared library's
`eduzim_shared.tenancy.TenancyResolver` routes traffic accordingly.

## When to promote

A school becomes a candidate for `dedicated` when:

* **Volume**: >1,000 students or >100,000 attendance rows projected/year.
  Cluster-wide impact of one school's slow query becomes operationally
  expensive.
* **Sovereignty / contract**: the school's contract requires the data
  to live on an isolated DB (ZDPA-style requirement). Common for
  private schools.
* **Customer ask**: school explicitly requests isolation and pays the
  premium tier.

Schools that don't meet any of these stay on `shared` (default).

## What you need beforehand

* A provisioned, empty target Postgres DB. The script does NOT create
  it. Most common pattern: spin a new RDS / Patroni instance.
* `alembic upgrade head` already run against the target DB. Use the
  same migrations container as the cluster:
  ```bash
  DATABASE_URL=postgresql://eduzim:pw@new-host/school_xxx_db \
    docker compose -f docker-compose.prod.yml run --rm migrations
  ```
* The `EDUZIM_TENANCY_DEDICATED_REGISTRY` env var on every service
  must include the new school_id → DB URL mapping (after the
  promotion, not before — see steps below).
* `psql` + `pg_dump` available on the host running the script.

## The seven steps

The promotion is automated by `scripts/promote-school-to-dedicated.sh`.
What it does:

1. **Sanity** — verifies school exists in shared with tier=shared;
   confirms target DB is empty (or `--truncate-first`).
2. **Lock** — sets `schools.maintenance_mode = true`. Writes from
   this school are blocked. (Application-side enforcement is a Phase
   8.5 follow-up; currently the flag is informational.)
3. **Snapshot** — `\COPY` each table to a CSV in `/tmp/eduzim-promote-<id>/`,
   filtered by `school_id`.
4. **Restore** — `\COPY` the CSVs into the target DB.
5. **Parity check** — compares row counts source vs target per table.
   Aborts if any table mismatches.
6. **Flip the tier** — `UPDATE schools SET tenancy_tier='dedicated',
   maintenance_mode=false` in the shared DB.
7. **Operator follow-up** — the script prints the env-update + service
   restart steps; these are NOT automated to avoid silent surprises.

## Walk-through

```bash
# 1. Provision the target DB (your IaC / cloud console; out of scope here).
psql "postgresql://eduzim:pw@host/postgres" \
    -c "CREATE DATABASE school_xxx_db OWNER eduzim"

# 2. Run migrations against the new DB.
DATABASE_URL=postgresql://eduzim:pw@host/school_xxx_db \
    docker compose -f docker-compose.prod.yml run --rm migrations

# 3. Dry-run the promotion first.
./scripts/promote-school-to-dedicated.sh \
    --school-id 11111111-1111-1111-1111-111111111111 \
    --target-db-url postgresql://eduzim:pw@host/school_xxx_db \
    --dry-run

# 4. Real run.
./scripts/promote-school-to-dedicated.sh \
    --school-id 11111111-1111-1111-1111-111111111111 \
    --target-db-url postgresql://eduzim:pw@host/school_xxx_db

# 5. Update EDUZIM_TENANCY_DEDICATED_REGISTRY in your secrets manager:
#      {
#        "11111111-1111-1111-1111-111111111111": "postgresql://eduzim:pw@host/school_xxx_db",
#        ...
#      }

# 6. Restart the four downstream services to pick up the new env.
docker compose -f docker-compose.prod.yml restart \
    academics finance communications reporting-service

# 7. Verify writes route to the new DB.
TOKEN=<admin token for the promoted school>
curl -X PUT "https://api.eduzim.co.zw/api/v1/students/<sid>" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"first_name": "Updated"}'

# The update should appear in the dedicated DB, NOT in the shared:
psql "postgresql://eduzim:pw@host/school_xxx_db" \
    -c "SELECT first_name, updated_at FROM students WHERE id = '<sid>'"
# Expect: Updated, <fresh timestamp>

psql "postgresql://eduzim:pw@host/academics_db" \
    -c "SELECT first_name, updated_at FROM students WHERE id = '<sid>'"
# Expect: <old value> — the shared row is now stale (kept for 30d rollback).

# 8. After 30 days of clean operation, the school's rows in the
#    shared DB can be archived (kept but is_active=false) or
#    permanently deleted. Schedule this via the Phase 9 retention job.
```

## What can go wrong

**Step 5 parity mismatch.**
The script aborts WITHOUT flipping the tier. The school stays in
`maintenance_mode=true` (writes still blocked from the app's POV when
the app-side enforcement lands). Investigate the mismatched tables,
clear the target DB, and re-run.

**Step 6 flip succeeds but step 7 (env update) is forgotten.**
The app keeps routing to the shared DB because the registry doesn't
have the school yet. Writes go to the OLD DB, which is now stale.
**Mitigation**: the registry update step is documented as the next
action in the script's exit banner. Don't skip it.

**Service restart needed and operator forgets.**
Same outcome as above. Add a deploy gate that asserts every
production service's running config includes the new registry entry
before considering the rollout complete.

**A future write to the same school via the SHARED DB**
(say a Kafka consumer wired to the wrong env) creates an inconsistent
state — some rows in shared, some in dedicated. The application's
shared library should catch this by checking tenancy_tier on every
operation, but if your wiring drifts, it's a real risk. Audit log
(Q-016) catches the divergence at next reconcile.

## Rollback

Within the 30-day soft-archive window:

```bash
# Flip the tier back.
psql "postgresql://eduzim:pw@host/academics_db" \
    -c "UPDATE schools SET tenancy_tier='shared' WHERE id='<id>'"

# Remove the registry entry.
# Restart services.
docker compose -f docker-compose.prod.yml restart \
    academics finance communications reporting-service

# Optionally drop the dedicated DB.
psql "postgresql://eduzim:pw@host/postgres" -c "DROP DATABASE school_xxx_db"
```

The shared DB still has the original rows (we soft-archived them at
step 7, not deleted). Writes that happened in the dedicated window
are lost from the rollback's perspective — operator decides whether
to manually copy them back.

After 30 days: rollback requires a full data restore from backup.

## Costs

* One Postgres instance per dedicated school. Even a small AWS RDS
  is ~$30/mo. Budget accordingly.
* Slightly higher ops complexity: each dedicated DB needs its own
  backup, its own monitoring, its own credentials.
* The `EDUZIM_TENANCY_DEDICATED_REGISTRY` env var becomes operationally
  important — treat it as part of your secrets management workflow,
  with the same review + rotation cadence as JWT secrets.
