"""Read-only queries against the reporting projection DB.

PH2-11 — academics serves /api/v1/reports/* by querying the projection
tables maintained by the reporting-service consumer. This service mirrors
the read methods that used to live on
`reporting-service/app/services/reporting_service.py` (`ReportingService`)
but contains NONE of the write/consume logic — those stay in the consumer
process.

Why a separate read service module?
  * Keeps the projection-model boundary clean: only this module imports
    `app.models.projections`. Nothing else in academics should.
  * Lets us swap the underlying read engine later (e.g. PgBouncer-routed
    replica) without touching route handlers.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.projections import (
    AttendanceDailyAggregate,
    DashboardStats,
    FinancialSummary,
)


class ReportingQueryService:
    """Read-only projection queries. NO writes — that's the consumer's job."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard(self, school_id) -> dict:
        sid = str(school_id)
        stats = (
            self.db.query(DashboardStats)
            .filter(DashboardStats.school_id == sid)
            .first()
        )
        if not stats:
            return {
                "total_students": 0,
                "active_students": 0,
                "total_enrollments": 0,
                "attendance_today_rate": 0.0,
                "outstanding_fees": 0.0,
                "collected_this_term": 0.0,
                "announcements_this_month": 0,
                "total_classes": 1,
                "attendance_rate": 0.0,
                "total_revenue": 0.0,
                "total_outstanding": 0.0,
                "announcements_count": 0,
            }

        attendance_rate = 0.0
        if stats.attendance_today_total > 0:
            attendance_rate = round(
                (stats.attendance_today_present / stats.attendance_today_total) * 100.0,
                1,
            )
        outstanding = float(stats.total_invoiced - stats.total_paid)
        collected = float(stats.total_paid)

        return {
            "total_students": stats.total_students,
            "active_students": stats.active_students,
            "total_enrollments": stats.total_enrollments,
            "attendance_today_rate": attendance_rate,
            "outstanding_fees": outstanding,
            "collected_this_term": collected,
            "announcements_this_month": stats.announcements_this_month,
            # Legacy / extra fields kept for backwards-compatible consumers
            "total_classes": stats.total_enrollments // 10 + 1,
            "attendance_rate": attendance_rate / 100.0 if attendance_rate else 0.0,
            "total_revenue": collected,
            "total_outstanding": outstanding,
            "announcements_count": stats.announcements_this_month,
        }

    def get_attendance_trend(
        self, school_id, from_date: date, to_date: date
    ) -> list[dict]:
        sid = str(school_id)
        rows = (
            self.db.query(AttendanceDailyAggregate)
            .filter(
                AttendanceDailyAggregate.school_id == sid,
                AttendanceDailyAggregate.date >= from_date,
                AttendanceDailyAggregate.date <= to_date,
            )
            .order_by(AttendanceDailyAggregate.date)
            .all()
        )
        return [
            {
                "date": r.date.isoformat(),
                "present": r.present_count,
                "absent": r.absent_count,
                "late": r.late_count,
                "total": r.present_count + r.absent_count + r.late_count,
                "rate": round(
                    r.present_count
                    / max(r.present_count + r.absent_count + r.late_count, 1)
                    * 100,
                    1,
                ),
            }
            for r in rows
        ]

    def get_financial_summary(
        self, school_id, year_id: Optional[str] = None
    ) -> list[dict]:
        sid = str(school_id)
        q = self.db.query(FinancialSummary).filter(FinancialSummary.school_id == sid)
        if year_id:
            q = q.filter(FinancialSummary.academic_year_id == str(year_id))
        return [
            {
                "academic_year_id": str(f.academic_year_id),
                "total_invoiced": float(f.total_invoiced),
                "total_paid": float(f.total_paid),
                "total_outstanding": float(f.total_outstanding),
            }
            for f in q.all()
        ]
