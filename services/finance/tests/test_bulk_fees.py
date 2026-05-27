"""Phase 15a — Bulk fee-structure import tests."""
from __future__ import annotations

import io
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_finance_bulk_fees.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
AY_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import fees as _f  # noqa
    from app.models import audit as _au  # noqa

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session):
    _, SessionLocal = engine_and_session
    from app.database import get_db
    from app.main import app

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _admin_headers(school_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,fees:write",
    }


def _csv(rows: list[dict]) -> bytes:
    import csv
    out = io.StringIO()
    if not rows:
        return b""
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode("utf-8")


class TestBulkFees:
    def test_happy_path_creates_structure_and_items(self, client, engine_and_session):
        csv_bytes = _csv([
            {"structure_name": "Term 1 Tuition",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Tuition", "amount": "1500.00", "currency": "USD"},
            {"structure_name": "Term 1 Tuition",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Books", "amount": "200.00", "currency": "USD"},
        ])
        r = client.post(
            "/api/v1/bulk/fee-structures",
            headers=_admin_headers(),
            files={"file": ("fees.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["structures_created"] == 1
        assert data["items_written"] == 2

        # Verify rows.
        from app.models.fees import FeeStructure, FeeItem
        _, SL = engine_and_session
        s = SL()
        try:
            fs = s.query(FeeStructure).filter(
                FeeStructure.school_id == SCHOOL_A).first()
            assert fs is not None
            assert fs.name == "Term 1 Tuition"
            items = s.query(FeeItem).filter(
                FeeItem.fee_structure_id == fs.id).all()
            assert len(items) == 2
            labels = sorted(i.label for i in items)
            assert labels == ["Books", "Tuition"]
        finally:
            s.close()

    def test_dry_run_does_not_persist(self, client, engine_and_session):
        csv_bytes = _csv([
            {"structure_name": "Dry Run",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "X", "amount": "100", "currency": "USD"},
        ])
        r = client.post(
            "/api/v1/bulk/fee-structures?dry_run=true",
            headers=_admin_headers(),
            files={"file": ("fees.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["structures_created"] == 1
        # No rows in DB.
        from app.models.fees import FeeStructure
        _, SL = engine_and_session
        s = SL()
        try:
            assert s.query(FeeStructure).count() == 0
        finally:
            s.close()

    def test_idempotent_replace_items(self, client, engine_and_session):
        csv_bytes = _csv([
            {"structure_name": "Term 2",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Tuition", "amount": "1000", "currency": "USD"},
        ])
        client.post("/api/v1/bulk/fee-structures",
                    headers=_admin_headers(),
                    files={"file": ("fees.csv", csv_bytes, "text/csv")})
        # Re-import with different amount → structure updated, items replaced.
        csv_bytes2 = _csv([
            {"structure_name": "Term 2",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Tuition", "amount": "1100", "currency": "USD"},
            {"structure_name": "Term 2",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Activities", "amount": "50", "currency": "USD"},
        ])
        r = client.post("/api/v1/bulk/fee-structures",
                        headers=_admin_headers(),
                        files={"file": ("fees.csv", csv_bytes2, "text/csv")})
        d = r.json()["data"]
        assert d["structures_created"] == 0
        assert d["structures_updated"] == 1
        assert d["items_written"] == 2

    def test_invalid_amount_skipped(self, client):
        csv_bytes = _csv([
            {"structure_name": "Bad",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "X", "amount": "not-a-number", "currency": "USD"},
        ])
        r = client.post("/api/v1/bulk/fee-structures",
                        headers=_admin_headers(),
                        files={"file": ("fees.csv", csv_bytes, "text/csv")})
        d = r.json()["data"]
        assert d["structures_created"] == 0
        assert d["skipped"] == 1
        assert len(d["errors"]) >= 1

    def test_tenant_isolation(self, client, engine_and_session):
        """Two admins from different schools import — rows land in
        their own school only."""
        csv_a = _csv([
            {"structure_name": "Tenant A Fees",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Tuition", "amount": "1000", "currency": "USD"},
        ])
        csv_b = _csv([
            {"structure_name": "Tenant B Fees",
             "academic_year_id": str(AY_A), "term_id": "",
             "label": "Tuition", "amount": "2000", "currency": "USD"},
        ])
        client.post("/api/v1/bulk/fee-structures",
                    headers=_admin_headers(),
                    files={"file": ("a.csv", csv_a, "text/csv")})
        client.post("/api/v1/bulk/fee-structures",
                    headers=_admin_headers(school_id=SCHOOL_B),
                    files={"file": ("b.csv", csv_b, "text/csv")})

        from app.models.fees import FeeStructure
        _, SL = engine_and_session
        s = SL()
        try:
            a_rows = s.query(FeeStructure).filter(
                FeeStructure.school_id == SCHOOL_A).all()
            b_rows = s.query(FeeStructure).filter(
                FeeStructure.school_id == SCHOOL_B).all()
            assert len(a_rows) == 1
            assert len(b_rows) == 1
            assert a_rows[0].name == "Tenant A Fees"
            assert b_rows[0].name == "Tenant B Fees"
        finally:
            s.close()
