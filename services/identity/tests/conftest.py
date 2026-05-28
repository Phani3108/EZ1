"""Shared test fixtures — Phase 20c. See academics/tests/conftest.py."""
from __future__ import annotations

import os

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_identity_default.db")
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
    import app.models  # noqa: F401

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
