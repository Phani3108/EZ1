"""Phase 15a — StudentDraft + ParentDraft tests.

Covers:
  * Teacher submits a student draft → row lands in pending queue.
  * Admin approves → real Student row created + ParentDraft auto-spawned
    when contact info present.
  * Admin rejects with reason → row marked rejected; reason stored.
  * Tenant isolation — admin in school A cannot see/approve drafts
    from school B.
  * Audit invariants — submit/approve/reject events log scoped IDs
    only; names, DOB never logged. Rejection reason IS in the audit
    detail (admin-supplied, the only place we accept free text).
"""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_drafts.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
TEACHER_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
ADMIN_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    # Import every model module so Base.metadata sees them all.
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


def _headers(role: str, user_id: uuid.UUID, school_id: uuid.UUID,
             perms: str):
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


def teacher_headers(school_id=None):
    return _headers("Teacher", TEACHER_A, school_id or SCHOOL_A,
                    "student:draft")


def admin_headers(school_id=None, user_id=None):
    return _headers("SchoolAdmin", user_id or ADMIN_A,
                    school_id or SCHOOL_A,
                    "school:manage,student:write,student:read")


class TestSubmit:
    def test_teacher_submits_draft(self, client):
        r = client.post(
            "/api/v1/drafts/students",
            headers=teacher_headers(),
            json={
                "first_name": "Tendai",
                "last_name": "Mukoma",
                "student_code": "S-001",
                "parent_phone": "+263770111111",
                "parent_first_name": "Mai",
                "parent_last_name": "Mukoma",
            },
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["review_status"] == "pending"
        assert d["first_name"] == "Tendai"

    def test_list_pending(self, client):
        client.post("/api/v1/drafts/students", headers=teacher_headers(),
                    json={"first_name": "A", "last_name": "B",
                          "student_code": "S-100"})
        client.post("/api/v1/drafts/students", headers=teacher_headers(),
                    json={"first_name": "C", "last_name": "D",
                          "student_code": "S-101"})
        r = client.get("/api/v1/drafts/students?status=pending",
                       headers=admin_headers())
        rows = r.json()["data"]
        assert len(rows) == 2

    def test_tenant_isolation_on_list(self, client):
        client.post("/api/v1/drafts/students",
                    headers=teacher_headers(school_id=SCHOOL_A),
                    json={"first_name": "A", "last_name": "B",
                          "student_code": "S-A"})
        # Admin in school B should see nothing.
        r = client.get("/api/v1/drafts/students",
                       headers=admin_headers(school_id=SCHOOL_B,
                                             user_id=ADMIN_B))
        assert r.json()["data"] == []


class TestApprove:
    def test_approve_creates_student_and_parent_draft(self, client, engine_and_session):
        c = client
        _, SL = engine_and_session
        r = c.post("/api/v1/drafts/students", headers=teacher_headers(),
                   json={"first_name": "Tinashe", "last_name": "M",
                         "student_code": "S-200",
                         "parent_phone": "+263770444555",
                         "parent_first_name": "Mai",
                         "parent_last_name": "M"})
        draft_id = r.json()["data"]["id"]

        ap = c.post(f"/api/v1/drafts/students/{draft_id}/approve",
                    headers=admin_headers(), json={})
        assert ap.status_code == 200, ap.text
        data = ap.json()["data"]
        assert data["draft"]["review_status"] == "approved"
        assert data["student_id"] is not None

        # Real Student row exists.
        from app.models.student import Student
        from app.models.onboarding import ParentDraft
        s = SL()
        try:
            student = s.query(Student).filter(
                Student.id == uuid.UUID(data["student_id"])).first()
            assert student is not None
            assert student.first_name == "Tinashe"
            assert student.student_code == "S-200"
            # ParentDraft auto-spawned (since parent_phone present).
            pd = s.query(ParentDraft).filter(
                ParentDraft.student_id == student.id).first()
            assert pd is not None
            assert pd.phone == "+263770444555"
            assert pd.review_status == "pending"
        finally:
            s.close()

    def test_approve_without_parent_contact_no_parent_draft(self, client, engine_and_session):
        _, SL = engine_and_session
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "Solo", "last_name": "Kid",
                              "student_code": "S-301"})
        draft_id = r.json()["data"]["id"]
        client.post(f"/api/v1/drafts/students/{draft_id}/approve",
                    headers=admin_headers(), json={})
        from app.models.onboarding import ParentDraft
        s = SL()
        try:
            assert s.query(ParentDraft).count() == 0
        finally:
            s.close()

    def test_approve_rejected_if_no_student_code(self, client):
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "NoCode", "last_name": "Y"})
        draft_id = r.json()["data"]["id"]
        ap = client.post(f"/api/v1/drafts/students/{draft_id}/approve",
                         headers=admin_headers(), json={})
        assert ap.status_code == 400
        assert ap.json()["error"]["code"] == "STUDENT_CODE_REQUIRED"

    def test_approve_blocked_on_duplicate_code(self, client, engine_and_session):
        _, SL = engine_and_session
        from app.models.student import Student
        s = SL()
        try:
            s.add(Student(
                id=uuid.uuid4(), school_id=SCHOOL_A,
                student_code="DUP-1", first_name="X", last_name="X",
            ))
            s.commit()
        finally:
            s.close()
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "A", "last_name": "A",
                              "student_code": "DUP-1"})
        ap = client.post(f"/api/v1/drafts/students/{r.json()['data']['id']}/approve",
                         headers=admin_headers(), json={})
        assert ap.status_code == 409
        assert ap.json()["error"]["code"] == "STUDENT_CODE_TAKEN"


