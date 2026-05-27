"""CLI replacement for POST /api/v1/reports/rebuild (PH2-11).

Clears all projection rows and the processed-events inbox, then replays
the supplied event file from scratch. Use this when a projection model
changes shape, when projection data has drifted, or as part of disaster
recovery from a known-good event archive.

Usage:
    python -m cli.rebuild_projections events.json
    python -m cli.rebuild_projections events.json --confirm

Without --confirm, the script PREVIEWS what it would do (counts events,
shows DB target) and exits without writing. This makes accidental "I
ran the wrong command" foot-guns harder.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


logger = logging.getLogger("cli.rebuild_projections")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="REBUILD the reporting projection from an event log. "
                    "DESTRUCTIVE — wipes all projection rows first."
    )
    parser.add_argument("path", help="Path to JSON array or NDJSON file of events")
    parser.add_argument("--confirm", action="store_true",
                        help="Required to actually wipe + rebuild. Without this the "
                             "script previews and exits.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from cli.consume_events import _iter_events  # share the parser

    path = Path(args.path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return 2

    events = list(_iter_events(path))

    from app.config import get_settings
    settings = get_settings()
    logger.info("REBUILD PLAN")
    logger.info("  events file:  %s", path)
    logger.info("  event count:  %d", len(events))
    logger.info("  target DB:    %s", settings.DATABASE_URL)
    logger.info("")

    if not args.confirm:
        logger.warning("Preview only. Pass --confirm to actually rebuild.")
        return 0

    from app.database import SessionLocal
    from app.services.reporting_service import ReportingService

    db = SessionLocal()
    try:
        svc = ReportingService(db)
        logger.info("Wiping projections + inbox, replaying %d events…", len(events))
        result = svc.rebuild(events)
        logger.info(
            "DONE  processed=%d  duplicates=%d  errors=%d",
            result["processed"], result["duplicates"], result["errors"],
        )
        return 0 if result["errors"] == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
