"""Phase 17d — curriculum versioning + upgrade-subject tests."""
from __future__ import annotations

import json as _json
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_versioning.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
OPS = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    import app.models  # noqa
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


def _admin_headers():
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


def _ops_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(OPS),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "EduZimOps",
        "X-Permissions": "school:create",
    }


def _seed_and_publish_national(client):
    nat = client.post(
        "/api/v1/ministry/national-curriculum/subjects",
        headers=_ops_headers(),
        json={"code": "ZIM-V-MATH", "name": "Form 1 Maths"},
    ).json()["data"]
    u1 = client.post(
        "/api/v1/ministry/national-curriculum/units",
        headers=_ops_headers(),
        json={"national_subject_id": nat["id"], "name": "Numbers", "code": "U-NUM",
              "sequence_order": 1, "grade_level": "Form 1"},
    ).json()["data"]
    client.post(
        "/api/v1/ministry/national-curriculum/topics",
        headers=_ops_headers(),
        json={"national_unit_id": u1["id"], "name": "Integers", "code": "T-INT",
              "sequence_order": 1, "learning_outcomes": "v1 outcomes."},
    )
    client.post(
        f"/api/v1/ministry/national-curriculum/subjects/{nat['id']}/publish",
        headers=_ops_headers(),
    )
    return nat["id"], u1["id"]


class TestVersionedAdopt:
    def test_initial_adopt_records_version_1(self, client):
        nat_id, _ = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        ).json()["data"]
        local_id = r["subject"]["id"]
        # List shows version 1, not stale.
        l = client.get("/api/v1/curriculum/subjects",
                       headers=_admin_headers()).json()["data"]
        match = next(s for s in l if s["id"] == local_id)
        assert match["adopted_national_version"] == 1
        assert match["national_current_version"] == 1
        assert match["is_stale"] is False


class TestRepublishMakesStale:
    def test_adopt_then_republish_marks_stale(self, client):
        nat_id, u1 = _seed_and_publish_national(client)
        # School A adopts at v1.
        client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        # Ministry adds a new topic + republishes → v2.
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Fractions", "code": "T-FRAC",
                  "sequence_order": 2, "learning_outcomes": "Add fractions."},
        )
        rp = client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        assert rp.json()["data"]["to_version"] == 2
        # School now sees `is_stale: true`.
        l = client.get("/api/v1/curriculum/subjects",
                       headers=_admin_headers()).json()["data"]
        local = l[0]
        assert local["adopted_national_version"] == 1
        assert local["national_current_version"] == 2
        assert local["is_stale"] is True


class TestUpgrade:
    def test_upgrade_pulls_new_topic_and_clears_stale(self, client, engine_and_session):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        # Adopt at v1.
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]
        # Ministry adds + republishes.
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Fractions", "code": "T-FRAC",
                  "sequence_order": 2, "learning_outcomes": "v2 fractions."},
        )
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        # Upgrade.
        up = client.post(
            "/api/v1/curriculum/upgrade-subject",
            headers=_admin_headers(),
            json={"school_subject_id": local_id},
        )
        assert up.status_code == 200, up.text
        d = up.json()["data"]
        assert d["from_version"] == 1
        assert d["to_version"] == 2
        assert d["topics_added"] == 1
        assert d["no_op"] is False
        # Stale indicator cleared.
        l = client.get("/api/v1/curriculum/subjects",
                       headers=_admin_headers()).json()["data"]
        local = next(s for s in l if s["id"] == local_id)
        assert local["adopted_national_version"] == 2
        assert local["is_stale"] is False
        # Tree now contains the new topic.
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        topic_codes = {
            t["code"]
            for u in tree["units"]
            for t in u["topics"]
        }
        assert "T-INT" in topic_codes
        assert "T-FRAC" in topic_codes

    def test_upgrade_is_noop_when_already_current(self, client):
        nat_id, _ = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]
        up = client.post(
            "/api/v1/curriculum/upgrade-subject",
            headers=_admin_headers(),
            json={"school_subject_id": local_id},
        )
        d = up.json()["data"]
        assert d["no_op"] is True
        assert d["topics_added"] == 0
        assert d["units_added"] == 0

    def test_upgrade_preserves_custom_topics(self, client, engine_and_session):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]

        # Find the local unit clone.
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        local_unit_id = tree["units"][0]["id"]

        # Add a custom topic under that local unit (NOT tied to any
        # NationalTopic).
        client.post(
            "/api/v1/curriculum/topics",
            headers=_admin_headers(),
            json={"unit_id": local_unit_id, "name": "School Custom",
                  "code": "T-CUSTOM", "sequence_order": 99,
                  "learning_outcomes": "School-specific topic."},
        )

        # Ministry republishes.
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        # Upgrade — the custom topic survives.
        client.post(
            "/api/v1/curriculum/upgrade-subject",
            headers=_admin_headers(),
            json={"school_subject_id": local_id},
        )
        tree2 = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        codes = {t["code"] for u in tree2["units"] for t in u["topics"]}
        assert "T-CUSTOM" in codes

    def test_upgrade_rejects_non_adopted(self, client):
        # Create a custom (non-national) subject.
        s = client.post(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(),
            json={"name": "Custom", "code": "CUST"},
        ).json()["data"]
        up = client.post(
            "/api/v1/curriculum/upgrade-subject",
            headers=_admin_headers(),
            json={"school_subject_id": s["id"]},
        )
        assert up.status_code == 400
        assert up.json()["error"]["code"] == "SUBJECT_NOT_ADOPTED"


