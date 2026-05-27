#!/usr/bin/env python3
"""Audit-log retention purge (Phase 9 / INFRA-018).

Deletes `audit_log` rows older than the retention window from one or
more service databases. Default window matches the policy in
`docs/compliance/retention-policy.md` — 2 years.

Usage:
    # Dry-run against academics DB
    python scripts/audit-log-retention.py \\
        --db-url postgresql://eduzim:pw@host/academics_db \\
        --dry-run

    # Real purge across all four databases
    python scripts/audit-log-retention.py \\
        --db-url postgresql://eduzim:pw@host/academics_db \\
        --db-url postgresql://eduzim:pw@host/fees_db \\
        --db-url postgresql://eduzim:pw@host/comms_db \\
        --db-url postgresql://eduzim:pw@host/auth_db \\
        --retention-days 730

Intended scheduling: a daily cron job inside the migrations container
(it already has Postgres client + alembic + service code on PYTHONPATH).
For Phase 9 scaffolding the cron line is documented in the runbook;
operators wire it into their scheduler of choice (Kubernetes CronJob,
GitHub Actions schedule, plain crond).

Safety:
  * Counts rows BEFORE deleting (preview line).
  * Hard cap on per-invocation deletes: 1_000_000 rows. Past that the
    operator should investigate why a single run wants to delete that
    much — typically only happens on the first run after a long
    period of no purges.
  * Batched DELETE (5,000 rows per statement) so a runaway purge doesn't
    lock the table.
  * `--dry-run` reports counts without writing.

Exit codes:
  0 — completed successfully.
  2 — argument / setup error.
  3 — exceeded the safety cap; aborted.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional


logger = logging.getLogger("audit-retention")


SAFETY_CAP_PER_RUN = 1_000_000
BATCH_SIZE = 5_000


def _purge_one_db(
    db_url: str,
    *,
    cutoff: datetime,
    dry_run: bool,
    safety_cap: int = SAFETY_CAP_PER_RUN,
) -> dict:
    """Purge audit rows older than `cutoff` from a single DB.

    Returns a dict {db: <url>, eligible: int, deleted: int, skipped_capped: bool}.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    redacted_url = _redact(db_url)
    result: dict = {
        "db": redacted_url, "eligible": 0, "deleted": 0,
        "skipped_capped": False, "skipped_no_table": False,
    }

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            try:
                row = conn.execute(text(
                    "SELECT count(*) FROM audit_log WHERE occurred_at < :cutoff"
                ), {"cutoff": cutoff}).first()
                eligible = int(row[0]) if row else 0
            except (OperationalError, ProgrammingError) as e:
                # Table doesn't exist — that's fine for services that
                # haven't yet added the audit_log table.
                logger.warning("audit-retention skip %s: %s", redacted_url, e)
                result["skipped_no_table"] = True
                return result

            result["eligible"] = eligible

            if eligible > safety_cap:
                logger.error(
                    "audit-retention SAFETY-CAP exceeded for %s: %d > %d. "
                    "Aborting without deleting. Re-run with a tighter cutoff "
                    "to whittle the backlog down in chunks.",
                    redacted_url, eligible, safety_cap,
                )
                result["skipped_capped"] = True
                return result

            if dry_run or eligible == 0:
                logger.info(
                    "audit-retention %s: %d row(s) eligible (dry-run=%s)",
                    redacted_url, eligible, dry_run,
                )
                return result

            deleted = 0
            while True:
                # Postgres + SQLite both support this LIMIT-in-subquery
                # pattern; explicit transaction per batch so a midway
                # abort releases locks promptly.
                with conn.begin():
                    r = conn.execute(text(
                        """
                        DELETE FROM audit_log
                        WHERE id IN (
                          SELECT id FROM audit_log
                          WHERE occurred_at < :cutoff
                          LIMIT :batch
                        )
                        """
                    ), {"cutoff": cutoff, "batch": BATCH_SIZE})
                batch_deleted = r.rowcount or 0
                deleted += batch_deleted
                logger.info(
                    "audit-retention %s: batch deleted %d (total %d / %d)",
                    redacted_url, batch_deleted, deleted, eligible,
                )
                if batch_deleted < BATCH_SIZE:
                    break
                if deleted >= safety_cap:
                    logger.warning(
                        "audit-retention %s: hit safety cap mid-run; stopping",
                        redacted_url,
                    )
                    break

            result["deleted"] = deleted
            logger.info(
                "audit-retention %s: %d row(s) deleted (eligible %d)",
                redacted_url, deleted, eligible,
            )
    finally:
        engine.dispose()

    return result


def _redact(url: str) -> str:
    """Hide credentials in a DB URL for log lines."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://{rest}"
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://{creds}@{host}"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Purge audit_log rows older than the retention window.",
    )
    parser.add_argument(
        "--db-url", action="append", required=True,
        help="One or more Postgres URLs to purge. Repeat the flag for "
             "each service DB.",
    )
    parser.add_argument(
        "--retention-days", type=int, default=730,
        help="Keep rows from the last N days. Default 730 (2 years, "
             "per docs/compliance/retention-policy.md).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Count eligible rows but don't delete.",
    )
    parser.add_argument(
        "--safety-cap", type=int, default=SAFETY_CAP_PER_RUN,
        help="Refuse to delete more than this many rows in one invocation. "
             "Default 1,000,000. Past this, investigate before raising.",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.retention_days < 1:
        logger.error("--retention-days must be ≥ 1 (got %d)", args.retention_days)
        return 2

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.retention_days)
    logger.info(
        "audit-retention: cutoff=%s retention_days=%d dry_run=%s",
        cutoff.isoformat(), args.retention_days, args.dry_run,
    )

    overall_rc = 0
    for db_url in args.db_url:
        result = _purge_one_db(
            db_url,
            cutoff=cutoff,
            dry_run=args.dry_run,
            safety_cap=args.safety_cap,
        )
        if result["skipped_capped"]:
            overall_rc = 3

    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
