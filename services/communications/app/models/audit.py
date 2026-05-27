"""Audit log table for the communications service (Phase 9 follow-up).

Uses the shared `AuditLogMixin` so the schema matches every other
service. See ADR 018.
"""
from eduzim_shared.audit import AuditLogMixin

from app.database import Base


class AuditLog(AuditLogMixin, Base):
    __tablename__ = "audit_log"
