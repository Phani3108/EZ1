#!/usr/bin/env bash
# BUG-008 / Phase 4 — run alembic upgrade head for every service.
#
# Each service has its own alembic tree + its own database. We loop
# through them, set DATABASE_URL appropriately, and run `alembic upgrade
# head` from the service's directory.
#
# Exit code:
#   0 — all services migrated cleanly.
#   N — at least one failed; N is the worst exit code observed.
#
# The script is intentionally serial. Postgres handles concurrent
# migrations fine, but serial is easier to read in logs and we don't
# have hundreds of services. Total runtime in prod is dominated by the
# Postgres connect, not the migrations themselves.
set -uo pipefail

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:?DB_USER missing}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD missing}"

# (service-dir, db-name) pairs. db-name matches docker-compose's
# POSTGRES_MULTIPLE_DATABASES list.
declare -a SERVICES=(
    "identity:auth_db"
    "academics:academics_db"
    "finance:fees_db"
    "communications:comms_db"
    "reporting-service:reporting_db"
)

# Wait for Postgres to accept connections (compose's healthcheck should
# already gate this, but defence-in-depth on cold cluster starts).
echo "[migrations] waiting for postgres at ${DB_HOST}:${DB_PORT}..."
for i in {1..60}; do
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
        echo "[migrations] postgres ready"
        break
    fi
    sleep 1
done
if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
    echo "[migrations] ERROR: postgres still not ready after 60s; bailing"
    exit 2
fi

WORST_RC=0
for pair in "${SERVICES[@]}"; do
    svc="${pair%%:*}"
    dbname="${pair##*:}"
    dir="/migrations/services/${svc}"

    if [[ ! -d "${dir}" ]]; then
        echo "[migrations] skip ${svc} — directory not found"
        continue
    fi
    if [[ ! -f "${dir}/alembic.ini" ]]; then
        echo "[migrations] skip ${svc} — no alembic.ini"
        continue
    fi

    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${dbname}"
    echo ""
    echo "================================================================"
    echo "[migrations] ${svc} → ${dbname}"
    echo "================================================================"

    (
        cd "${dir}" && \
        # Stub required env vars so the service's app.config loads at
        # alembic env.py import time without forcing the operator to
        # set them in the migrations container env.
        JWT_SECRET_KEY="${JWT_SECRET_KEY:-migrations-stub-secret-key-32-chars-min-padding}" \
        INTERNAL_SERVICE_TOKEN="${INTERNAL_SERVICE_TOKEN:-migrations-stub-internal-token}" \
        alembic upgrade head
    )
    rc=$?
    if [[ $rc -ne 0 ]]; then
        echo "[migrations] ${svc} FAILED (rc=${rc})"
        if [[ $rc -gt $WORST_RC ]]; then
            WORST_RC=$rc
        fi
    else
        echo "[migrations] ${svc} OK"
    fi
done

echo ""
echo "[migrations] all done. worst rc = ${WORST_RC}"
exit "${WORST_RC}"
