#!/usr/bin/env bash
# Chaos test: Kafka broker loss in a 3-broker KRaft cluster.
#
# Stops kafka-1. Existing consumers should keep receiving (the
# remaining brokers serve the partitions). We verify by watching the
# consumer-group offset for the reporting-service group; it should
# continue to advance during a 30s observation window.
#
# Exit codes: 0 = pass, 1 = fail, 2 = setup error.
set -uo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml"
OBSERVATION_WINDOW=30
GROUP=reporting-service

read_offsets() {
    # kafka-consumer-groups returns CURRENT-OFFSET column for the group.
    # Sum across partitions so we don't care which partition advanced.
    $COMPOSE exec -T kafka-0 kafka-consumer-groups \
        --bootstrap-server kafka-0:9092,kafka-2:9092 \
        --describe --group "$GROUP" 2>/dev/null \
        | awk 'NR>1 && $4 ~ /^[0-9]+$/ {sum+=$4} END {print sum+0}'
}

echo "[chaos:kafka] sanity — 3 brokers up?"
for b in kafka-0 kafka-1 kafka-2; do
    if ! $COMPOSE ps "$b" 2>/dev/null | grep -q "Up\|running"; then
        echo "[chaos:kafka] FAIL: $b not running at start; abort"
        exit 2
    fi
done

echo "[chaos:kafka] reading baseline offsets..."
sleep 5
before=$(read_offsets)
echo "[chaos:kafka] baseline offset sum: $before"

echo "[chaos:kafka] stopping kafka-1..."
$COMPOSE stop kafka-1

echo "[chaos:kafka] sleeping ${OBSERVATION_WINDOW}s during outage..."
sleep "$OBSERVATION_WINDOW"

after=$(read_offsets)
echo "[chaos:kafka] post-outage offset sum: $after"

echo "[chaos:kafka] restarting kafka-1..."
$COMPOSE start kafka-1

if [[ "$after" -gt "$before" ]]; then
    echo "[chaos:kafka] PASS — offsets advanced ${before} → ${after} during broker outage"
    exit 0
fi
echo "[chaos:kafka] FAIL — offsets did not advance during outage (${before} = ${after})"
echo "[chaos:kafka] note: this can ALSO mean there was no Kafka traffic during the window."
echo "[chaos:kafka] re-run with the seed script generating events:"
echo "[chaos:kafka]   docker compose exec academics python -m scripts.dev-seed &"
echo "[chaos:kafka]   ./scripts/chaos/kill-kafka-broker.sh"
exit 1
