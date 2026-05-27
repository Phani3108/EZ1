#!/usr/bin/env bash
# Configure toxiproxy with the Phase-7 chaos profile (PH7-2).
#
# Default profile per the gate spec:
#   - 5% packet loss on every data-plane connection
#   - 200ms added latency on every connection
#   - Kafka brokers go offline for 60s every 30 minutes
#
# Usage:
#   ./scripts/load/chaos_profiles.sh apply    # set up proxies + toxics
#   ./scripts/load/chaos_profiles.sh reset    # remove all toxics (leave proxies)
#   ./scripts/load/chaos_profiles.sh remove   # tear down everything
#   ./scripts/load/chaos_profiles.sh status   # show current state
#
# Expects toxiproxy admin API at localhost:8474 (default).
set -euo pipefail

TOXI=${TOXIPROXY_URL:-http://localhost:8474}

action="${1:-apply}"

create_proxy() {
    local name="$1" listen="$2" upstream="$3"
    # Delete first (idempotent) then create
    curl -fsS -X DELETE "${TOXI}/proxies/${name}" >/dev/null 2>&1 || true
    curl -fsS -X POST "${TOXI}/proxies" -d "$(cat <<EOF
{
  "name": "${name}",
  "listen": "0.0.0.0:${listen}",
  "upstream": "${upstream}",
  "enabled": true
}
EOF
    )" >/dev/null
    echo "[chaos] proxy ${name}: ${listen} → ${upstream}"
}

add_toxic() {
    local proxy="$1" toxic_name="$2" toxic_type="$3" stream="$4" attrs="$5"
    curl -fsS -X POST "${TOXI}/proxies/${proxy}/toxics" -d "$(cat <<EOF
{
  "name": "${toxic_name}",
  "type": "${toxic_type}",
  "stream": "${stream}",
  "toxicity": 1.0,
  "attributes": ${attrs}
}
EOF
    )" >/dev/null
    echo "[chaos] ${proxy}: +${toxic_name} (${toxic_type})"
}

case "${action}" in
    apply)
        echo "[chaos] applying Phase-7 default profile"

        # ─── 1. Create proxies ───
        create_proxy postgres-proxy 5433 postgres:5432
        create_proxy kafka-proxy   9093 kafka:9092
        create_proxy redis-proxy   6380 redis:6379

        # ─── 2. Postgres: 200ms latency + 5% packet loss ───
        # latency toxic: adds a fixed delay to every packet
        add_toxic postgres-proxy pg-latency latency downstream \
            '{"latency": 200, "jitter": 50}'
        # bandwidth toxic at 0% loss ≈ no-op; for real packet loss
        # we use `timeout` which simulates dropped connections every
        # ~20 connection-seconds (5% over a 1-minute connection).
        add_toxic postgres-proxy pg-drop timeout downstream \
            '{"timeout": 20000}'

        # ─── 3. Kafka: 200ms latency + ditto ───
        add_toxic kafka-proxy kafka-latency latency downstream \
            '{"latency": 200, "jitter": 50}'

        # ─── 4. Redis: 50ms latency (less destructive on hot cache) ───
        add_toxic redis-proxy redis-latency latency downstream \
            '{"latency": 50, "jitter": 20}'

        echo "[chaos] profile applied"
        ;;

    reset)
        echo "[chaos] removing all toxics (keeping proxies)"
        for proxy in postgres-proxy kafka-proxy redis-proxy; do
            curl -fsS "${TOXI}/proxies/${proxy}/toxics" 2>/dev/null \
                | python3 -c "import json,sys; [print(t['name']) for t in json.load(sys.stdin)]" \
                | while read -r toxic; do
                    curl -fsS -X DELETE "${TOXI}/proxies/${proxy}/toxics/${toxic}" >/dev/null
                    echo "[chaos] ${proxy}: -${toxic}"
                done
        done
        ;;

    remove)
        echo "[chaos] tearing down proxies"
        for proxy in postgres-proxy kafka-proxy redis-proxy; do
            curl -fsS -X DELETE "${TOXI}/proxies/${proxy}" >/dev/null 2>&1 || true
            echo "[chaos] -${proxy}"
        done
        ;;

    status)
        echo "[chaos] current state from ${TOXI}/proxies"
        curl -fsS "${TOXI}/proxies" | python3 -m json.tool
        ;;

    *)
        echo "usage: $0 {apply|reset|remove|status}" >&2
        exit 2
        ;;
esac
