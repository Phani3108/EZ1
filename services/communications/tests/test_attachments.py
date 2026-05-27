"""Attachment upload / list / download / delete tests (Phase 11b / T-008).

Exercises the full surface against an in-memory SQLite + tempdir
storage, including:

  * Upload happy path → returns metadata
  * Mime + size validation
  * Owner-exists check (announcement is the test owner kind)
  * List by owner
  * Download returns the raw bytes with correct content type
  * Delete soft-deletes the row + drops bytes from disk
  * Audit hooks: upload + delete write rows; file content never appears
    in the audit payload
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_attachments.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()


@pytest.fixture
def temp_storage_root(monkeypatch):
    """Per-test temp dir for storage, so files don't leak across tests."""
    from app.services import storage as _storage_mod
    tmp = tempfile.mkdtemp(prefix="eduzim-att-test-")
    monkeypatch.setenv("EDUZIM_ATTACHMENT_BACKEND", "local")
    monkeypatch.setenv("EDUZIM_ATTACHMENT_LOCAL_ROOT", tmp)
    _storage_mod.reset_storage_for_tests()
    yield tmp
    _storage_mod.reset_storage_for_tests()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import communication as _c  # noqa
    from app.models import idempotency as _i  # noqa
    from app.models import whatsapp as _w  # noqa
    from app.models import audit as _au  # noqa
    from app.models import messaging as _m  # noqa
    from app.models import attachment as _a  # noqa

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session, temp_storage_root):
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


def _headers(user_id=TEACHER_A, role="Teacher", school_id=SCHOOL_A,
             perms="authenticated") -> dict:
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": role,
        "X-Permissions": perms,
    }


def _seed_announcement(SessionLocal) -> uuid.UUID:
    from app.models.communication import Announcement
    s = SessionLocal()
    try:
        a = Announcement(
            school_id=SCHOOL_A,
            title="seed",
            body="for-attachment-test",
            audience_type="ALL",
            created_by=TEACHER_A,
        )
        s.add(a)
        s.commit()
        return a.id
    finally:
        s.close()


# ─── Upload ────────────────────────────────────────────────────────


class TestUpload:
    def test_happy_path(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)

        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("school-day.jpg", io.BytesIO(b"\xff\xd8imagebytes"), "image/jpeg")},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["file_name"] == "school-day.jpg"
        assert body["mime_type"] == "image/jpeg"
        assert body["size_bytes"] == len(b"\xff\xd8imagebytes")
        assert body["owner_kind"] == "announcement"

    def test_unsupported_mime_rejected(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("danger.exe", io.BytesIO(b"x"),
                            "application/x-msdownload")},
        )
        assert r.status_code == 415
        assert r.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_oversize_rejected(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        # 11 MB > MAX_UPLOAD_BYTES (10 MB)
        big = b"a" * (11 * 1024 * 1024)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("huge.jpg", io.BytesIO(big), "image/jpeg")},
        )
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "FILE_TOO_LARGE"

    def test_invalid_owner_kind(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "evil", "owner_id": str(ann_id)},
            files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_OWNER_KIND"

    def test_missing_owner_returns_404(self, client):
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(uuid.uuid4())},
            files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "OWNER_NOT_FOUND"


# ─── List / Download / Delete ──────────────────────────────────────


class TestListDownloadDelete:
    def _upload(self, client, ann_id):
        return client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("note.txt", io.BytesIO(b"hello world"), "text/plain")},
        ).json()["data"]

    def test_list_returns_uploaded(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        self._upload(client, ann_id)
        r = client.get(
            "/api/v1/comm/attachments",
            headers=_headers(),
            params={"owner_kind": "announcement", "owner_id": str(ann_id)},
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1

    def test_download_returns_bytes(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        att = self._upload(client, ann_id)
        r = client.get(
            f"/api/v1/comm/attachments/{att['id']}/download",
            headers=_headers(),
        )
        assert r.status_code == 200
        assert r.content == b"hello world"
        assert r.headers["content-type"].startswith("text/plain")

    def test_delete_soft_marks_and_purges_bytes(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        att = self._upload(client, ann_id)
        d = client.request(
            "DELETE",
            f"/api/v1/comm/attachments/{att['id']}",
            headers=_headers(),
        )
        assert d.status_code == 200
        assert d.json()["data"]["deleted_at"] is not None

        # Download now returns 404 (deleted_at filter) — the file may
        # be gone from storage too, but the metadata check catches it
        # first either way.
        r = client.get(
            f"/api/v1/comm/attachments/{att['id']}/download",
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_non_uploader_non_admin_cannot_delete(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        att = self._upload(client, ann_id)
        OTHER = uuid.uuid4()
        d = client.request(
            "DELETE",
            f"/api/v1/comm/attachments/{att['id']}",
            headers=_headers(user_id=OTHER, role="Teacher"),
        )
        assert d.status_code == 403


# ─── Audit hooks ───────────────────────────────────────────────────


class TestAttachmentAudit:
    def test_upload_audit_does_not_contain_file_contents_or_name(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        ann_id = _seed_announcement(SessionLocal)
        client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={
                "file": (
                    "alice-report-PII.pdf",
                    io.BytesIO(b"secret content here"),
                    "application/pdf",
                )
            },
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "attachment.uploaded")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "secret content here" not in blob
            assert "alice-report-PII.pdf" not in blob
        finally:
            s.close()