class TestReject:
    def test_reject_with_reason(self, client):
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "Wrong", "last_name": "Entry",
                              "student_code": "S-400"})
        draft_id = r.json()["data"]["id"]
        rj = client.post(f"/api/v1/drafts/students/{draft_id}/reject",
                         headers=admin_headers(),
                         json={"reason": "duplicate of existing record"})
        assert rj.status_code == 200, rj.text
        d = rj.json()["data"]
        assert d["review_status"] == "rejected"
        assert d["rejection_reason"] == "duplicate of existing record"


class TestParentDraftApprove:
    def test_full_round_trip(self, client, engine_and_session):
        _, SL = engine_and_session
        # 1. Submit student draft with parent contact.
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "RoundTrip", "last_name": "Kid",
                              "student_code": "S-500",
                              "parent_phone": "+263770999000",
                              "parent_first_name": "Mai", "parent_last_name": "K"})
        draft_id = r.json()["data"]["id"]
        # 2. Approve student → spawns parent draft.
        ap = client.post(f"/api/v1/drafts/students/{draft_id}/approve",
                         headers=admin_headers(), json={})
        student_id = ap.json()["data"]["student_id"]
        # 3. Find the parent draft.
        pd = client.get("/api/v1/drafts/parents?status=pending",
                        headers=admin_headers())
        rows = pd.json()["data"]
        assert len(rows) == 1
        pdid = rows[0]["id"]
        # 4. Approve the parent draft.
        pap = client.post(f"/api/v1/drafts/parents/{pdid}/approve",
                          headers=admin_headers())
        assert pap.status_code == 200, pap.text
        parent_id = pap.json()["data"]["parent_id"]
        # 5. Verify Parent + StudentParent rows exist.
        from app.models.student import Parent, StudentParent
        s = SL()
        try:
            p = s.query(Parent).filter(Parent.id == uuid.UUID(parent_id)).first()
            assert p is not None
            sp = s.query(StudentParent).filter(
                StudentParent.parent_id == p.id,
                StudentParent.student_id == uuid.UUID(student_id),
            ).first()
            assert sp is not None
        finally:
            s.close()


class TestAuditInvariants:
    def test_audit_omits_names_and_dob(self, client, engine_and_session):
        _, SL = engine_and_session
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "SECRETFIRST",
                              "last_name": "SECRETLAST",
                              "student_code": "S-AUD",
                              "dob": "2010-03-15"})
        draft_id = r.json()["data"]["id"]
        client.post(f"/api/v1/drafts/students/{draft_id}/approve",
                    headers=admin_headers(), json={})

        from app.models.audit import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type.like("student.draft.%"))
                .all()
            )
            assert len(rows) >= 2  # submitted + approved
            for row in rows:
                blob = _json.dumps({"target": row.target,
                                    "details": row.details or "{}"})
                assert "SECRETFIRST" not in blob
                assert "SECRETLAST" not in blob
                assert "2010-03-15" not in blob
        finally:
            s.close()

    def test_audit_rejection_includes_reason(self, client, engine_and_session):
        _, SL = engine_and_session
        r = client.post("/api/v1/drafts/students", headers=teacher_headers(),
                        json={"first_name": "X", "last_name": "Y",
                              "student_code": "S-REJ"})
        client.post(f"/api/v1/drafts/students/{r.json()['data']['id']}/reject",
                    headers=admin_headers(),
                    json={"reason": "ADMIN_REJECT_NOTE_42"})
        from app.models.audit import AuditLog
        s = SL()
        try:
            row = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "student.draft.rejected")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            # The admin-supplied reason IS in the audit detail (this is
            # the one explicit ADR-018 exception — admin-supplied free
            # text, 200-char-capped).
            assert "ADMIN_REJECT_NOTE_42" in blob
        finally:
            s.close()
