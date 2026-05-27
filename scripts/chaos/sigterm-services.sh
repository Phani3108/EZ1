#!/usr/bin/env bash
# Chaos test: graceful SIGTERM shutdown for each app service.
#
# The shared `app_factory.create_app()` registers a lifespan (INFRA-022)
# that drains in-flight requests + flushes the Kafka producer on SIGTERM.
# We send the signal and confirm the "Service X shutdown complete" log
# line appears within 5s.
#
# Exit codes: 0 = pass, 1 = at least one service failed to drain.
set -uo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml"
SERVICES=(identity academics finance communications reporting-service api-gateway)
DEADLINE_SECS=5

fail=0
for svc in "${SERVICES[@]}"; do
    echo ""
    echo "[chaos:sigterm] testing ${svc}..."
    cid=$($COMPOSE ps -q "${svc}")
    if [[ -z "$cid" ]]; then
        echo "[chaos:sigterm] ${svc}: container not running; skip"
        continue
    fi

    start=$(date +%s)
    docker kill --signal=SIGTERM "$cid" >/dev/null

    # Watch the container's exit. `docker wait` blocks until exit code
    # is available. We bound it with timeout.
    if timeout "${DEADLINE_SECS}s" docker wait "$cid" >/dev/null; then
        elapsed=$(( $(date +%s) - start ))
        # Check the logs for the shutdown-complete line.
        if docker logs "$cid" 2>&1 | grep -q "shutdown complete"; then
            echo "[chaos:sigterm] ${svc}: PASS (drained in ${elapsed}s)"
        else
            echo "[chaos:sigterm] ${svc}: PARTIAL — exited cleanly but no 'shutdown complete' log line"
            fail=$((fail + 1))
        fi
    else
        echo "[chaos:sigterm] ${svc}: FAIL — did not exit within ${DEADLINE_SECS}s"
        fail=$((fail + 1))
        docker kill "$cid" >/dev/null 2>&1 || true
    fi

    # Bring it back up.
    $COMPOSE up -d "${svc}" >/dev/null
done

echo ""
if [[ $fail -eq 0 ]]; then
    echo "[chaos:sigterm] ALL PASS"
    exit 0
fi
echo "[chaos:sigterm] ${fail} service(s) failed graceful shutdown"
exit 1
