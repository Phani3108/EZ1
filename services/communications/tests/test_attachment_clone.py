"""Phase 17a — attachment clone + bulk-clone tests."""
from __future__ import annotations

import io
import json as _json
import os
import tempfile
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_clone.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def tmp_storage():
    """Per-test temp dir for LocalDiskStorage."""
    with tempfile.TemporaryDirectory() as d:
        old = os.environ.get("EDUZIM_ATTACHMENT_LOCAL_ROOT")
        os.environ["EDUZIM_ATTACHMENT_LOCAL_ROOT"] = d
        from app.services.storage import reset_storage_for_tests
        reset_storage_for_tests()
        yield d
        if old is None:
            os.environ.pop("EDUZIM_ATTACHMENT_LOCAL_ROOT", None)
        else:
            os.environ["EDUZIM_ATTACHMENT_LOCAL_ROOT"] = old
        reset_storage_for_tests()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import (  # noqa
        communication, audit, messaging, attachment,
        notification_config, invite_outbox, whatsapp,
    )
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


def _headers(school_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,comm:write",
    }


def _seed_attachment_on_template(client, template_id: uuid.UUID,
                                 mime="application/pdf",
                                 body=b"%PDF-1.4\nfake content") -> str:
    r = client.post(
        "/api/v1/comm/attachments",
        headers=_headers(),
        data={"owner_kind": "homework_template",
              "owner_id": str(template_id)},
        files={"file": ("worksheet.pdf", io.BytesIO(body), mime)},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


class TestCloneSingle:
    def test_clone_single_attachment(self, client, tmp_storage):
        template_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        src_id = _seed_attachment_on_template(client, template_id)

        r = client.post(
            "/api/v1/comm/attachments/clone",
            headers=_headers(),
            json={
                "source_attachment_id": src_id,
                "new_owner_kind": "homework",
                "new_owner_id": str(new_owner_id),
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["owner_kind"] == "homework"
        assert d["owner_id"] == str(new_owner_id)
        # New row, distinct ID.
        assert d["id"] != src_id
        # Same file metadata.
        assert d["file_name"] == "worksheet.pdf"
        assert d["mime_type"] == "application/pdf"

    def test_clone_preserves_bytes(self, client, tmp_storage, engine_and_session):
        template_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        src_id = _seed_attachment_on_template(
            client, template_id, body=b"%PDF-CONTENT-VERIFY-42")

        r = client.post(
            "/api/v1/comm/attachments/clone",
            headers=_headers(),
            json={
                "source_attachment_id": src_id,
                "new_owner_kind": "homework",
                "new_owner_id": str(new_owner_id),
            },
        )
        new_id = r.json()["data"]["id"]

        # Download both via the existing download endpoint + verify
        # the bytes are identical.
        src = client.get(f"/api/v1/comm/attachments/{src_id}/download",
                         headers=_headers())
        new = client.get(f"/api/v1/comm/attachments/{new_id}/download",
                         headers=_headers())
        assert src.status_code == 200
        assert new.status_code == 200
        assert src.content == new.content
        assert b"PDF-CONTENT-VERIFY-42" in new.content

    def test_clone_rejects_unknown_owner_kind(self, client, tmp_storage):
        template_id = uuid.uuid4()
        src_id = _seed_attachment_on_template(client, template_id)
        r = client.post(
            "/api/v1/comm/attachments/clone",
            headers=_headers(),
            json={
                "source_attachment_id": src_id,
                "new_owner_kind": "evil_kind",
                "new_owner_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_OWNER_KIND"

    def test_clone_tenant_isolation(self, client, tmp_storage):
        """A clone request from school B referencing school A's
        attachment must fail."""
        template_id = uuid.uuid4()
        src_id = _seed_attachment_on_template(client, template_id)
        r = client.post(
            "/api/v1/comm/attachments/clone",
            headers=_headers(school_id=SCHOOL_B),
            json={
                "source_attachment_id": src_id,
                "new_owner_kind": "homework",
                "new_owner_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "ATTACHMENT_NOT_FOUND"


class TestCloneBulk:
    def test_bulk_clone_three_attachments(self, client, tmp_storage):
        template_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        for i in range(3):
            _seed_attachment_on_template(
                client, template_id, body=f"file-{i}".encode())

        r = client.post(
            "/api/v1/comm/attachments/clone-bulk",
            headers=_headers(),
            json={
                "source_owner_kind": "homework_template",
                "source_owner_id": str(template_id),
                "new_owner_kind": "homework",
                "new_owner_id": str(new_owner_id),
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["cloned_count"] == 3
        assert d["source_attachment_count"] == 3
        assert len(d["cloned_attachment_ids"]) == 3

    def test_bulk_clone_zero_when_no_source_attachments(self, client, tmp_storage):
        r = client.post(
            "/api/v1/comm/attachments/clone-bulk",
            headers=_headers(),
            json={
                "source_owner_kind": "homework_template",
                "source_owner_id": str(uuid.uuid4()),
                "new_owner_kind": "homework",
                "new_owner_id": str(uuid.uuid4()),
            },
        )
        d = r.json()["data"]
        assert d["cloned_count"] == 0


class TestAuditNoFilename:
    def test_clone_audit_omits_filename(self, client, tmp_storage, engine_and_session):
        _, SessionLocal = engine_and_session
        template_id = uuid.uuid4()
        # Upload with a PII-shaped filename.
        client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "homework_template",
                  "owner_id": str(template_id)},
            files={"file": ("alice-PII-secret-name.pdf",
                            io.BytesIO(b"%PDF..."),
                            "application/pdf")},
        )
        src_id = client.get(
            f"/api/v1/comm/attachments?owner_kind=homework_template"
            f"&owner_id={template_id}",
            headers=_headers(),
        ).json()["data"][0]["id"]

        client.post(
            "/api/v1/comm/attachments/clone",
            headers=_headers(),
            json={
                "source_attachment_id": src_id,
                "new_owner_kind": "homework",
                "new_owner_id": str(uuid.uuid4()),
            },
        )

        from app.models.audit import AuditLog
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "attachment.cloned")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details or "{}"})
            # Filename NOT in details.
            assert "alice-PII-secret-name" not in blob
            # MIME + size ARE OK.
            assert "application/pdf" in blob
        finally:
            s.close()
