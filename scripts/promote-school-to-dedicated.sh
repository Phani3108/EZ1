#!/usr/bin/env bash
# PH8-3 — promote a school from shared → dedicated tenancy.
#
# Usage:
#   ./scripts/promote-school-to-dedicated.sh \
#       --school-id <uuid> \
#       --target-db-url postgresql://eduzim:pw@host/school_xxx_db \
#       [--dry-run] [--no-lock]
#
# The seven steps below are documented in ADR 009 / docs/runbooks/
# tenancy-upgrade.md. Each step prints a marker so a partial failure
# is obvious in the log.
#
# Idempotent on RETRY: the script checks for existing data in the
# target DB and refuses to overwrite unless --truncate-first is passed.
# Idempotent on CANCEL: if step 6 (flip tier) fails, step 7 (soft-delete
# from shared) is NOT executed; the source rows stay intact and the
# operator can re-run.
#
# What this script does NOT do:
#   * Provision the target DB. It must already exist + be empty (or
#     pass --truncate-first).
#   * Wire the dedicated DB URL into EDUZIM_TENANCY_DEDICATED_REGISTRY.
#     That's a separate config-update + service-restart step documented
#     in the runbook.
set -euo pipefail

SCHOOL_ID=""
TARGET_DB_URL=""
SHARED_DB_URL="${SHARED_DB_URL:-postgresql://eduzim:eduzim_secret@postgres:5432/academics_db}"
DRY_RUN=0
NO_LOCK=0
TRUNCATE_FIRST=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --school-id) SCHOOL_ID="$2"; shift 2 ;;
        --target-db-url) TARGET_DB_URL="$2"; shift 2 ;;
        --shared-db-url) SHARED_DB_URL="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-lock) NO_LOCK=1; shift ;;
        --truncate-first) TRUNCATE_FIRST=1; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "$SCHOOL_ID" || -z "$TARGET_DB_URL" ]]; then
    echo "ERROR: --school-id and --target-db-url are required" >&2
    exit 2
fi

# Tables to move. Order matters for FK respect on restore (school first,
# then enrolment + parents, then attendance/marks which reference them).
TABLES=(
    schools
    academic_years
    terms
    classes
    subjects
    class_teacher_assignments
    students
    parents
    student_parents
    enrollments
    attendance_records
    assessments
    marks
    sync_batches
    processed_client_events
    idempotency_keys
)

