FROM postgres:16-alpine

# INFRA-001: pg_dump backup container.
# Runs `pg_dump` on a configurable cron schedule against the EduZim
# postgres instance, writes timestamped .sql.gz files to /backups, and
# retains the most recent N (configurable, default 14).
#
# Restore procedure documented in docs/runbooks/backup-restore.md.

RUN apk add --no-cache bash curl ca-certificates tzdata

WORKDIR /app
COPY ./infra/backups/backup.sh /app/backup.sh
COPY ./infra/backups/restore.sh /app/restore.sh
COPY ./infra/backups/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/backup.sh /app/restore.sh /app/entrypoint.sh

ENV BACKUP_DIR=/backups \
    BACKUP_RETENTION=14 \
    BACKUP_SCHEDULE_SECONDS=86400

ENTRYPOINT ["/app/entrypoint.sh"]
