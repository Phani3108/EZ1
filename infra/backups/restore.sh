#!/usr/bin/env bash
# infra/backups/restore.sh — INFRA-001 restore companion
# Usage:
#   docker compose run --rm pg-backup /app/restore.sh <db_name> [timestamp]
#
# If timestamp is omitted, restores from the latest snapshot of <db_name>.
# Existing data in the target DB is wiped (pg_dump was made with --clean).
#
# DESTRUCTIVE. Tested as part of the Phase 4 verification.

set -euo pipefail

: "${POSTGRES_HOST:?POSTGRES_HOST not set}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER not set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}"
: "${BACKUP_DIR:=/backups}"

DB="${1:?usage: restore.sh <db_name> [YYYYMMDD-HHMMSS]}"
STAMP="${2:-}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

if [[ -z "${STAMP}" ]]; then
  SRC="$(ls -1t "${BACKUP_DIR}/${DB}_"*.sql.gz | head -n1 || true)"
  if [[ -z "${SRC}" ]]; then
    echo "No backups found for ${DB} in ${BACKUP_DIR}" >&2
    exit 1
  fi
else
  SRC="${BACKUP_DIR}/${DB}_${STAMP}.sql.gz"
  if [[ ! -f "${SRC}" ]]; then
    echo "Backup not found: ${SRC}" >&2
    exit 1
  fi
fi

echo "[$(date -u +%FT%TZ)] DESTRUCTIVE restore of ${DB} from ${SRC}"
gunzip -c "${SRC}" | psql \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${DB}" \
    -v ON_ERROR_STOP=1

echo "[$(date -u +%FT%TZ)] ✓ ${DB} restored from $(basename "${SRC}")"
