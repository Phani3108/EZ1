#!/usr/bin/env bash
# Run the Phase 5 HA gate's chaos tests in sequence.
#
# Each test takes 30-60s including recovery time, plus a 30s settle
# pause between to let the cluster re-stabilize.
#
# Exit code: 0 if every test passed; otherwise the count of failures.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS=(
    "kill-pg-primary.sh"
    "kill-kafka-broker.sh"
    "kill-redis-primary.sh"
    "sigterm-services.sh"
)

fail=0
results=()
for t in "${TESTS[@]}"; do
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  $t"
    echo "════════════════════════════════════════════════════════════════"
    if bash "${DIR}/${t}"; then
        results+=("PASS  $t")
    else
        results+=("FAIL  $t")
        fail=$((fail + 1))
    fi
    echo "[run-all] settling 30s before next test..."
    sleep 30
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  SUMMARY"
echo "════════════════════════════════════════════════════════════════"
for r in "${results[@]}"; do
    echo "  $r"
done
exit "$fail"
