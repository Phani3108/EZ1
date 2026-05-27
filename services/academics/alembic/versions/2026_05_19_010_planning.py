"""planning tables (Phase 11d)

Revision ID: 2026_05_19_010
Revises: 2026_05_19_009
Create Date: 2026-05-26

Five-table batch: school_periods (T-010 promotion target),
lesson_plans (T-005), formative_assessments + formative_responses
(T-013), exam_seat_plans (T-012). Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_010"
down_revision: Union[str, None] = "2026_05_19_009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("school_periods"):
        op.create_table(
            "school_periods",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("period_number", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "period_number",
                                name="uq_school_period_number"),
        )
        op.create_index("ix_school_periods_school", "school_periods", ["school_id"])

    if not _has("lesson_plans"):
        op.create_table(
            "lesson_plans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("subject_id", sa.String(36), nullable=True),
            sa.Column("class_id", sa.String(36), nullable=True),
            sa.Column("template_id", sa.String(36), nullable=True),
            sa.Column("objectives", sa.Text(), nullable=True),
            sa.Column("activities", sa.Text(), nullable=True),
            sa.Column("resources", sa.Text(), nullable=True),
            sa.Column("scheduled_date", sa.Date(), nullable=True),
            sa.Column("scheduled_period_number", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_lesson_plans_school_class", "lesson_plans",
                        ["school_id", "class_id"])
        op.create_index("ix_lesson_plans_template", "lesson_plans",
                        ["school_id", "template_id"])

    if not _has("formative_assessments"):
        op.create_table(
            "formative_assessments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("class_id", sa.String(36), nullable=False),
            sa.Column("subject_id", sa.String(36), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("formative_kind", sa.String(32), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_formative_school_class", "formative_assessments",
                        ["school_id", "class_id"])

    if not _has("formative_responses"):
        op.create_table(
            "formative_responses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("formative_assessment_id", sa.String(36),
                      sa.ForeignKey("formative_assessments.id",
                                    ondelete="CASCADE"), nullable=False),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("response_text", sa.Text(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("formative_assessment_id", "student_id",
                                name="uq_formative_response_student"),
        )

    if not _has("exam_seat_plans"):
        op.create_table(
            "exam_seat_plans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("assessment_id", sa.String(36), nullable=False),
            sa.Column("room", sa.String(80), nullable=True),
            sa.Column("layout_json", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_seat_plan_assessment", "exam_seat_plans",
                        ["school_id", "assessment_id"])


def downgrade() -> None:
    for t in (
        "exam_seat_plans", "formative_responses", "formative_assessments",
        "lesson_plans", "school_periods",
    ):
        if _has(t):
            op.drop_table(t)
