"""Phase 16c — Question Bank endpoints + auto-grading helper.

Endpoints
---------
  * `POST /questions`               — direct create (HoD / SchoolAdmin).
  * `GET  /questions`               — list with filters (subject /
                                       topic / type / difficulty).
  * `GET  /questions/{id}`          — single question with options.
  * `POST /question-drafts`         — teacher submits a draft.
  * `GET  /question-drafts`         — list (admin queue).
  * `POST /question-drafts/{id}/approve` — HoD/Admin approves → real
                                       Question + Options created.
  * `POST /question-drafts/{id}/reject`  — with reason.
  * `POST /assessments/{id}/compose`     — bind question_ids to an
                                       Assessment + optional
                                       exam_paper_attachment_id +
                                       instructions.
  * `POST /assessments/{id}/auto-grade`  — given `{student_id,
                                       answers: [{question_id,
                                       response}]}`, score the
                                       submission and upsert a Mark.

Audit invariants (ADR 018)
-------------------------
  * `question.created` / `question.draft.{submitted,approved,rejected}`
    log the question_id + subject_id only. NO question text, NO
    correct_answer_text, NO option text. `rejection_reason` IS logged
    on reject (single allowed free-text exception, 200-char cap).
  * `assessment.composed` logs `{question_count, has_exam_paper_pdf}`.
  * `assessment.auto_graded` logs `{question_count, correct_count}`.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.assessment import Assessment, Mark
from app.models.question_bank import Question, QuestionOption, QuestionDraft
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Question Bank"])


VALID_TYPES = ("MCQ", "TRUE_FALSE", "SHORT_ANSWER")


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request, status=400, details=None):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": details or {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request, status=200):
    return JSONResponse(status_code=status,
                        content={"data": data, "meta": _meta(request)})


def _actor(current_user) -> str:
    return str(current_user["sub"])


def _audit(db: Session, request: Request, *,
           event_type: str, school_id: str, actor: str,
           target: dict, details: Optional[dict] = None):
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    try:
        record_audit_event(
            db, AuditLog,
            event_type=event_type,
            school_id=uuid.UUID(school_id),
            actor_user_id=uuid.UUID(actor),
            target=target,
            details=details or {},
            request_id=request_id,
        )
    except Exception:
        pass


def _ser_question(q: Question, options: List[QuestionOption] | None = None) -> dict:
    return {
        "id": q.id,
        "school_id": q.school_id,
        "subject_id": q.subject_id,
        "topic_ids": json.loads(q.topic_ids) if q.topic_ids else [],
        "question_type": q.question_type,
        "text": q.text,
        "correct_answer_text": q.correct_answer_text,
        "difficulty": int(q.difficulty or 3),
        "status": q.status,
        "owner_user_id": q.owner_user_id,
        "approved_by_hod_id": q.approved_by_hod_id,
        "approved_at": q.approved_at.isoformat() if q.approved_at else None,
        "attempts_count": int(q.attempts_count or 0),
        "correct_count": int(q.correct_count or 0),
        "options": [
            {"id": o.id, "label": o.label, "text": o.text,
             "is_correct": bool(o.is_correct),
             "sequence_order": int(o.sequence_order or 0)}
            for o in (options or [])
        ],
    }


def _ser_draft(d: QuestionDraft) -> dict:
    return {
        "id": d.id,
        "school_id": d.school_id,
        "subject_id": d.subject_id,
        "topic_ids": json.loads(d.topic_ids) if d.topic_ids else [],
        "question_type": d.question_type,
        "text": d.text,
        "correct_answer_text": d.correct_answer_text,
        "difficulty": int(d.difficulty or 3),
        "options_json": json.loads(d.options_json) if d.options_json else [],
        "submitted_by_user_id": d.submitted_by_user_id,
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "review_status": d.review_status,
        "reviewed_by_user_id": d.reviewed_by_user_id,
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "rejection_reason": d.rejection_reason,
        "approved_question_id": d.approved_question_id,
    }


# ─── Schemas ──────────────────────────────────────────────────────


class OptionInput(BaseModel):
    label: str = Field(..., min_length=1, max_length=2)
    text: str = Field(..., min_length=1)
    is_correct: bool = False


class QuestionCreate(BaseModel):
    subject_id: uuid.UUID
    topic_ids: List[uuid.UUID] = Field(default_factory=list)
    question_type: Literal["MCQ", "TRUE_FALSE", "SHORT_ANSWER"]
    text: str = Field(..., min_length=1)
    correct_answer_text: Optional[str] = Field(default=None, max_length=255)
    difficulty: int = Field(default=3, ge=1, le=5)
    options: List[OptionInput] = Field(default_factory=list)


class QuestionDraftSubmit(BaseModel):
    subject_id: uuid.UUID
    topic_ids: List[uuid.UUID] = Field(default_factory=list)
    question_type: Literal["MCQ", "TRUE_FALSE", "SHORT_ANSWER"]
    text: str = Field(..., min_length=1)
    correct_answer_text: Optional[str] = Field(default=None, max_length=255)
    difficulty: int = Field(default=3, ge=1, le=5)
    options: List[OptionInput] = Field(default_factory=list)


class DraftReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)


class AssessmentCompose(BaseModel):
    question_ids: List[uuid.UUID] = Field(default_factory=list)
    instructions: Optional[str] = None
    exam_paper_attachment_id: Optional[uuid.UUID] = None


class AutoGradeAnswer(BaseModel):
    question_id: uuid.UUID
    response: str  # for MCQ: "A" / "B"; for TRUE_FALSE: "true"/"false"; SA: free text


class AutoGradeBody(BaseModel):
    student_id: uuid.UUID
    answers: List[AutoGradeAnswer]


# ─── Validation helpers ───────────────────────────────────────────


def _validate_question_shape(question_type: str, correct_answer_text: Optional[str],
                             options: List[OptionInput]) -> Optional[str]:
    """Return error message string or None if valid."""
    if question_type == "MCQ":
        if not options:
            return "MCQ questions need at least 2 options."
        if len(options) < 2:
            return "MCQ questions need at least 2 options."
        correct = [o for o in options if o.is_correct]
        if len(correct) < 1:
            return "MCQ questions need at least one is_correct option."
    elif question_type == "TRUE_FALSE":
        if not correct_answer_text:
            return "TRUE_FALSE questions need correct_answer_text ('true' or 'false')."
        if correct_answer_text.strip().lower() not in ("true", "false"):
            return "correct_answer_text must be 'true' or 'false'."
    elif question_type == "SHORT_ANSWER":
        if not correct_answer_text:
            return "SHORT_ANSWER questions need correct_answer_text."
    return None


# ─── Direct create + list ─────────────────────────────────────────


@router.post("/questions")
def create_question(
    body: QuestionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Direct add to the question bank (HoD / SchoolAdmin path)."""
    err = _validate_question_shape(body.question_type, body.correct_answer_text, body.options)
    if err:
        return _err("INVALID_QUESTION_SHAPE", err, request, status=400)

    q = Question(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        subject_id=str(body.subject_id),
        topic_ids=json.dumps([str(t) for t in body.topic_ids]) if body.topic_ids else None,
        question_type=body.question_type,
        text=body.text,
        correct_answer_text=(
            body.correct_answer_text.strip().lower()
            if (body.question_type == "TRUE_FALSE" and body.correct_answer_text)
            else body.correct_answer_text
        ),
        difficulty=body.difficulty,
        status="published",
        owner_user_id=_actor(current_user),
    )
    db.add(q)
    db.flush()
    opt_rows: List[QuestionOption] = []
    for i, o in enumerate(body.options):
        opt = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q.id,
            label=o.label.upper(),
            text=o.text,
            is_correct=o.is_correct,
            sequence_order=i,
        )
        db.add(opt)
        opt_rows.append(opt)
    _audit(
        db, request,
        event_type="question.created",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "question", "id": q.id,
                "school_id": str(school_id),
                "subject_id": str(body.subject_id)},
        details={"type": body.question_type,
                 "difficulty": int(body.difficulty)},
    )
    db.commit()
    return _ok(_ser_question(q, opt_rows), request, status=201)


