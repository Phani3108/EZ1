"""Phase 15a — StudentDraft + ParentDraft.

Teachers can add students directly into a *draft* queue (they have
`student:draft` permission). Admins (`school:manage`) review the queue
and either approve (→ real Student + Enrollment row + parent invite
queued) or reject (with a free-text reason).

The Draft pattern keeps the safer review step that matches how real
schools run — a teacher noticing a new student arrived can capture them
on-the-spot without polluting the live roster until an admin signs off.

Audit invariants (ADR 018):
  * `student.draft.submitted` — target = {school_id, draft_id}.
    Details = {submitted_by_user_id, class_id}. NO names, NO DOB.
  * `student.draft.approved` — target = {school_id, draft_id, student_id}.
    Details = {approved_by_user_id}. NO names.
  * `student.draft.rejected` — target = {school_id, draft_id}.
    Details = {approved_by_user_id, rejection_reason}. The
    rejection_reason IS free text — it's admin-supplied and short.
    This is the only place we log admin-supplied free text in audit
    details; the rejection-reason field has a 200-char cap.
"""
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, String, Date, DateTime, Boolean, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class StudentDraft(Base):
    __tablename__ = "student_drafts"
    __table_args__ = (
        Index("ix_student_drafts_school_status",
              "school_id", "review_status"),
        Index("ix_student_drafts_submitted_by",
              "submitted_by_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)

    # Mirrors Student. student_code stays optional in draft — admin
    # can assign it on approval.
    student_code = Column(String(50), nullable=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    dob = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    admission_date = Column(Date, nullable=True)

    # Class to enroll the student into, if known. Optional — admin may
    # assign at approval time.
    class_id = Column(UUID(as_uuid=True), nullable=True)

    # Parent contact information captured at draft time. If present,
    # a ParentDraft is automatically spawned on approval and an
    # Invitation is queued.
    parent_first_name = Column(String(255), nullable=True)
    parent_last_name = Column(String(255), nullable=True)
    parent_phone = Column(String(32), nullable=True)
    parent_email = Column(String(255), nullable=True)
    parent_relationship_type = Column(String(20), nullable=True)

    # Lifecycle.
    submitted_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    submitted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    review_status = Column(
        String(16), nullable=False, default="pending",
    )  # pending | approved | rejected
    reviewed_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(200), nullable=True)

    # Set on approval — back-reference to the real Student row created.
    approved_student_id = Column(UUID(as_uuid=True), nullable=True)


class InviteRequest(Base):
    """Phase 15 — queue of invitations the school wants to issue.

    Academics owns class assignments + the school roster, so it's the
    natural source of "we want to invite this teacher / parent."
    Identity owns Users + the Invitation token table — admin-web reads
    this queue + posts each row to identity's `POST /api/v1/invitations`,
    then marks the row dispatched with the returned invitation_id.

    Keeping the queue here (rather than calling identity inline from
    the bulk endpoint) keeps the bulk-import path single-service,
    transactional, and easy to test in isolation. The cross-service
    HTTP hop happens in a separate, retry-friendly worker step.

    Fields mirror identity's Invitation schema but at the request
    level (no token yet — that's created by identity at dispatch).
    """
    __tablename__ = "invite_requests"
    __table_args__ = (
        Index("ix_invite_requests_school_status",
              "school_id", "request_status"),
        Index("ix_invite_requests_role", "role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)

    # SchoolAdmin | Teacher | Parent | Student
    role = Column(String(32), nullable=False)
    full_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(32), nullable=True)

    # For Parent invites — the student this parent is linked to.
    # For Teacher invites — comma-separated class_code list (the
    # admin-web dispatcher uses these to wire ClassTeacherAssignment
    # after identity creates the User row).
    target_resource_id = Column(String(36), nullable=True)
    target_resource_type = Column(String(32), nullable=True)
    extra = Column(String(500), nullable=True)  # e.g., class_codes csv

    # pending | dispatched | failed | superseded
    request_status = Column(String(16), nullable=False, default="pending")
    identity_invitation_id = Column(String(36), nullable=True)
    last_error = Column(String(500), nullable=True)

    requested_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    requested_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    dispatched_at = Column(DateTime(timezone=True), nullable=True)


class ParentDraft(Base):
    __tablename__ = "parent_drafts"
    __table_args__ = (
        Index("ix_parent_drafts_school_status",
              "school_id", "review_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)

    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(32), nullable=False)
    email = Column(String(255), nullable=True)
    relationship_type = Column(String(20), nullable=False, default="GUARDIAN")

    # The student this parent is being linked to (the same admin-
    # approval flow auto-spawns this row when a StudentDraft with
    # parent contact is approved).
    student_id = Column(UUID(as_uuid=True), nullable=True)

    submitted_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    submitted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    review_status = Column(
        String(16), nullable=False, default="pending",
    )
    reviewed_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(200), nullable=True)

    approved_parent_id = Column(UUID(as_uuid=True), nullable=True)
