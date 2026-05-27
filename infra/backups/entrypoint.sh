#!/usr/bin/env bash
# infra/backups/entrypoint.sh — INFRA-001 long-running entrypoint
# Runs an initial backup at start, then sleeps for BACKUP_SCHEDULE_SECONDS
# between runs. A real production deployment swaps this for a cron-driven
# Kubernetes CronJob or AWS EventBridge schedule — for compose this loop is
# simpler than installing supercronic.

set -euo pipefail

: "${BACKUP_SCHEDULE_SECONDS:=86400}"

echo "EduZim backup container starting (interval=${BACKUP_SCHEDULE_SECONDS}s)"

# Run once immediately so the first snapshot is fresh.
/app/backup.sh || {
  echo "Initial backup failed; sleeping ${BACKUP_SCHEDULE_SECONDS}s before retry" >&2
}

while true; do
  sleep "${BACKUP_SCHEDULE_SECONDS}"
  /app/backup.sh || echo "Scheduled backup failed; will retry next interval" >&2
done
