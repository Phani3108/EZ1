"""Second SQLAlchemy engine bound to the reporting projection DB.

PH2-11 — academics now serves /api/v1/reports/* (the read side). The writes
(consume Kafka events → projection rows) still happen inside the
reporting-service container, which now runs as a pure Kafka consumer with
no HTTP surface. Both sides share `reporting_db`:

  * reporting-service: read+write via its own SessionLocal (single owner of
                       projection schema).
  * academics:         read-only via THIS module's SessionLocal.

The connection is opened lazily (first request) so unit tests that never
exercise /reports/* don't need REPORTING_DATABASE_URL set.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


_engine: Engine | None = None
_ReportingSession: sessionmaker | None = None


def _init() -> None:
    """Open the reporting-db engine on first use. Idempotent."""
    global _engine, _ReportingSession
    if _engine is not None:
        return
    settings = get_settings()
    url = settings.REPORTING_DATABASE_URL
    # Same pool tuning as the primary academics_db engine (see PH4-1).
    _engine = create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    _ReportingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_reporting_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a read-only session on the reporting DB."""
    _init()
    assert _ReportingSession is not None  # for type-checkers
    s = _ReportingSession()
    try:
        yield s
    finally:
        s.close()


def get_reporting_engine() -> Engine:
    """Direct access to the engine (used by CLI tools and tests)."""
    _init()
    assert _engine is not None
    return _engine
