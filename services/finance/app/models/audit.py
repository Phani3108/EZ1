"""Audit log table for the finance service (Phase 9 follow-up).

Uses the shared `AuditLogMixin` from `eduzim_shared.audit` so the schema
matches the same shape every other service uses. New columns only ever
get added in one place (the mixin); per-service migrations pick them up
on the next alembic run.

See ADR 018 for the architectural decisions and the per-write wiring
policy.
"""
from eduzim_shared.audit import AuditLogMixin

from app.database import Base


class AuditLog(AuditLogMixin, Base):
    __tablename__ = "audit_log"
