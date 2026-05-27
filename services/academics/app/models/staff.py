"""Staff + HR + admissions + transfers models — Phase 13a.

The "school admin's operational depth" lives mostly in academics
(the consolidated service per PH2-12 owns everything school-shaped).

  * `NonTeachingStaff` (A-001) — accountants, drivers, security,
    cleaners, IT support. Distinct from `Teacher` (which lives via
    `class_teacher_assignments`).
  * `LeaveRequest` (A-002) — annual / sick / unpaid / compassionate
    leave with status flow open → approved/rejected → cancelled.
  * `EmploymentContract` (A-002) — basic contract record with role,
    salary band, start/end dates. The full contract document is
    attached via the polymorphic T-008 attachments table.
  * `SalarySlip` (A-002) — generated per pay period. Amount fields
    in integer cents to avoid decimal/float pain.
  * `PerformanceReview` (A-002) — periodic review with reviewer +
    overall_rating + JSON criteria payload.
  * `AdmissionApplication` (A-003) — pre-enrolment pipeline.
    Status flow submitted → in_review → accepted/rejected →
    enrolled. Once `enrolled_at` is set, the Student row exists
    and the application is terminal.
  * `StudentTransfer` (A-004) — in / out transfer record. Holds
    the outgoing transcript reference (an attachment id) for
    outbound transfers and a flag for inbound enrolments coming
    from another school.

Privacy: HR + admissions hold PII. Audit invariants apply (per
ADR 018): `target` carries IDs only; `details` carries event-meta
(status changes, action types) but never PII like names / addresses
/ medical info / contract bodies.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Date, Text, Integer, Boolean, ForeignKey,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── A-001 — Non-teaching staff ───────────────────────────────────


class NonTeachingStaff(Base):
    __tablename__ = "non_teaching_staff"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "staff_code",
            name="uq_non_teaching_staff_code",
        ),
        Index("ix_nts_school_role", "school_id", "role_category"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    # accountant / driver / security / cleaner / it_support / nurse / cook / other
    role_category = Column(String(32), nullable=False, default="other")
    staff_code = Column(String(50), nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    # Links to an Identity User if the staff member has a login. NULL
    # is allowed — many non-teaching staff don't need digital accounts.
    user_id = Column(UUID_STR, nullable=True, unique=True)
    hired_on = Column(Date, nullable=True)
    terminated_on = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-002 — HR: leave, contracts, salary, reviews ────────────────


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_school_user", "school_id", "user_id"),
        Index("ix_leave_school_status", "school_id", "status"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    # annual / sick / unpaid / compassionate / study / maternity / paternity / other
    leave_type = Column(String(32), nullable=False, default="annual")
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    # open | approved | rejected | cancelled
    status = Column(String(16), nullable=False, default="open")
    decided_by_user_id = Column(UUID_STR, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class EmploymentContract(Base):
    __tablename__ = "employment_contracts"
    __table_args__ = (
        Index("ix_contract_school_user", "school_id", "user_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    role_title = Column(String(120), nullable=False)
    # Bands rather than raw values so the salary number can be opaque
    # to most viewers. The actual amount stays in salary slips.
    salary_band = Column(String(32), nullable=True)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=True)  # null = open-ended
    # Optional attachment_id pointing at the signed PDF.
    attachment_id = Column(UUID_STR, nullable=True)
    terminated_at = Column(DateTime(timezone=True), nullable=True)
    termination_reason = Column(String(500), nullable=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class SalarySlip(Base):
    __tablename__ = "salary_slips"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "user_id", "period_year", "period_month",
            name="uq_salary_slip_period",
        ),
        Index("ix_salary_school_user", "school_id", "user_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)  # 1..12
    gross_cents = Column(Integer, nullable=False, default=0)
    deductions_cents = Column(Integer, nullable=False, default=0)
    net_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    # Optional generated PDF attachment id (T-008).
    attachment_id = Column(UUID_STR, nullable=True)
    issued_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"
    __table_args__ = (
        Index("ix_perf_school_user", "school_id", "user_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    reviewer_user_id = Column(UUID_STR, nullable=False)
    period_label = Column(String(80), nullable=False)  # "2026 Q1"
    overall_rating = Column(String(32), nullable=False)  # outstanding | satisfactory | needs_improvement | unsatisfactory
    criteria_json = Column(Text, nullable=True)  # school-defined rubric
    summary = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-003 — Admissions ────────────────────────────────────────────


class AdmissionApplication(Base):
    __tablename__ = "admission_applications"
    __table_args__ = (
        Index("ix_admission_school_status", "school_id", "status"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    # Applicant details (the student-to-be). When converted to a real
    # Student record, `student_id` gets set.
    applicant_first_name = Column(String(255), nullable=False)
    applicant_last_name = Column(String(255), nullable=False)
    applicant_dob = Column(Date, nullable=True)
    applicant_gender = Column(String(10), nullable=True)
    # Guardian details. Optional Parent linkage once a real Parent
    # record exists.
    guardian_first_name = Column(String(255), nullable=False)
    guardian_last_name = Column(String(255), nullable=False)
    guardian_phone = Column(String(20), nullable=False)
    guardian_email = Column(String(255), nullable=True)
    # Target class (admin-side hint, not authoritative).
    target_class_label = Column(String(80), nullable=True)
    notes = Column(Text, nullable=True)
    # submitted | in_review | accepted | rejected | enrolled
    status = Column(String(16), nullable=False, default="submitted")
    decided_by_user_id = Column(UUID_STR, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_notes = Column(String(500), nullable=True)
    # Set when the application is converted to a real Student.
    student_id = Column(UUID_STR, nullable=True, unique=True)
    enrolled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-004 — Transfers ────────────────────────────────────────────


class StudentTransfer(Base):
    __tablename__ = "student_transfers"
    __table_args__ = (
        Index("ix_transfer_school_direction", "school_id", "direction"),
        Index("ix_transfer_student", "student_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False)
    # outbound = student leaving this school; inbound = joining
    direction = Column(String(8), nullable=False)
    counterparty_school_name = Column(String(255), nullable=True)
    counterparty_school_contact = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    # For outbound: the transcript PDF attachment id (T-008).
    transcript_attachment_id = Column(UUID_STR, nullable=True)
    effective_date = Column(Date, nullable=False)
    initiated_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
