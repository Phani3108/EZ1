#!/usr/bin/env bash
# Chaos test: Postgres primary failover via repmgr.
#
# Stops pg-0; expects repmgr to promote pg-1 and pgpool to start routing
# writes to it within 60s. Verifies by issuing a write through pgbouncer
# and timing the success.
#
# Exit codes: 0 = pass, 1 = fail, 2 = setup error.
set -uo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml"
TIMEOUT_SECS=60
SLEEP_BETWEEN_PROBES=2

echo "[chaos:pg] sanity — pg-0 healthy + primary?"
if ! $COMPOSE exec -T pg-0 pg_isready -U "${DB_USER:-eduzim}" >/dev/null 2>&1; then
    echo "[chaos:pg] FAIL: pg-0 is not healthy at start; abort"
    exit 2
fi

echo "[chaos:pg] stopping pg-0..."
$COMPOSE stop pg-0
killed_at=$(date +%s)

# Probe pgbouncer with a write every SLEEP_BETWEEN_PROBES seconds.
# Success = the write committed (rows=1 or the SELECT after returns the new row).
deadline=$((killed_at + TIMEOUT_SECS))
attempt=0
while [[ $(date +%s) -lt $deadline ]]; do
    attempt=$((attempt + 1))
    # The chaos_marker table is created on the fly so this script doesn't
    # need a pre-existing schema. Use auth_db since it's the smallest.
    out=$($COMPOSE exec -T pgbouncer psql \
        "postgres://${DB_USER:-eduzim}:${DB_PASSWORD}@127.0.0.1:6432/auth_db" \
        -At -c "CREATE TABLE IF NOT EXISTS chaos_marker(ts timestamptz default now()); \
                INSERT INTO chaos_marker DEFAULT VALUES; \
                SELECT count(*) FROM chaos_marker;" 2>&1)
    rc=$?
    if [[ $rc -eq 0 ]]; then
        elapsed=$(( $(date +%s) - killed_at ))
        echo "[chaos:pg] PASS — write succeeded ${elapsed}s after kill (attempt $attempt)"
        echo "[chaos:pg] sample output: $out"
        echo "[chaos:pg] restarting pg-0..."
        $COMPOSE start pg-0
        exit 0
    fi
    echo "[chaos:pg] attempt $attempt failed (rc=$rc); retrying in ${SLEEP_BETWEEN_PROBES}s..."
    sleep "$SLEEP_BETWEEN_PROBES"
done

elapsed=$(( $(date +%s) - killed_at ))
echo "[chaos:pg] FAIL — no successful write in ${elapsed}s (target ${TIMEOUT_SECS}s)"
echo "[chaos:pg] last error: $out"
echo "[chaos:pg] restarting pg-0 anyway..."
$COMPOSE start pg-0
exit 1
