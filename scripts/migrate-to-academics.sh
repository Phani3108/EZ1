#!/usr/bin/env bash
# scripts/migrate-to-academics.sh — PH2-10 one-time data migration
#
# Copies all rows from the four pre-consolidation databases (school_db,
# student_db, attendance_db, assessment_db) into the consolidated
# academics_db. After PH2-10's gateway cutover, academics serves all 13
# academic-domain prefixes; this script populates academics_db with the
# existing data so the cutover is non-disruptive.
#
# Safety
# ------
# - Idempotent NOT guaranteed. By default the script refuses to run if
#   academics_db is non-empty. Use --truncate-first to wipe and re-load
#   (DESTRUCTIVE — only safe during the cutover window before any traffic
#   has reached academics).
# - Source DBs are NOT modified. A rollback is: flip gateway routes back.
# - Always run against a backup first. See docs/runbooks/backup-restore.md.
#
# Usage
# -----
#   ./scripts/migrate-to-academics.sh             # safe: fails if dest non-empty
#   ./scripts/migrate-to-academics.sh --dry-run   # show what would copy, no writes
#   ./scripts/migrate-to-academics.sh --truncate-first   # wipe dest, then copy
#
# Env
# ---
#   POSTGRES_HOST     (default: postgres)
#   POSTGRES_PORT     (default: 5432)
#   POSTGRES_USER     (default: eduzim)
#   POSTGRES_PASSWORD (REQUIRED)
#   TARGET_DB         (default: academics_db)

set -euo pipefail

DRY_RUN=false
TRUNCATE_FIRST=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)         DRY_RUN=true ;;
    --truncate-first)  TRUNCATE_FIRST=true ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=eduzim}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}"
: "${TARGET_DB:=academics_db}"

export PGPASSWORD="${POSTGRES_PASSWORD}"
PG_ARGS=(-h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}")

# Source DBs and tables, in dependency order so FK chains import cleanly.
declare -a SRC_DB_school_db=(provinces districts schools academic_years terms classes subjects class_teacher_assignments)
declare -a SRC_DB_student_db=(students parents student_parents enrollments)
declare -a SRC_DB_attendance_db=(sync_batches processed_client_events attendance_records)
declare -a SRC_DB_assessment_db=(assessments marks idempotency_keys)

DBS=(school_db student_db attendance_db assessment_db)
ALL_TABLES_REVERSED=(
  idempotency_keys marks assessments
  attendance_records processed_client_events sync_batches
  enrollments student_parents parents students
  class_teacher_assignments subjects classes terms academic_years schools districts provinces
)

log() { echo "[$(date -u +%FT%TZ)] $*"; }

count_target_rows() {
  local total=0
  for tbl in "${ALL_TABLES_REVERSED[@]}"; do
    n=$(psql "${PG_ARGS[@]}" -d "${TARGET_DB}" -tAc \
      "SELECT count(*) FROM ${tbl}" 2>/dev/null || echo 0)
    total=$((total + n))
  done
  echo "${total}"
}

# ── Pre-flight: dest must exist ──
if ! psql "${PG_ARGS[@]}" -d "${TARGET_DB}" -c "SELECT 1" >/dev/null 2>&1; then
  echo "ERROR: target database ${TARGET_DB} does not exist or is unreachable." >&2
  exit 1
fi

# ── Pre-flight: dest emptiness check ──
TARGET_ROWS_BEFORE="$(count_target_rows)"
log "Target ${TARGET_DB} has ${TARGET_ROWS_BEFORE} total rows before migration."

if [[ "${TARGET_ROWS_BEFORE}" != "0" && "${TRUNCATE_FIRST}" != "true" ]]; then
  echo "ERROR: ${TARGET_DB} is non-empty. Re-run with --truncate-first" >&2
  echo "  if you really want to wipe and reload (DESTRUCTIVE)." >&2
  exit 1
fi

if $TRUNCATE_FIRST && ! $DRY_RUN; then
  log "TRUNCATE CASCADE every academic table in ${TARGET_DB}..."
  psql "${PG_ARGS[@]}" -d "${TARGET_DB}" <<SQL
TRUNCATE TABLE ${ALL_TABLES_REVERSED[*]} RESTART IDENTITY CASCADE;
SQL
fi

# ── Per-DB migration ──
for db in "${DBS[@]}"; do
  tables_var="SRC_DB_${db}[@]"
  tables=("${!tables_var}")
  log "Migrating ${db} (${#tables[@]} tables) → ${TARGET_DB}"
  table_args=()
  for t in "${tables[@]}"; do
    table_args+=("--table=${t}")
  done

  if $DRY_RUN; then
    for t in "${tables[@]}"; do
      n=$(psql "${PG_ARGS[@]}" -d "${db}" -tAc "SELECT count(*) FROM ${t}" 2>/dev/null || echo 0)
      log "  ${db}.${t}: ${n} rows (would copy)"
    done
    continue
  fi

  pg_dump "${PG_ARGS[@]}" \
      --data-only --no-owner --no-privileges \
      "${table_args[@]}" "${db}" \
    | psql "${PG_ARGS[@]}" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 >/dev/null
  log "  ${db} → ${TARGET_DB}: done"
done

if $DRY_RUN; then
  log "Dry-run complete. No writes performed."
  exit 0
fi

# ── Post-flight: row count parity ──
TARGET_ROWS_AFTER="$(count_target_rows)"
SRC_ROWS=0
for db in "${DBS[@]}"; do
  tables_var="SRC_DB_${db}[@]"
  for t in "${!tables_var}"; do
    n=$(psql "${PG_ARGS[@]}" -d "${db}" -tAc "SELECT count(*) FROM ${t}" 2>/dev/null || echo 0)
    SRC_ROWS=$((SRC_ROWS + n))
  done
done

log "Source total rows: ${SRC_ROWS}"
log "Target total rows after migration: ${TARGET_ROWS_AFTER}"

if [[ "${SRC_ROWS}" != "${TARGET_ROWS_AFTER}" ]]; then
  echo "WARN: row counts differ — source=${SRC_ROWS}, target=${TARGET_ROWS_AFTER}" >&2
  echo "      Inspect manually. Common cause: legitimate duplicates filtered by" >&2
  echo "      PK/unique constraints (e.g., processed_client_events with the same" >&2
  echo "      (school_id, device_id, client_event_id) across servers)." >&2
  exit 2
fi

log "✓ Row counts match. Migration complete."
log "Next: flip the gateway routes (already configured in routes.py for PH2-10)"
log "and verify with: docs/runbooks/ph2-10-cutover.md"
