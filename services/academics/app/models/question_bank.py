"""Phase 16c — Question Bank.

Reusable, per-school question pool. The Assessment row's
`question_ids` JSON array references entries here; the bulk-marks
upsert path auto-grades when an assessment has bound questions.

Models
------
* `Question`       — published, ready-to-use questions. Per-school.
* `QuestionOption` — choices for MCQ questions. Optional `is_correct`.
                     For TRUE_FALSE / SHORT_ANSWER questions, the
                     answer key lives on Question.correct_answer_text.
* `QuestionDraft`  — teacher-submitted draft pending HoD/Admin review.
                     Mirrors the Phase 15 StudentDraft pattern; on
                     approval, a real `Question` row is created.

Audit invariants (ADR 018)
-------------------------
* `question.created` — target = `{school_id, subject_id, question_id}`.
                       details = `{type, difficulty}`. NO text, NO answer.
* `question.draft.submitted` / `.approved` / `.rejected` — same shape
                       as student.draft.* (rejection_reason allowed on
                       reject; capped at 200 chars).
* `assessment.composed` — target = `{school_id, assessment_id}`.
                       details = `{question_count, has_exam_paper_pdf}`.

Cross-index
-----------
Questions carry `topic_ids` (JSON text array of Topic UUIDs) so the
existing `/curriculum/topics/{id}/resources` endpoint can list them
alongside lesson plans and homework. The cross-index code includes
Questions when the column is set.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, Integer, Boolean,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Question(Base):
    """Published question, reusable across assessments."""
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_school_subject", "school_id", "subject_id"),
        Index("ix_questions_school_status", "school_id", "status"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False)
    subject_id = Column(UUID_STR, nullable=False)

    # JSON text array of Topic UUIDs this question covers.
    topic_ids = Column(Text, nullable=True)

    # MCQ | TRUE_FALSE | SHORT_ANSWER. SHORT_ANSWER auto-grading is a
    # case-insensitive trim+strip match — useful for one-word answers
    # like "Harare" or "12". Longer free-form responses should be
    # PDF-attached and manually graded.
    question_type = Column(String(16), nullable=False)

    # The prompt. Up to ~2KB; longer prompts → PDF attachment instead.
    text = Column(Text, nullable=False)

    # Answer key for TRUE_FALSE and SHORT_ANSWER. For TRUE_FALSE the
    # value is "true" or "false" (lowercased). For SHORT_ANSWER it's
    # the canonical expected answer; auto-grader strips + lowercases
    # both sides before comparing. For MCQ this column is NULL — the
    # answer key is on QuestionOption.is_correct.
    correct_answer_text = Column(String(255), nullable=True)

    # 1 (easiest) ... 5 (hardest). Used by the compose-exam UI to
    # spread difficulty.
    difficulty = Column(Integer, nullable=False, default=3)

    # draft | published | archived. Drafts created via QuestionDraft
    # approve flow; admins can directly create `published` rows.
    status = Column(String(16), nullable=False, default="published")

    owner_user_id = Column(UUID_STR, nullable=False)
    approved_by_hod_id = Column(UUID_STR, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Lightweight analytics. Bumped by the auto-grader on every
    # answer submission.
    attempts_count = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)


class QuestionOption(Base):
    """Choice for an MCQ question."""
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint(
            "question_id", "label",
            name="uq_question_options_label",
        ),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    question_id = Column(
        UUID_STR,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # "A" | "B" | "C" | ... — uppercase, ordered.
    label = Column(String(2), nullable=False)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)
    sequence_order = Column(Integer, nullable=False, default=0)


class QuestionDraft(Base):
    """Teacher-submitted draft. HoD or SchoolAdmin reviews + approves.

    Mirrors the Phase 15 StudentDraft pattern. On approval, the
    approve endpoint creates a real `Question` + `QuestionOption` rows
    and records the back-reference via `approved_question_id`.
    """
    __tablename__ = "question_drafts"
    __table_args__ = (
        Index("ix_question_drafts_school_status",
              "school_id", "review_status"),
        Index("ix_question_drafts_submitted_by",
              "submitted_by_user_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False)
    subject_id = Column(UUID_STR, nullable=False)
    topic_ids = Column(Text, nullable=True)

    question_type = Column(String(16), nullable=False)
    text = Column(Text, nullable=False)
    correct_answer_text = Column(String(255), nullable=True)
    difficulty = Column(Integer, nullable=False, default=3)

    # JSON text encoding of the option list for MCQ drafts. Shape:
    # `[{"label": "A", "text": "Foo", "is_correct": true}, …]`. Plain
    # JSON-in-text to avoid a separate `question_draft_options` table
    # — drafts are short-lived.
    options_json = Column(Text, nullable=True)

    submitted_by_user_id = Column(UUID_STR, nullable=False)
    submitted_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    review_status = Column(
        String(16), nullable=False, default="pending",
    )  # pending | approved | rejected
    reviewed_by_user_id = Column(UUID_STR, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(200), nullable=True)

    approved_question_id = Column(UUID_STR, nullable=True)
