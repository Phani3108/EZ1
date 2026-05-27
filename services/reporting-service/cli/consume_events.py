"""CLI replacement for POST /api/v1/reports/consume (PH2-11).

Reads a JSON file of events and feeds them into ReportingService.consume_batch.

Usage:
    python -m cli.consume_events events.json
    python -m cli.consume_events events.json --dry-run

The input file must be either:
  * a JSON array of event envelopes, OR
  * NDJSON (one envelope per line)

Each envelope is the same shape the Kafka publishers produce — see
shared/eduzim_shared/kafka/producer.py:EduZimProducer.publish for the
expected fields (event_id, event_type, school_id, payload).

Exits non-zero on the first decoding error so CI / ops scripts can rely
on the return code.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterator


logger = logging.getLogger("cli.consume_events")


def _iter_events(path: Path) -> Iterator[dict]:
    """Yield events from either a JSON array or an NDJSON file."""
    text = path.read_text()
    text_stripped = text.lstrip()
    if text_stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"{path} top-level must be an array")
        yield from data
        return
    # NDJSON fallback
    for line_no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{line_no} — invalid JSON: {e}") from e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay events through the reporting projection.")
    parser.add_argument("path", help="Path to JSON array or NDJSON file of events")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse + validate but do NOT write to the DB")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Batch size for consume_batch calls (default 500)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    path = Path(args.path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return 2

    events = list(_iter_events(path))
    logger.info("Parsed %d events from %s", len(events), path)

    if args.dry_run:
        logger.info("Dry-run: skipping DB writes")
        return 0

    from app.database import SessionLocal
    from app.services.reporting_service import ReportingService

    total_processed = 0
    total_duplicates = 0
    total_errors = 0

    db = SessionLocal()
    try:
        svc = ReportingService(db)
        for i in range(0, len(events), args.batch_size):
            chunk = events[i: i + args.batch_size]
            result = svc.consume_batch(chunk)
            total_processed += result["processed"]
            total_duplicates += result["duplicates"]
            total_errors += result["errors"]
            logger.info(
                "  batch %d-%d  processed=%d  duplicates=%d  errors=%d",
                i, i + len(chunk), result["processed"], result["duplicates"], result["errors"],
            )
    finally:
        db.close()

    logger.info(
        "TOTAL  processed=%d  duplicates=%d  errors=%d",
        total_processed, total_duplicates, total_errors,
    )
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