log() { printf '\n[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

# ─── Step 0: sanity ──────────────────────────────────────────────
log "STEP 0 — sanity checks"
log "  source DB: ${SHARED_DB_URL}"
log "  target DB: ${TARGET_DB_URL}"
log "  school_id: ${SCHOOL_ID}"
log "  dry-run:   ${DRY_RUN}"

if ! command -v psql >/dev/null; then
    echo "ERROR: psql not found in PATH" >&2; exit 3
fi
if ! command -v pg_dump >/dev/null; then
    echo "ERROR: pg_dump not found in PATH" >&2; exit 3
fi

# Confirm school exists + is shared in source
existing_tier=$(psql "$SHARED_DB_URL" -At -c \
    "SELECT tenancy_tier FROM schools WHERE id = '${SCHOOL_ID}'")
if [[ -z "$existing_tier" ]]; then
    echo "ERROR: school_id ${SCHOOL_ID} not found in shared DB" >&2; exit 4
fi
if [[ "$existing_tier" != "shared" ]]; then
    echo "ERROR: school_id ${SCHOOL_ID} is currently tier=${existing_tier} " \
         "(expected shared). Aborting." >&2
    exit 4
fi
log "  source tier: ${existing_tier} ✓"

# Confirm target is empty (or --truncate-first)
target_has_rows=$(psql "$TARGET_DB_URL" -At -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" \
    || echo 0)
if [[ "$target_has_rows" -gt 0 && "$TRUNCATE_FIRST" -eq 0 ]]; then
    schools_count=$(psql "$TARGET_DB_URL" -At -c "SELECT count(*) FROM schools" 2>/dev/null || echo 0)
    if [[ "$schools_count" -gt 0 ]]; then
        echo "ERROR: target DB has data. Pass --truncate-first to clear it, or " \
             "use an empty target." >&2
        exit 4
    fi
fi

# ─── Step 1: lock the school (maintenance_mode = true) ───────────
if [[ $NO_LOCK -eq 0 && $DRY_RUN -eq 0 ]]; then
    log "STEP 1 — lock school (maintenance_mode = true)"
    psql "$SHARED_DB_URL" -c \
        "UPDATE schools SET maintenance_mode = true WHERE id = '${SCHOOL_ID}'"
fi

# ─── Step 2: snapshot the school's rows from shared ──────────────
log "STEP 2 — snapshot rows (pg_dump per table, filtered by school_id)"
SNAPSHOT_DIR="/tmp/eduzim-promote-${SCHOOL_ID}-$(date -u +%s)"
mkdir -p "$SNAPSHOT_DIR"
log "  snapshot dir: ${SNAPSHOT_DIR}"

for tbl in "${TABLES[@]}"; do
    if [[ "$tbl" == "schools" ]]; then
        filter="WHERE id = '${SCHOOL_ID}'"
    else
        filter="WHERE school_id = '${SCHOOL_ID}'"
    fi
    file="${SNAPSHOT_DIR}/${tbl}.csv"
    if [[ $DRY_RUN -eq 1 ]]; then
        log "  [dry-run] would dump ${tbl} ${filter} → ${file}"
        continue
    fi
    rows=$(psql "$SHARED_DB_URL" -At -c "SELECT count(*) FROM ${tbl} ${filter}" || echo 0)
    psql "$SHARED_DB_URL" \
        -c "\\COPY (SELECT * FROM ${tbl} ${filter}) TO '${file}' CSV HEADER"
    log "  ${tbl}: ${rows} rows → ${file}"
done

if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY-RUN complete. Re-run without --dry-run to execute."
    exit 0
fi

# ─── Step 3: restore into the dedicated DB ───────────────────────
log "STEP 3 — restore into dedicated DB"

# The dedicated DB needs the SAME schema. We use the academics
# migrations container for this. Operator should have run
#   alembic upgrade head
# against the dedicated DB beforehand (documented in the runbook).

if [[ $TRUNCATE_FIRST -eq 1 ]]; then
    log "  --truncate-first: clearing tables in target"
    # Truncate in reverse order to respect FKs
    for ((i=${#TABLES[@]}-1; i>=0; i--)); do
        psql "$TARGET_DB_URL" -c "TRUNCATE ${TABLES[$i]} CASCADE" || true
    done
fi

for tbl in "${TABLES[@]}"; do
    file="${SNAPSHOT_DIR}/${tbl}.csv"
    if [[ ! -f "$file" ]]; then continue; fi
    rows=$(($(wc -l < "$file") - 1))
    if [[ "$rows" -le 0 ]]; then
        log "  ${tbl}: empty, skipping"
        continue
    fi
    psql "$TARGET_DB_URL" -c "\\COPY ${tbl} FROM '${file}' CSV HEADER"
    log "  ${tbl}: ${rows} rows restored"
done

# ─── Step 4: row-count parity check ──────────────────────────────
log "STEP 4 — row-count parity check"
failed=0
for tbl in "${TABLES[@]}"; do
    if [[ "$tbl" == "schools" ]]; then
        filter="WHERE id = '${SCHOOL_ID}'"
    else
        filter="WHERE school_id = '${SCHOOL_ID}'"
    fi
    src=$(psql "$SHARED_DB_URL" -At -c "SELECT count(*) FROM ${tbl} ${filter}" || echo 0)
    dst=$(psql "$TARGET_DB_URL" -At -c "SELECT count(*) FROM ${tbl}" || echo 0)
    if [[ "$src" != "$dst" ]]; then
        log "  ${tbl}: SRC=${src}  DST=${dst}  ❌ MISMATCH"
        failed=$((failed + 1))
    else
        log "  ${tbl}: ${src} rows ✓"
    fi
done
if [[ $failed -gt 0 ]]; then
    log "PARITY CHECK FAILED. NOT flipping tier — school stays in maintenance."
    log "Investigate the mismatched tables above and re-run with --truncate-first."
    exit 5
fi

# ─── Step 5: flip the tier in the shared DB ──────────────────────
# At this point, the dedicated DB has a complete copy. We flip the
# tier flag on shared. Once flipped, the application routes traffic
# to the dedicated DB (after a config reload).
log "STEP 5 — flip tenancy_tier (shared → dedicated)"
psql "$SHARED_DB_URL" -c \
    "UPDATE schools SET tenancy_tier = 'dedicated', maintenance_mode = false " \
    "WHERE id = '${SCHOOL_ID}'"

# ─── Step 6: print follow-up config instructions ─────────────────
cat <<EOF

────────────────────────────────────────────────────────────────────
✅ Promotion data move complete.

Follow-up steps (NOT done by this script):

  1. Add to EDUZIM_TENANCY_DEDICATED_REGISTRY:
       "${SCHOOL_ID}": "${TARGET_DB_URL}"

  2. Restart academics + finance + communications + reporting-service.
     They re-read the registry on startup.

  3. Verify writes route to the new DB:
       curl -X POST .../api/v1/schools/${SCHOOL_ID}/test-write ...
       psql "${TARGET_DB_URL}" -c "SELECT count(*) FROM <some_table>"

  4. After 30 days of clean operation, archive the school's rows in
     the shared DB:
       UPDATE schools SET is_active=false WHERE id='${SCHOOL_ID}' AND ...
     (keep the row but mark inactive; full delete is a separate sweep)

Snapshot files retained at: ${SNAPSHOT_DIR}
(Manual cleanup once you've confirmed steady-state on the new DB.)
────────────────────────────────────────────────────────────────────
EOF
