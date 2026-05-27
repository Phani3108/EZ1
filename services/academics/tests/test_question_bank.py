"""Phase 16c — Question Bank, draft flow, assessment composition,
auto-grading tests + audit invariants."""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_qbank.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
HOD_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
STUDENT_1 = uuid.uuid4()


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


def _admin_headers(school_id=None, user_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


def _teacher_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(TEACHER_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Teacher",
        "X-Permissions": "question:draft,student:draft",
    }


def _seed_subject(client):
    return client.post(
        "/api/v1/curriculum/subjects",
        headers=_admin_headers(),
        json={"name": "Mathematics", "code": "MATH"},
    ).json()["data"]


def _seed_assessment(SessionLocal, subject_id: str, max_marks=100) -> str:
    from app.models.assessment import Assessment
    s = SessionLocal()
    try:
        a = Assessment(
            id=str(uuid.uuid4()),
            school_id=str(SCHOOL_A),
            academic_year_id=str(uuid.uuid4()),
            term_id=str(uuid.uuid4()),
            class_id=str(uuid.uuid4()),
            subject_id=subject_id,
            name="Mid-term",
            assessment_type="TEST",
            date=date.today(),
            max_marks=max_marks,
            created_by=str(ADMIN_A),
        )
        s.add(a)
        s.commit()
        return str(a.id)
    finally:
        s.close()


class TestCreateQuestion:
    def test_create_mcq_question(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "MCQ",
                "text": "What is 2 + 2?",
                "difficulty": 2,
                "options": [
                    {"label": "A", "text": "3", "is_correct": False},
                    {"label": "B", "text": "4", "is_correct": True},
                    {"label": "C", "text": "5", "is_correct": False},
                    {"label": "D", "text": "22", "is_correct": False},
                ],
            },
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["question_type"] == "MCQ"
        assert len(d["options"]) == 4
        correct = [o for o in d["options"] if o["is_correct"]]
        assert len(correct) == 1 and correct[0]["label"] == "B"

    def test_create_true_false_question(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "TRUE_FALSE",
                "text": "Harare is the capital of Zimbabwe.",
                "correct_answer_text": "true",
                "difficulty": 1,
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["correct_answer_text"] == "true"

    def test_mcq_without_options_rejected(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "MCQ",
                "text": "Q?",
                "difficulty": 1,
                "options": [],
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_QUESTION_SHAPE"

    def test_short_answer_requires_correct_answer_text(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "SHORT_ANSWER",
                "text": "Capital of Zimbabwe?",
                "difficulty": 1,
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_QUESTION_SHAPE"


class TestList:
    def test_filter_by_subject_and_type(self, client):
        s = _seed_subject(client)
        for i, t in enumerate(["MCQ", "TRUE_FALSE", "SHORT_ANSWER"]):
            payload = {
                "subject_id": s["id"],
                "question_type": t,
                "text": f"Q {i}",
                "difficulty": 2,
            }
            if t == "MCQ":
                payload["options"] = [
                    {"label": "A", "text": "1", "is_correct": True},
                    {"label": "B", "text": "2"},
                ]
            else:
                payload["correct_answer_text"] = "true" if t == "TRUE_FALSE" else "Harare"
            client.post("/api/v1/questions", headers=_admin_headers(), json=payload)
        r = client.get(
            f"/api/v1/questions?subject_id={s['id']}&question_type=MCQ",
            headers=_admin_headers(),
        )
        d = r.json()["data"]
        assert len(d) == 1
        assert d[0]["question_type"] == "MCQ"


class TestDraftFlow:
    def test_teacher_submits_then_admin_approves(self, client):
        s = _seed_subject(client)
        # Teacher submits.
        r = client.post(
            "/api/v1/question-drafts",
            headers=_teacher_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "MCQ",
                "text": "What does ZIMSEC stand for?",
                "difficulty": 3,
                "options": [
                    {"label": "A", "text": "Zimbabwe Schools Examinations Council", "is_correct": True},
                    {"label": "B", "text": "Zimbabwe Internal Mathematics Society", "is_correct": False},
                ],
            },
        )
        assert r.status_code == 201, r.text
        draft_id = r.json()["data"]["id"]
        # Admin lists pending drafts.
        l = client.get("/api/v1/question-drafts?status=pending",
                       headers=_admin_headers())
        rows = l.json()["data"]
        assert any(d["id"] == draft_id for d in rows)
        # Admin approves.
        ap = client.post(f"/api/v1/question-drafts/{draft_id}/approve",
                         headers=_admin_headers())
        assert ap.status_code == 200, ap.text
        question_id = ap.json()["data"]["question_id"]
        assert question_id is not None
        # Question is now in the bank.
        q = client.get(f"/api/v1/questions/{question_id}",
                       headers=_admin_headers()).json()["data"]
        assert q["question_type"] == "MCQ"
        assert len(q["options"]) == 2

    def test_reject_with_reason(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/question-drafts",
            headers=_teacher_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "TRUE_FALSE",
                "text": "Bad question",
                "correct_answer_text": "true",
                "difficulty": 1,
            },
        )
        draft_id = r.json()["data"]["id"]
        rj = client.post(
            f"/api/v1/question-drafts/{draft_id}/reject",
            headers=_admin_headers(),
            json={"reason": "Ambiguous wording; please clarify."},
        )
        assert rj.status_code == 200
        assert rj.json()["data"]["review_status"] == "rejected"
        assert rj.json()["data"]["rejection_reason"] == "Ambiguous wording; please clarify."


class TestComposeAndAutoGrade:
    def _make_questions(self, client, subj_id: str) -> list[str]:
        """Create 3 questions: 1 MCQ + 1 TF + 1 SA. Return question_ids."""
        ids = []
        # MCQ
        mcq = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": subj_id,
                "question_type": "MCQ",
                "text": "What is 2 + 2?",
                "difficulty": 2,
                "options": [
                    {"label": "A", "text": "3", "is_correct": False},
                    {"label": "B", "text": "4", "is_correct": True},
                    {"label": "C", "text": "5", "is_correct": False},
                ],
            },
        ).json()["data"]
        ids.append(mcq["id"])
        # TF
        tf = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": subj_id,
                "question_type": "TRUE_FALSE",
                "text": "5 is an odd number.",
                "correct_answer_text": "true",
                "difficulty": 1,
            },
        ).json()["data"]
        ids.append(tf["id"])
        # SA
        sa = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": subj_id,
                "question_type": "SHORT_ANSWER",
                "text": "What is the capital of Zimbabwe?",
                "correct_answer_text": "Harare",
                "difficulty": 2,
            },
        ).json()["data"]
        ids.append(sa["id"])
        return ids

    def test_compose_then_auto_grade_all_correct(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        asmt_id = _seed_assessment(SL, s["id"], max_marks=100)
        q_ids = self._make_questions(client, s["id"])

        # Compose.
        comp = client.post(
            f"/api/v1/assessments/{asmt_id}/compose",
            headers=_admin_headers(),
            json={"question_ids": q_ids,
                  "instructions": "Answer all questions."},
        )
        assert comp.status_code == 200, comp.text

        # Auto-grade — all correct.
        ag = client.post(
            f"/api/v1/assessments/{asmt_id}/auto-grade",
            headers=_admin_headers(),
            json={
                "student_id": str(STUDENT_1),
                "answers": [
                    {"question_id": q_ids[0], "response": "B"},
                    {"question_id": q_ids[1], "response": "true"},
                    {"question_id": q_ids[2], "response": "harare"},
                ],
            },
        )
        assert ag.status_code == 200, ag.text
        d = ag.json()["data"]
        assert d["correct"] == 3
        assert d["total_questions"] == 3
        # 3/3 of 100 = 100.
        assert d["score"] == 100.0

    def test_auto_grade_partial_credit(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        asmt_id = _seed_assessment(SL, s["id"], max_marks=60)
        q_ids = self._make_questions(client, s["id"])
        client.post(
            f"/api/v1/assessments/{asmt_id}/compose",
            headers=_admin_headers(),
            json={"question_ids": q_ids},
        )
        # 1 of 3 correct.
        ag = client.post(
            f"/api/v1/assessments/{asmt_id}/auto-grade",
            headers=_admin_headers(),
            json={
                "student_id": str(STUDENT_1),
                "answers": [
                    {"question_id": q_ids[0], "response": "A"},  # wrong
                    {"question_id": q_ids[1], "response": "false"},  # wrong
                    {"question_id": q_ids[2], "response": "Harare"},  # correct
                ],
            },
        ).json()["data"]
        assert ag["correct"] == 1
        # 1/3 * 60 = 20.0
        assert ag["score"] == 20.0

    def test_short_answer_case_insensitive(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        asmt_id = _seed_assessment(SL, s["id"], max_marks=10)
        q = client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "SHORT_ANSWER",
                "text": "Capital?",
                "correct_answer_text": "Harare",
                "difficulty": 1,
            },
        ).json()["data"]
        client.post(
            f"/api/v1/assessments/{asmt_id}/compose",
            headers=_admin_headers(),
            json={"question_ids": [q["id"]]},
        )
        for resp in ("Harare", "harare", "  HARARE  "):
            r = client.post(
                f"/api/v1/assessments/{asmt_id}/auto-grade",
                headers=_admin_headers(),
                json={"student_id": str(uuid.uuid4()),
                      "answers": [{"question_id": q["id"], "response": resp}]},
            )
            assert r.json()["data"]["correct"] == 1, f"failed for input '{resp}'"

    def test_compose_rejects_questions_from_other_school(self, client, engine_and_session):
        _, SL = engine_and_session
        # School A creates a subject + question.
        s_a = _seed_subject(client)
        q_a = client.post(
            "/api/v1/questions",
            headers=_admin_headers(school_id=SCHOOL_A),
            json={
                "subject_id": s_a["id"],
                "question_type": "TRUE_FALSE",
                "text": "X",
                "correct_answer_text": "true",
                "difficulty": 1,
            },
        ).json()["data"]
        # School B creates a subject + assessment.
        s_b = client.post(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(school_id=SCHOOL_B),
            json={"name": "M", "code": "MATH"},
        ).json()["data"]
        from app.models.assessment import Assessment
        ses = SL()
        try:
            a_b = Assessment(
                id=str(uuid.uuid4()),
                school_id=str(SCHOOL_B),
                academic_year_id=str(uuid.uuid4()),
                term_id=str(uuid.uuid4()),
                class_id=str(uuid.uuid4()),
                subject_id=s_b["id"],
                name="X", assessment_type="TEST",
                date=date.today(), max_marks=10,
                created_by=str(ADMIN_A),
            )
            ses.add(a_b)
            ses.commit()
            assessment_b_id = a_b.id
        finally:
            ses.close()
        # B tries to compose with A's question — rejected.
        r = client.post(
            f"/api/v1/assessments/{assessment_b_id}/compose",
            headers=_admin_headers(school_id=SCHOOL_B),
            json={"question_ids": [q_a["id"]]},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_QUESTIONS"


class TestAuditNoPII:
    def test_question_created_audit_omits_text_and_answer(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        client.post(
            "/api/v1/questions",
            headers=_admin_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "TRUE_FALSE",
                "text": "SECRET_QUESTION_TEXT_42",
                "correct_answer_text": "true",
                "difficulty": 2,
            },
        )
        from app.models.audit import AuditLog
        ses = SL()
        try:
            row = (
                ses.query(AuditLog)
                .filter(AuditLog.event_type == "question.created")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            assert "SECRET_QUESTION_TEXT_42" not in blob
            assert "true" not in blob  # the answer should not be in details
            # Type + difficulty ARE allowed.
            assert "TRUE_FALSE" in blob
            assert "2" in blob
        finally:
            ses.close()

    def test_draft_rejected_audit_includes_reason(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        d = client.post(
            "/api/v1/question-drafts",
            headers=_teacher_headers(),
            json={
                "subject_id": s["id"],
                "question_type": "SHORT_ANSWER",
                "text": "X",
                "correct_answer_text": "X",
                "difficulty": 1,
            },
        ).json()["data"]
        client.post(
            f"/api/v1/question-drafts/{d['id']}/reject",
            headers=_admin_headers(),
            json={"reason": "REJECT_NOTE_QB_42"},
        )
        from app.models.audit import AuditLog
        ses = SL()
        try:
            row = (
                ses.query(AuditLog)
                .filter(AuditLog.event_type == "question.draft.rejected")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            # Reason IS in details (ADR 018 exception for admin free-text).
            assert "REJECT_NOTE_QB_42" in blob
        finally:
            ses.close()