class TestUpgradePreview:
    """Phase 18a — `GET /curriculum/upgrade-subject/preview` returns the
    diff WITHOUT mutating, so the HoD can review before clicking
    upgrade."""

    def test_preview_returns_pending_changes_for_stale_subject(
        self, client, engine_and_session
    ):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Fractions",
                  "code": "T-FRAC", "sequence_order": 2,
                  "learning_outcomes": "Add fractions."},
        )
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )

        preview = client.get(
            f"/api/v1/curriculum/upgrade-subject/preview?school_subject_id={local_id}",
            headers=_admin_headers(),
        )
        assert preview.status_code == 200, preview.text
        d = preview.json()["data"]
        assert d["no_op"] is False
        assert d["from_version"] == 1
        assert d["to_version"] == 2
        assert len(d["topics_to_add"]) == 1
        assert d["topics_to_add"][0]["code"] == "T-FRAC"
        assert d["topics_to_add"][0]["name"] == "Fractions"
        assert d["units_to_add"] == []
        assert d["topics_to_update"] == []

        # Tree is UNCHANGED after preview — proves no mutation.
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        codes = {t["code"] for u in tree["units"] for t in u["topics"]}
        assert "T-FRAC" not in codes

    def test_preview_no_op_when_already_current(self, client):
        nat_id, _ = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]
        preview = client.get(
            f"/api/v1/curriculum/upgrade-subject/preview?school_subject_id={local_id}",
            headers=_admin_headers(),
        )
        d = preview.json()["data"]
        assert d["no_op"] is True
        assert d["topics_to_add"] == []
        assert d["units_to_add"] == []

    def test_preview_reports_custom_topics_preserved_count(
        self, client, engine_and_session
    ):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        r = client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = r.json()["data"]["subject"]["id"]
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        local_unit_id = tree["units"][0]["id"]
        client.post(
            "/api/v1/curriculum/topics",
            headers=_admin_headers(),
            json={"unit_id": local_unit_id, "name": "Custom",
                  "code": "T-LOCAL", "sequence_order": 99},
        )
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Decimals",
                  "code": "T-DEC", "sequence_order": 3},
        )
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        preview = client.get(
            f"/api/v1/curriculum/upgrade-subject/preview?school_subject_id={local_id}",
            headers=_admin_headers(),
        ).json()["data"]
        assert preview["local_custom_topics_preserved_count"] == 1

    def test_preview_rejects_non_adopted(self, client):
        s = client.post(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(),
            json={"name": "Custom", "code": "CUST"},
        ).json()["data"]
        preview = client.get(
            f"/api/v1/curriculum/upgrade-subject/preview?school_subject_id={s['id']}",
            headers=_admin_headers(),
        )
        assert preview.status_code == 400
        assert preview.json()["error"]["code"] == "SUBJECT_NOT_ADOPTED"

    def test_preview_audit_carries_counts_not_names(
        self, client, engine_and_session
    ):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = client.get(
            "/api/v1/curriculum/subjects", headers=_admin_headers(),
        ).json()["data"][0]["id"]
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Secret Topic",
                  "code": "T-SEC", "sequence_order": 2},
        )
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        client.get(
            f"/api/v1/curriculum/upgrade-subject/preview?school_subject_id={local_id}",
            headers=_admin_headers(),
        )
        from app.models.audit import AuditLog
        s = SL()
        try:
            row = (
                s.query(AuditLog)
                .filter(AuditLog.event_type ==
                        "curriculum.subject.upgrade_previewed")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            assert "from_version" in blob
            assert "to_version" in blob
            assert "topics_to_add_count" in blob
            # NO names, NO codes.
            assert "Secret Topic" not in blob
            assert "T-SEC" not in blob
        finally:
            s.close()


class TestAuditVersioning:
    def test_upgrade_audit_includes_version_delta(self, client, engine_and_session):
        _, SL = engine_and_session
        nat_id, u1 = _seed_and_publish_national(client)
        client.post(
            "/api/v1/curriculum/adopt-subject",
            headers=_admin_headers(),
            json={"national_subject_id": nat_id},
        )
        local_id = client.get(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(),
        ).json()["data"][0]["id"]
        client.post(
            "/api/v1/ministry/national-curriculum/topics",
            headers=_ops_headers(),
            json={"national_unit_id": u1, "name": "Fractions", "code": "T-FRAC",
                  "sequence_order": 2},
        )
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{nat_id}/republish",
            headers=_ops_headers(),
        )
        client.post(
            "/api/v1/curriculum/upgrade-subject",
            headers=_admin_headers(),
            json={"school_subject_id": local_id},
        )
        from app.models.audit import AuditLog
        s = SL()
        try:
            row = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "curriculum.subject.upgraded")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            # Version transition AND counts ARE in details.
            assert "from_version" in blob
            assert "to_version" in blob
            assert "topics_added" in blob
            # Topic names NOT in details.
            assert "Fractions" not in blob
            assert "Integers" not in blob
        finally:
            s.close()
