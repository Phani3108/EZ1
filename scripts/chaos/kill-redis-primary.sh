#!/usr/bin/env bash
# Chaos test: Redis primary failover via Sentinel quorum.
#
# Stops redis-master. The 3-sentinel cluster (quorum 2) should detect
# the loss within REDIS_SENTINEL_DOWN_AFTER_MILLISECONDS (5s) and
# promote redis-replica to primary. The gateway's rate-limit client
# uses sentinel discovery (eduzim_shared.redis_client) — it should
# transparently switch.
#
# Verification: a request to the gateway that exercises Redis (any
# login attempt triggers the per-IP rate-limit increment) succeeds
# within 15s of the master kill.
#
# Exit codes: 0 = pass, 1 = fail, 2 = setup error.
set -uo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
TIMEOUT_SECS=15
SLEEP_BETWEEN_PROBES=1

echo "[chaos:redis] sanity — redis-master + sentinels healthy?"
if ! $COMPOSE exec -T redis-master redis-cli -a "${REDIS_PASSWORD:-}" PING >/dev/null 2>&1; then
    echo "[chaos:redis] FAIL: redis-master not responsive; abort"
    exit 2
fi

echo "[chaos:redis] stopping redis-master..."
$COMPOSE stop redis-master
killed_at=$(date +%s)

deadline=$((killed_at + TIMEOUT_SECS))
attempt=0
while [[ $(date +%s) -lt $deadline ]]; do
    attempt=$((attempt + 1))
    # The login endpoint always touches Redis (per-IP rate-limit
    # increment). We don't care about the auth outcome — only that the
    # gateway returns SOMETHING (not 502 / 503 from a Redis timeout).
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${GATEWAY_URL}/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"chaos@x","password":"x"}' \
        --max-time 5)
    # 400-level → reached the gateway and the auth/identity service
    # processed (and rejected) the request. 502/503 → Redis dead, fail.
    if [[ "$status" =~ ^[24] ]]; then
        elapsed=$(( $(date +%s) - killed_at ))
        echo "[chaos:redis] PASS — gateway responsive ${elapsed}s after master kill (status=$status, attempt=$attempt)"
        echo "[chaos:redis] restarting redis-master..."
        $COMPOSE start redis-master
        exit 0
    fi
    echo "[chaos:redis] attempt $attempt got HTTP $status — retrying in ${SLEEP_BETWEEN_PROBES}s..."
    sleep "$SLEEP_BETWEEN_PROBES"
done

elapsed=$(( $(date +%s) - killed_at ))
echo "[chaos:redis] FAIL — gateway did not recover in ${elapsed}s"
echo "[chaos:redis] restarting redis-master anyway..."
$COMPOSE start redis-master
exit 1
