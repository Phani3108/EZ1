"""Phase 17b — image thumbnail generation tests."""
from __future__ import annotations

import io
import os
import tempfile
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_thumb.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()


def _make_png_bytes(width: int = 800, height: int = 600, colour=(120, 200, 60)) -> bytes:
    """Build a real PNG that Pillow can decode."""
    from PIL import Image
    img = Image.new("RGB", (width, height), colour)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def tmp_storage():
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


def _headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


class TestThumbnailGenerator:
    def test_generates_thumb_for_png(self):
        from app.services.thumbnails import generate_thumbnail
        data = _make_png_bytes(800, 600)
        thumb = generate_thumbnail(data, "image/png")
        assert thumb is not None
        # Should be substantially smaller than the source.
        assert len(thumb) < len(data)
        # Decodes as JPEG.
        from PIL import Image
        thumb_img = Image.open(io.BytesIO(thumb))
        assert thumb_img.format == "JPEG"
        # Bounds preserved.
        assert thumb_img.width <= 256
        assert thumb_img.height <= 256
        # Aspect preserved (4:3 source).
        assert abs((thumb_img.width / thumb_img.height) - (800 / 600)) < 0.02

    def test_skip_non_image_mime(self):
        from app.services.thumbnails import generate_thumbnail
        assert generate_thumbnail(b"%PDF...", "application/pdf") is None

    def test_skip_gif(self):
        """Animated GIFs are deliberately skipped — flattening them
        loses meaning."""
        from app.services.thumbnails import generate_thumbnail
        # Even a static GIF is skipped by policy.
        assert generate_thumbnail(b"GIF89a...", "image/gif") is None

    def test_malformed_image_returns_none(self):
        from app.services.thumbnails import generate_thumbnail
        assert generate_thumbnail(b"not-an-image", "image/png") is None


class TestUploadGeneratesThumb:
    def _seed_announcement(self, SessionLocal):
        from app.models.communication import Announcement
        s = SessionLocal()
        try:
            a = Announcement(
                id=uuid.uuid4(), school_id=SCHOOL_A,
                title="Test", body="Test",
                audience_type="ALL",
                created_by=ADMIN_A,
            )
            s.add(a)
            s.commit()
            return a.id
        finally:
            s.close()

    def test_image_upload_sets_has_thumbnail(self, client, tmp_storage, engine_and_session):
        _, SL = engine_and_session
        ann_id = self._seed_announcement(SL)
        png_bytes = _make_png_bytes(640, 480)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("photo.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["has_thumbnail"] is True

    def test_pdf_upload_has_no_thumbnail(self, client, tmp_storage, engine_and_session):
        _, SL = engine_and_session
        ann_id = self._seed_announcement(SL)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4..."), "application/pdf")},
        )
        d = r.json()["data"]
        assert d["has_thumbnail"] is False

    def test_thumbnail_endpoint_returns_jpeg(self, client, tmp_storage, engine_and_session):
        _, SL = engine_and_session
        ann_id = self._seed_announcement(SL)
        png_bytes = _make_png_bytes(800, 600)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("photo.png", io.BytesIO(png_bytes), "image/png")},
        )
        att_id = r.json()["data"]["id"]
        thumb = client.get(
            f"/api/v1/comm/attachments/{att_id}/thumbnail",
            headers=_headers(),
        )
        assert thumb.status_code == 200, thumb.text
        assert thumb.headers["content-type"] == "image/jpeg"
        # Confirm it's actually a JPEG.
        from PIL import Image
        thumb_img = Image.open(io.BytesIO(thumb.content))
        assert thumb_img.format == "JPEG"

    def test_thumbnail_endpoint_404_for_non_image(self, client, tmp_storage, engine_and_session):
        _, SL = engine_and_session
        ann_id = self._seed_announcement(SL)
        r = client.post(
            "/api/v1/comm/attachments",
            headers=_headers(),
            data={"owner_kind": "announcement", "owner_id": str(ann_id)},
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4..."), "application/pdf")},
        )
        att_id = r.json()["data"]["id"]
        thumb = client.get(
            f"/api/v1/comm/attachments/{att_id}/thumbnail",
            headers=_headers(),
        )
        assert thumb.status_code == 404
        assert thumb.json()["error"]["code"] == "NO_THUMBNAIL"
