"""Phase 16 — Curriculum models + NationalCurriculum reference

Revision ID: 2026_05_27_021
Revises: 2026_05_27_020
Create Date: 2026-05-27

Idempotent. Adds:
  * Subject.grade_levels (JSON text) + Subject.national_subject_id.
  * `curriculum_units`, `curriculum_topics` — school-local curriculum.
  * `national_subjects`, `national_units`, `national_topics` — Ministry
    reference data (no school_id; global rows).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_27_021"
down_revision: Union[str, None] = "2026_05_27_020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns(table)]
    return col in cols


def upgrade() -> None:
    # ── Phase 16b — topic_ids cross-index on existing content tables ──
    for table, extra_cols in (
        ("lesson_plans", []),
        ("formative_assessments", []),
        ("homework", [("template_source_id", sa.String(36))]),
        ("assessments", [
            ("description", sa.Text()),
            ("instructions", sa.Text()),
            ("question_ids", sa.Text()),
            ("exam_paper_attachment_id", sa.String(36)),
        ]),
    ):
        if _has(table):
            if not _has_col(table, "topic_ids"):
                op.add_column(table, sa.Column("topic_ids", sa.Text(), nullable=True))
            for col_name, col_type in extra_cols:
                if not _has_col(table, col_name):
                    op.add_column(table, sa.Column(col_name, col_type, nullable=True))

    # ── Subject extensions ──────────────────────────────────────────
    if not _has_col("subjects", "grade_levels"):
        op.add_column(
            "subjects", sa.Column("grade_levels", sa.Text(), nullable=True),
        )
    if not _has_col("subjects", "national_subject_id"):
        op.add_column(
            "subjects",
            sa.Column("national_subject_id", sa.String(36), nullable=True),
        )
        op.create_index(
            "ix_subjects_national_subject_id", "subjects",
            ["national_subject_id"],
        )

    # ── School-local curriculum ────────────────────────────────────
    if not _has("curriculum_units"):
        op.create_table(
            "curriculum_units",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", UUID(as_uuid=True), nullable=False),
            sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("sequence_order", sa.Integer(),
                      nullable=False, server_default="0"),
            sa.Column("grade_level", sa.String(32), nullable=True),
            sa.Column("national_unit_id", sa.String(36), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_by", UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "school_id", "subject_id", "code",
                name="uq_curriculum_unit_subject_code",
            ),
        )
        op.create_index(
            "ix_curriculum_units_school_subject", "curriculum_units",
            ["school_id", "subject_id"],
        )
        op.create_index(
            "ix_curriculum_units_national_unit_id", "curriculum_units",
            ["national_unit_id"],
        )

    if not _has("curriculum_topics"):
        op.create_table(
            "curriculum_topics",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", UUID(as_uuid=True), nullable=False),
            sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "unit_id", UUID(as_uuid=True),
                sa.ForeignKey("curriculum_units.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "parent_topic_id", UUID(as_uuid=True),
                sa.ForeignKey("curriculum_topics.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("sequence_order", sa.Integer(),
                      nullable=False, server_default="0"),
            sa.Column("learning_outcomes", sa.Text(), nullable=True),
            sa.Column("national_topic_id", sa.String(36), nullable=True),
            sa.Column("created_by", UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "school_id", "unit_id", "code",
                name="uq_curriculum_topic_unit_code",
            ),
        )
        op.create_index(
            "ix_curriculum_topics_school_unit", "curriculum_topics",
            ["school_id", "unit_id"],
        )
        op.create_index(
            "ix_curriculum_topics_school_subject", "curriculum_topics",
            ["school_id", "subject_id"],
        )
        op.create_index(
            "ix_curriculum_topics_national_topic_id", "curriculum_topics",
            ["national_topic_id"],
        )

    # ── National (Ministry-side) curriculum ────────────────────────
    if not _has("national_subjects"):
        op.create_table(
            "national_subjects",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("country", sa.String(5), nullable=False,
                      server_default="ZW"),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("ministry_published_at",
                      sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "country", "code", name="uq_national_subject_code",
            ),
        )

    if not _has("national_units"):
        op.create_table(
            "national_units",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "national_subject_id", UUID(as_uuid=True),
                sa.ForeignKey("national_subjects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("sequence_order", sa.Integer(),
                      nullable=False, server_default="0"),
            sa.Column("grade_level", sa.String(32), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "national_subject_id", "code",
                name="uq_national_unit_subject_code",
            ),
        )
        op.create_index(
            "ix_national_units_subject", "national_units",
            ["national_subject_id"],
        )

    if not _has("national_topics"):
        op.create_table(
            "national_topics",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "national_unit_id", UUID(as_uuid=True),
                sa.ForeignKey("national_units.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "parent_topic_id", UUID(as_uuid=True),
                sa.ForeignKey("national_topics.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("sequence_order", sa.Integer(),
                      nullable=False, server_default="0"),
            sa.Column("learning_outcomes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "national_unit_id", "code",
                name="uq_national_topic_unit_code",
            ),
        )
        op.create_index(
            "ix_national_topics_unit", "national_topics",
            ["national_unit_id"],
        )


def downgrade() -> None:
    for t in (
        "national_topics", "national_units", "national_subjects",
        "curriculum_topics", "curriculum_units",
    ):
        if _has(t):
            op.drop_table(t)
    if _has_col("subjects", "national_subject_id"):
        op.drop_index("ix_subjects_national_subject_id", table_name="subjects")
        op.drop_column("subjects", "national_subject_id")
    if _has_col("subjects", "grade_levels"):
        op.drop_column("subjects", "grade_levels")
