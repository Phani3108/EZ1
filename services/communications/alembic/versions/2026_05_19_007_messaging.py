"""parent-teacher messaging (Phase 11b / T-011)

Revision ID: 2026_05_19_007
Revises: 2026_05_19_006
Create Date: 2026-05-26

Adds `message_threads` + `messages` tables for the parent-teacher 1:1
messaging surface described in task.md §2.1 ("teachers need 1:1
conversations (audit-logged)") and §2.3 ("zero parent→teacher
communication today").

Append-only design — soft-delete via `messages.redacted_at`. Hard-delete
only through the retention purge job.

Idempotent — safe to re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_19_007"
down_revision: Union[str, None] = "2026_05_19_006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("message_threads"):
        op.create_table(
            "message_threads",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", UUID(as_uuid=True), nullable=False),
            sa.Column("parent_user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("teacher_user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("parent_unread_count", sa.Integer(), nullable=False,
                      server_default="0"),
            sa.Column("teacher_unread_count", sa.Integer(), nullable=False,
                      server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "school_id", "parent_user_id", "teacher_user_id",
                name="uq_message_thread_pair",
            ),
        )
        op.create_index("ix_msg_thread_parent", "message_threads",
                        ["school_id", "parent_user_id"])
        op.create_index("ix_msg_thread_teacher", "message_threads",
                        ["school_id", "teacher_user_id"])
        op.create_index("ix_msg_thread_last_message", "message_threads",
                        ["school_id", "last_message_at"])

    if not _has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", UUID(as_uuid=True), nullable=False),
            sa.Column("thread_id", UUID(as_uuid=True),
                      sa.ForeignKey("message_threads.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("sender_user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("sender_role", sa.String(32), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("redacted_by_user_id", UUID(as_uuid=True), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_message_thread_created", "messages",
                        ["thread_id", "created_at"])
        op.create_index("ix_message_school", "messages", ["school_id"])


def downgrade() -> None:
    # Message threads contain user-generated content under retention
    # policy. Don't drop on routine downgrade — operator must do this
    # manually after archiving.
    pass
