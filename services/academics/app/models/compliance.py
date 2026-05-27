"""Compliance + feedback + health models — Phase 13b.

  * `ComplianceReportTemplate` (A-005) — Ministry-format report
    templates (Zimbabwe MoPSE).
  * `ComplianceReportSubmission` (A-005) — generated reports tracked
    for the compliance dashboard.
  * `HealthRecord` (A-007) — allergies + emergency contacts +
    vaccinations. PIA-gated per RULE-10 (read access via the
    admin/school-nurse role only; never to teachers).

Disciplinary rollup (A-006) and parent complaints (A-010) reuse the
existing `BehaviorIncident` (Phase 11e) and `Grievance` (Phase 12e)
models — we add aggregation endpoints in `compliance_routes.py`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Date, Text, Boolean, Integer,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── A-005 — Compliance reports ────────────────────────────────────


class ComplianceReportTemplate(Base):
    """Catalog of Ministry-format report templates a school must
    submit (MoPSE statistical returns, financial summaries, etc.).
    Stored as JSON so adding a new template doesn't need code."""
    __tablename__ = "compliance_report_templates"
    __table_args__ = (
        UniqueConstraint("school_id", "code",
                         name="uq_compliance_template_code"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    code = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    # quarterly | termly | annual | adhoc
    cadence = Column(String(16), nullable=False, default="annual")
    # JSON schema describing the fields the report collects
    schema_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ComplianceReportSubmission(Base):
    """One submission of a template for a reporting period. Status
    tracks the lifecycle: draft → submitted → accepted/rejected."""
    __tablename__ = "compliance_report_submissions"
    __table_args__ = (
        Index("ix_compliance_school_period",
              "school_id", "period_label"),
        UniqueConstraint(
            "school_id", "template_id", "period_label",
            name="uq_compliance_submission_period",
        ),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    template_id = Column(UUID_STR, nullable=False)
    period_label = Column(String(64), nullable=False)  # "2026-Q1", "2026"
    # draft | submitted | accepted | rejected
    status = Column(String(16), nullable=False, default="draft")
    # Filled-in payload matching template.schema_json
    payload_json = Column(Text, nullable=False)
    # Attachment id for the generated PDF, if rendered.
    attachment_id = Column(UUID_STR, nullable=True)
    submitted_by_user_id = Column(UUID_STR, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejection_notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-007 — Health records ────────────────────────────────────────


class HealthRecord(Base):
    """Student health record. Highly PII-sensitive — RBAC restricts
    reads to school admin / nurse only. Per ADR 007 the audit details
    NEVER carry the body fields; only the FACT that a record was
    accessed / updated is logged."""
    __tablename__ = "health_records"
    __table_args__ = (
        UniqueConstraint("student_id",
                         name="uq_health_record_student"),
        Index("ix_health_school", "school_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False)
    # Concatenated allergies list — free-form text rather than a
    # rigid taxonomy. A school nurse will know how to read it.
    allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    # Emergency contact — denormalised (separate from Parent because
    # an emergency contact may not be the legal guardian).
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_relation = Column(String(64), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    # JSON-encoded vaccination history. School nurse fills it in;
    # the schema is school-defined per current MoPSE guidance.
    vaccinations_json = Column(Text, nullable=True)
    blood_group = Column(String(8), nullable=True)
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(UUID_STR, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow, onupdate=_utcnow, nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
