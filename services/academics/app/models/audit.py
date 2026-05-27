"""Audit log table for academics (Phase 9 / INFRA-018).

Each service has its own `audit_log` table in its own DB. The
canonical column set lives in `eduzim_shared.audit.AuditLogMixin` —
this file is just the per-service mapping.

Writes go through `eduzim_shared.audit.record_audit_event(db, AuditLog,
...)`. Reads (admin browse) are served by `app/api/audit_routes.py`.

Retention: 2 years per `docs/compliance/retention-policy.md`. Purge
via `scripts/audit-log-retention.py`.
"""
from __future__ import annotations

from eduzim_shared.audit import AuditLogMixin
from app.database import Base


class AuditLog(AuditLogMixin, Base):
    __tablename__ = "audit_log"
