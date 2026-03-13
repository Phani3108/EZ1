#!/bin/bash
# EduZim — PostgreSQL Backup Script
# Usage: ./scripts/backup-db.sh
# Cron: 0 2 * * * /path/to/eduzim/scripts/backup-db.sh >> /var/log/eduzim-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_USER="${DB_USER:-eduzim}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

DATABASES=(
  auth_db
  school_db
  student_db
  attendance_db
  fees_db
  comms_db
  reporting_db
  assessment_db
)

mkdir -p "$BACKUP_DIR"

echo "═══════════════════════════════════════════"
echo "EduZim Database Backup — $TIMESTAMP"
echo "═══════════════════════════════════════════"

for db in "${DATABASES[@]}"; do
  BACKUP_FILE="$BACKUP_DIR/${db}_${TIMESTAMP}.sql.gz"
  echo -n "  Backing up $db... "

  if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" \
    --no-owner --no-privileges --clean --if-exists 2>/dev/null | gzip > "$BACKUP_FILE"; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ $SIZE"
  else
    echo "❌ FAILED"
    rm -f "$BACKUP_FILE"
  fi
done

# Cleanup old backups
echo ""
echo "Cleaning backups older than $RETENTION_DAYS days..."
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
echo "  Removed $DELETED old backup(s)"

echo ""
echo "✅ Backup complete. Files in: $BACKUP_DIR"
echo "═══════════════════════════════════════════"
