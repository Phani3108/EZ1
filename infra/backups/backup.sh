#!/usr/bin/env bash
# infra/backups/backup.sh — INFRA-001 (Phase 4)
# Dumps every EduZim database to a timestamped .sql.gz file. Retains the
# most recent $BACKUP_RETENTION snapshots; older ones are pruned.

set -euo pipefail

: "${POSTGRES_HOST:?POSTGRES_HOST not set}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER not set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}"
: "${BACKUP_DIR:=/backups}"
: "${BACKUP_RETENTION:=14}"

DATABASES="${BACKUP_DATABASES:-auth_db school_db student_db attendance_db fees_db comms_db reporting_db assessment_db}"

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

export PGPASSWORD="${POSTGRES_PASSWORD}"

for db in ${DATABASES}; do
  OUT="${BACKUP_DIR}/${db}_${STAMP}.sql.gz"
  echo "[$(date -u +%FT%TZ)] Backing up ${db} → ${OUT}"
  if pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        --no-owner --no-privileges --clean --if-exists \
        "${db}" | gzip -9 > "${OUT}"; then
    echo "[$(date -u +%FT%TZ)]   ✓ ${db} OK ($(du -h "${OUT}" | cut -f1))"
  else
    echo "[$(date -u +%FT%TZ)]   ✗ ${db} FAILED"
    rm -f "${OUT}"
    exit 1
  fi
done

# Retention prune (oldest first). Operate per-DB so a fast-growing DB
# doesn't push out the snapshots of a slow-changing one.
for db in ${DATABASES}; do
  ls -1t "${BACKUP_DIR}/${db}_"*.sql.gz 2>/dev/null \
    | tail -n +$((BACKUP_RETENTION + 1)) \
    | xargs -r rm -v
done

# Mark the most recent set so it's trivial to find.
ln -sf "${STAMP}" "${BACKUP_DIR}/LATEST"
echo "[$(date -u +%FT%TZ)] Backup run complete (retention=${BACKUP_RETENTION})"
