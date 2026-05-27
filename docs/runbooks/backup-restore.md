# Postgres Backup & Restore Runbook

> **Scope**: how the pg-backup container works, how to restore from a snapshot, how to verify backups are healthy.
> **Related**: INFRA-001 (Phase 4), ADR 005 (data residency — backups must follow the same rules).
> **Status**: dev workflow live as of 2026-05-26. Production wiring (S3-compatible offsite + automated restore drills) lands in Phase 5 / Phase 17.

---

## What runs today

A `pg-backup` container is part of `docker-compose.yml`. It calls
`pg_dump` against the EduZim Postgres instance every
`BACKUP_SCHEDULE_SECONDS` (default 24h) and writes timestamped, gzipped SQL
files to a named volume `pg_backups`. The most recent
`BACKUP_RETENTION` (default 14) snapshots per database are retained;
older ones are pruned.

Backed-up databases (default):

```
auth_db  school_db  student_db  attendance_db
fees_db  comms_db   reporting_db assessment_db
```

Override via the `BACKUP_DATABASES` env var (space-separated list).

## Files in `infra/backups/`

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the backup image (alpine + `pg_dump`) |
| `backup.sh` | One-shot snapshot of every configured DB |
| `restore.sh` | Restore a single DB from a snapshot |
| `entrypoint.sh` | Runs backup at start + every `BACKUP_SCHEDULE_SECONDS` |

## Common operations

### Force an immediate backup

```bash
docker compose exec pg-backup /app/backup.sh
```

### List existing snapshots

```bash
docker compose exec pg-backup ls -la /backups | head -30
```

### Restore a single database to the latest snapshot

```bash
docker compose exec pg-backup /app/restore.sh auth_db
```

### Restore to a specific point in time

```bash
docker compose exec pg-backup /app/restore.sh auth_db 20260526-091500
```

The timestamp is the suffix used in the filename
(`auth_db_20260526-091500.sql.gz`).

### Copy a snapshot off the container (for local inspection or transfer)

```bash
docker compose cp pg-backup:/backups/auth_db_20260526-091500.sql.gz ./
```

### Tail the backup loop

```bash
docker compose logs -f pg-backup
```

## Verifying a backup is restorable (RECOMMENDED before any production roll-out)

```bash
# 1. Snapshot now
docker compose exec pg-backup /app/backup.sh

# 2. Pick a low-stakes table to spot-check, e.g. the audit log
docker compose exec postgres psql -U eduzim -d auth_db -c \
    "SELECT count(*) FROM login_audit;"

# 3. Restore (DESTRUCTIVE — overwrites current state of auth_db)
docker compose exec pg-backup /app/restore.sh auth_db

# 4. Verify the row count is identical
docker compose exec postgres psql -U eduzim -d auth_db -c \
    "SELECT count(*) FROM login_audit;"
```

Production should run this verification on staging (not prod!) at least
quarterly.

## What's deliberately NOT here yet

These come in later phases:

- **Off-host storage** (S3 / Backblaze / Wasabi). Currently the volume
  lives on the docker host's disk; a host failure loses the backups too.
  Phase 5 wires this with `aws s3 sync` or `rclone`.
- **Encryption at rest**. The `.sql.gz` files are unencrypted on the volume.
  Phase 9 (privacy / compliance) is where we add per-file encryption with a
  rotated key.
- **Cross-region replication**. Per ADR 005, backups should already live in
  a Zimbabwean cloud provider when compute moves there.
- **Automated restore drills**. The restore script is tested ad-hoc; a
  scheduled drill (restore to a throwaway DB, run a row-count check, fire
  an alert if it fails) lands in Phase 17.

## RTO / RPO targets

These are aspirational pending the Phase 5 HA work:

| Tier | RTO | RPO |
|---|---|---|
| Dev | best-effort | 24h |
| Pilot | < 4h | < 6h |
| National rollout | < 1h | < 15 min |

The current setup gets you to "Dev" only.

## Open items (tracked in `task.md`)

- **INFRA-001** — backup container (closed by this runbook + the compose addition).
- **Phase 5** — Postgres HA + off-host backup target.
- **Phase 9** — backup encryption at rest.
- **Phase 17** — automated restore drills in CI.