@router.get("/questions")
def list_questions(
    request: Request,
    subject_id: Optional[uuid.UUID] = Query(None),
    topic_id: Optional[uuid.UUID] = Query(None),
    question_type: Optional[Literal["MCQ", "TRUE_FALSE", "SHORT_ANSWER"]] = Query(None),
    difficulty: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """List published questions in this school."""
    q = (
        db.query(Question)
        .filter(
            Question.school_id == str(school_id),
            Question.status == "published",
            Question.archived_at.is_(None),
        )
    )
    if subject_id:
        q = q.filter(Question.subject_id == str(subject_id))
    if question_type:
        q = q.filter(Question.question_type == question_type)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    if topic_id:
        needle = f'"{str(topic_id)}"'
        q = q.filter(Question.topic_ids.like(f"%{needle}%"))
    rows = q.order_by(Question.created_at.desc()).limit(500).all()
    # Load options in one batch.
    ids = [r.id for r in rows]
    if ids:
        opts = (
            db.query(QuestionOption)
            .filter(QuestionOption.question_id.in_(ids))
            .all()
        )
        opts_by_q: dict[str, List[QuestionOption]] = {}
        for o in opts:
            opts_by_q.setdefault(o.question_id, []).append(o)
    else:
        opts_by_q = {}
    return _ok([
        _ser_question(r, opts_by_q.get(r.id, []))
        for r in rows
    ], request)


@router.get("/questions/{question_id}")
def get_question(
    question_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = (
        db.query(Question)
        .filter(
            Question.id == str(question_id),
            Question.school_id == str(school_id),
        )
        .first()
    )
    if not q:
        return _err("QUESTION_NOT_FOUND", "Question not found in this school.",
                    request, status=404)
    opts = (
        db.query(QuestionOption)
        .filter(QuestionOption.question_id == q.id)
        .order_by(QuestionOption.sequence_order.asc())
        .all()
    )
    return _ok(_ser_question(q, opts), request)


# ─── Draft → review flow ──────────────────────────────────────────


@router.post("/question-drafts")
def submit_draft(
    body: QuestionDraftSubmit,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Teacher submits a draft. Requires `question:draft` permission
    (granted to Teacher; gateway enforces)."""
    err = _validate_question_shape(body.question_type, body.correct_answer_text, body.options)
    if err:
        return _err("INVALID_QUESTION_SHAPE", err, request, status=400)
    d = QuestionDraft(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        subject_id=str(body.subject_id),
        topic_ids=json.dumps([str(t) for t in body.topic_ids]) if body.topic_ids else None,
        question_type=body.question_type,
        text=body.text,
        correct_answer_text=(
            body.correct_answer_text.strip().lower()
            if (body.question_type == "TRUE_FALSE" and body.correct_answer_text)
            else body.correct_answer_text
        ),
        difficulty=body.difficulty,
        options_json=json.dumps([o.model_dump() for o in body.options]) if body.options else None,
        submitted_by_user_id=_actor(current_user),
    )
    db.add(d)
    db.flush()
    _audit(
        db, request,
        event_type="question.draft.submitted",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "question_draft", "id": d.id,
                "school_id": str(school_id),
                "subject_id": str(body.subject_id)},
        details={"type": body.question_type,
                 "difficulty": int(body.difficulty)},
    )
    db.commit()
    return _ok(_ser_draft(d), request, status=201)


@router.get("/question-drafts")
def list_drafts(
    request: Request,
    status: Optional[Literal["pending", "approved", "rejected"]] = Query("pending"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(QuestionDraft).filter(QuestionDraft.school_id == str(school_id))
    if status:
        q = q.filter(QuestionDraft.review_status == status)
    rows = q.order_by(QuestionDraft.submitted_at.desc()).limit(500).all()
    return _ok([_ser_draft(r) for r in rows], request)


@router.post("/question-drafts/{draft_id}/approve")
def approve_draft(
    draft_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Approve → create real Question + Options. HoD / SchoolAdmin."""
    d = (
        db.query(QuestionDraft)
        .filter(QuestionDraft.id == str(draft_id),
                QuestionDraft.school_id == str(school_id))
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found.", request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)
    options = json.loads(d.options_json) if d.options_json else []

    q = Question(
        id=str(uuid.uuid4()),
        school_id=d.school_id,
        subject_id=d.subject_id,
        topic_ids=d.topic_ids,
        question_type=d.question_type,
        text=d.text,
        correct_answer_text=d.correct_answer_text,
        difficulty=d.difficulty,
        status="published",
        owner_user_id=d.submitted_by_user_id,
        approved_by_hod_id=_actor(current_user),
        approved_at=datetime.now(timezone.utc),
    )
    db.add(q)
    db.flush()
    for i, o in enumerate(options):
        db.add(QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q.id,
            label=str(o.get("label", "")).upper()[:2],
            text=str(o.get("text", "")),
            is_correct=bool(o.get("is_correct", False)),
            sequence_order=i,
        ))
    d.review_status = "approved"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.approved_question_id = q.id
    _audit(
        db, request,
        event_type="question.draft.approved",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "question_draft", "id": d.id,
                "school_id": str(school_id),
                "question_id": q.id},
        details={"approved_by": _actor(current_user)},
    )
    db.commit()
    return _ok({
        "draft": _ser_draft(d),
        "question_id": q.id,
    }, request)


@router.post("/question-drafts/{draft_id}/reject")
def reject_draft(
    draft_id: uuid.UUID,
    body: DraftReject,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    d = (
        db.query(QuestionDraft)
        .filter(QuestionDraft.id == str(draft_id),
                QuestionDraft.school_id == str(school_id))
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found.", request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)
    d.review_status = "rejected"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.rejection_reason = body.reason
    _audit(
        db, request,
        event_type="question.draft.rejected",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "question_draft", "id": d.id,
                "school_id": str(school_id)},
        details={"approved_by": _actor(current_user),
                 "rejection_reason": body.reason},
    )
    db.commit()
    return _ok(_ser_draft(d), request)


# ─── Assessment composition + auto-grading ────────────────────────


@router.post("/assessments/{assessment_id}/compose")
def compose_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentCompose,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Bind a list of Question IDs to an Assessment + optionally
    attach an exam-paper PDF (for long-form / scanned sections that
    auto-grading doesn't cover)."""
    a = (
        db.query(Assessment)
        .filter(Assessment.id == str(assessment_id),
                Assessment.school_id == str(school_id))
        .first()
    )
    if not a:
        return _err("ASSESSMENT_NOT_FOUND",
                    "Assessment not found in this school.",
                    request, status=404)
    # Verify every question belongs to this school.
    qids = [str(q) for q in body.question_ids]
    if qids:
        valid_count = (
            db.query(Question)
            .filter(
                Question.school_id == str(school_id),
                Question.id.in_(qids),
                Question.status == "published",
                Question.archived_at.is_(None),
            )
            .count()
        )
        if valid_count != len(set(qids)):
            return _err("INVALID_QUESTIONS",
                        "One or more question_ids are not in this "
                        "school's published bank.",
                        request, status=400)
    a.question_ids = json.dumps(qids) if qids else None
    if body.instructions is not None:
        a.instructions = body.instructions
    if body.exam_paper_attachment_id is not None:
        a.exam_paper_attachment_id = str(body.exam_paper_attachment_id)
    _audit(
        db, request,
        event_type="assessment.composed",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "assessment", "id": a.id,
                "school_id": str(school_id)},
        details={"question_count": len(qids),
                 "has_exam_paper_pdf": bool(body.exam_paper_attachment_id)},
    )
    db.commit()
    return _ok({
        "assessment_id": a.id,
        "question_ids": qids,
        "instructions": a.instructions,
        "exam_paper_attachment_id": a.exam_paper_attachment_id,
    }, request)


def _normalise(s: str) -> str:
    return (s or "").strip().lower()


@router.post("/assessments/{assessment_id}/auto-grade")
def auto_grade(
    assessment_id: uuid.UUID,
    body: AutoGradeBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Auto-grade one student's answers to a composed assessment.

    Scoring contract:
      - MCQ: response is a single option label (e.g., "A"). Correct
             iff one of the options for that question has
             label == response AND is_correct = true.
      - TRUE_FALSE: response is "true" or "false" (case-insensitive).
             Match against Question.correct_answer_text.
      - SHORT_ANSWER: response and correct_answer_text are both
             trimmed + lowercased before comparing.

    Marks the result onto the student's `Mark` row via upsert. Score =
    correct_count / question_count * max_marks, rounded to 2 dp.
    """
    a = (
        db.query(Assessment)
        .filter(Assessment.id == str(assessment_id),
                Assessment.school_id == str(school_id))
        .first()
    )
    if not a:
        return _err("ASSESSMENT_NOT_FOUND", "Assessment not found.",
                    request, status=404)
    if not a.question_ids:
        return _err("ASSESSMENT_NOT_COMPOSED",
                    "Assessment has no question bank bound. Use compose first.",
                    request, status=400)
    bound = set(json.loads(a.question_ids))
    if not bound:
        return _err("ASSESSMENT_NOT_COMPOSED",
                    "Assessment has zero questions bound.",
                    request, status=400)

    # Load every bound question + its options in two queries.
    bound_list = list(bound)
    qmap: dict[str, Question] = {
        q.id: q for q in db.query(Question)
        .filter(Question.id.in_(bound_list)).all()
    }
    opt_by_q: dict[str, List[QuestionOption]] = {}
    for o in (
        db.query(QuestionOption)
        .filter(QuestionOption.question_id.in_(bound_list)).all()
    ):
        opt_by_q.setdefault(o.question_id, []).append(o)

    answers_by_qid: dict[str, str] = {
        str(a.question_id): a.response for a in body.answers
    }

    correct = 0
    graded_questions = 0
    for qid in bound_list:
        if qid not in answers_by_qid:
            continue
        graded_questions += 1
        q = qmap.get(qid)
        if not q:
            continue
        resp = answers_by_qid[qid]
        if q.question_type == "MCQ":
            for o in opt_by_q.get(qid, []):
                if o.label.upper() == resp.strip().upper() and o.is_correct:
                    correct += 1
                    break
        elif q.question_type == "TRUE_FALSE":
            if _normalise(resp) == _normalise(q.correct_answer_text):
                correct += 1
        elif q.question_type == "SHORT_ANSWER":
            if _normalise(resp) == _normalise(q.correct_answer_text):
                correct += 1
        # Tick analytics counters.
        q.attempts_count = int(q.attempts_count or 0) + 1
        if q.question_type == "MCQ":
            for o in opt_by_q.get(qid, []):
                if o.label.upper() == resp.strip().upper() and o.is_correct:
                    q.correct_count = int(q.correct_count or 0) + 1
                    break
        elif _normalise(resp) == _normalise(q.correct_answer_text):
            q.correct_count = int(q.correct_count or 0) + 1

    # Compute Mark.marks = (correct / total_bound) * max_marks.
    total = len(bound_list)
    max_marks = float(a.max_marks or 0)
    score = (correct / total) * max_marks if total > 0 else 0.0
    score = round(score, 2)

    # Upsert Mark row.
    m = (
        db.query(Mark)
        .filter(
            Mark.assessment_id == a.id,
            Mark.student_id == str(body.student_id),
        )
        .first()
    )
    if m:
        m.marks = score
        m.is_absent = False
        m.graded_by = _actor(current_user)
        m.graded_at = datetime.now(timezone.utc)
        m.remarks = f"Auto-graded: {correct}/{total} correct."
    else:
        m = Mark(
            id=str(uuid.uuid4()),
            school_id=str(school_id),
            assessment_id=a.id,
            student_id=str(body.student_id),
            marks=score,
            is_absent=False,
            remarks=f"Auto-graded: {correct}/{total} correct.",
            graded_by=_actor(current_user),
        )
        db.add(m)

    _audit(
        db, request,
        event_type="assessment.auto_graded",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "mark", "assessment_id": a.id,
                "school_id": str(school_id)},
        details={"question_count": total,
                 "graded_questions": graded_questions,
                 "correct_count": correct},
    )
    db.commit()
    return _ok({
        "assessment_id": a.id,
        "student_id": str(body.student_id),
        "score": score,
        "max_marks": max_marks,
        "correct": correct,
        "graded_questions": graded_questions,
        "total_questions": total,
    }, request)
