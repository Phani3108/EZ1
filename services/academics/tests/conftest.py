"""Shared test fixtures — Phase 20c.

Every test file in `services/academics/tests/` used to redefine
identical copies of these two fixtures (~30 lines each × ~38 files).
Pytest's fixture-resolution rule prefers the closest definition, so
existing per-file fixtures continue to take precedence — this conftest
is purely additive for new tests + lets us delete the duplicates one
file at a time without coordinated changes.

Required env vars
-----------------

* `DATABASE_URL`        — placeholder for the app's settings loader.
                          Tests overwrite this with an in-memory SQLite.
* `KAFKA_ENABLED=false` — keeps the academics service from trying to
                          publish to a non-existent Kafka cluster
                          during request handling.
* `INTERNAL_SERVICE_TOKEN` + `JWT_SECRET_KEY` — required by config
                          load even though tests don't decode JWTs
                          (the gateway is the sole verifier; the
                          service trusts headers).

Fixtures
--------

* `engine_and_session` — fresh in-memory SQLite engine + sessionmaker
                         per test. Tables created from `Base.metadata`
                         after importing `app.models` so every model
                         class is registered.
* `client`             — FastAPI TestClient with `get_db` overridden
                         to use the in-memory engine. `raise_server_exceptions=False`
                         so handler 500s surface as response bodies
                         that tests can assert on.

What we deliberately DON'T put here
-----------------------------------

* Auth header helpers (`_admin_headers`, `_ops_headers`, …) — they
  vary too much per test file (different school_ids, different role
  combos). Keeping them per-file makes tests self-documenting.
* Test data seeders — same reason. A `_seed_subject` helper used in
  one file would be confusing context for another.
"""
from __future__ import annotations

import os

import pytest


# Defaults must be set BEFORE importing app.* (config loads at import time).
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_default.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault(
    "INTERNAL_SERVICE_TOKEN",
    "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION",
)


@pytest.fixture
def engine_and_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    import app.models  # noqa: F401 — register every model class

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    _, SessionLocal = engine_and_session

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
