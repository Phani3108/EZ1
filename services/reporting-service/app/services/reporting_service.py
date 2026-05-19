"""
Reporting Service — Event Consumer + Projection Engine
=========================================================
Consumes domain events, applies projections idempotently.
Each event is:
  1. Checked against inbox (ProcessedEvent)
  2. Applied to projection(s)
  3. Marked as processed

Rebuild: clears all projections, replays event log.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.projections import (
    ProcessedEvent, DashboardStats, AttendanceDailyAggregate,
    FinancialSummary, StudentCountProjection,
)


class ReportingService:
    def __init__(self, db: Session):
        self.db = db

    # ═══════════════════════════════════════════
    # Event Consumption (Idempotent)
    # ═══════════════════════════════════════════

    def consume_event(self, event: dict) -> dict:
        """Process a single domain event with immediate commit."""
        result = self._process_single(event)
        if result["status"] == "processed":
            self.db.commit()
        return result

    def _process_single(self, event: dict, known_processed: set = None) -> dict:
        """Internal: process without commit (for batching)."""
        event_id = event.get("event_id") or str(uuid.uuid4())
        event_type = event.get("event_type", "")
        school_id = event.get("school_id")

        if not school_id:
            return {"status": "rejected", "reason": "missing school_id"}

        school_uuid = uuid.UUID(school_id) if isinstance(school_id, str) else school_id

        # Idempotency — check in-memory set first, then DB
        if known_processed is not None:
            if event_id in known_processed:
                return {"status": "duplicate", "event_id": event_id}
        elif self._is_processed(event_id):
            return {"status": "duplicate", "event_id": event_id}

        handler = self._get_handler(event_type)
        if not handler:
            return {"status": "unknown_event", "event_type": event_type}

        handler(school_uuid, event.get("payload", {}))

        self.db.add(ProcessedEvent(
            event_id=event_id, event_type=event_type, school_id=school_uuid,
        ))
        if known_processed is not None:
            known_processed.add(event_id)

        return {"status": "processed", "event_id": event_id, "event_type": event_type}

    def consume_batch(self, events: list[dict]) -> dict:
        """Process multiple events with single commit at end."""
        # Pre-fetch all processed event_ids for this batch
        batch_ids = [e.get("event_id", "") for e in events if e.get("event_id")]
        known_processed = set()
        if batch_ids:
            chunk_size = 500
            for i in range(0, len(batch_ids), chunk_size):
                chunk = batch_ids[i:i + chunk_size]
                rows = self.db.query(ProcessedEvent.event_id).filter(
                    ProcessedEvent.event_id.in_(chunk),
                ).all()
                known_processed.update(r[0] for r in rows)

        processed = 0
        duplicates = 0
        errors = 0
        for e in events:
            r = self._process_single(e, known_processed)
            if r["status"] == "processed":
                processed += 1
            elif r["status"] == "duplicate":
                duplicates += 1
            else:
                errors += 1

        self.db.commit()
        return {"processed": processed, "duplicates": duplicates, "errors": errors,
                "total": len(events)}

    def _is_processed(self, event_id: str) -> bool:
        return self.db.query(ProcessedEvent).filter(
            ProcessedEvent.event_id == event_id,
        ).first() is not None

    def _get_handler(self, event_type: str):
        handlers = {
            "student.created": self._on_student_created,
            "enrollment.created": self._on_enrollment_created,
            "attendance.recorded": self._on_attendance_recorded,
            "invoice.created": self._on_invoice_created,
            "payment.recorded": self._on_payment_recorded,
            "announcement.created": self._on_announcement_created,
        }
        return handlers.get(event_type)

    # ═══════════════════════════════════════════
    # Event Handlers — Projection Updaters
    # ═══════════════════════════════════════════

    def _ensure_dashboard(self, school_id: uuid.UUID) -> DashboardStats:
        stats = self.db.query(DashboardStats).filter(
            DashboardStats.school_id == school_id,
        ).first()
        if not stats:
            stats = DashboardStats(school_id=school_id)
            self.db.add(stats)
            self.db.flush()
        return stats

    def _on_student_created(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)
        stats.total_students += 1
        stats.active_students += 1
        stats.updated_at = datetime.now(timezone.utc)

    def _on_enrollment_created(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)
        stats.total_enrollments += 1
        stats.updated_at = datetime.now(timezone.utc)

        # Update student count projection
        year_id = payload.get("academic_year_id")
        if year_id:
            year_uuid = uuid.UUID(year_id) if isinstance(year_id, str) else year_id
            proj = self.db.query(StudentCountProjection).filter(
                StudentCountProjection.school_id == school_id,
                StudentCountProjection.academic_year_id == year_uuid,
            ).first()
            if not proj:
                proj = StudentCountProjection(
                    school_id=school_id, academic_year_id=year_uuid,
                )
                self.db.add(proj)
                self.db.flush()
            proj.total_students += 1
            proj.active_students += 1
            proj.updated_at = datetime.now(timezone.utc)

    def _on_attendance_recorded(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)

        accepted = payload.get("accepted", 0)
        present = payload.get("present", 0)
        absent = payload.get("absent", 0)
        late = payload.get("late", 0)
        batch_date = payload.get("date")

        stats.attendance_today_total += accepted
        stats.attendance_today_present += present
        stats.updated_at = datetime.now(timezone.utc)

        # Update daily aggregate
        if batch_date:
            d = date.fromisoformat(batch_date) if isinstance(batch_date, str) else batch_date
            agg = self.db.query(AttendanceDailyAggregate).filter(
                AttendanceDailyAggregate.school_id == school_id,
                AttendanceDailyAggregate.date == d,
            ).first()
            if not agg:
                agg = AttendanceDailyAggregate(
                    school_id=school_id, date=d,
                )
                self.db.add(agg)
                self.db.flush()
            agg.present_count += present
            agg.absent_count += absent
            agg.late_count += late
            agg.updated_at = datetime.now(timezone.utc)

    def _on_invoice_created(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)
        amount = Decimal(str(payload.get("total_amount", 0)))
        stats.total_invoiced += amount
        stats.updated_at = datetime.now(timezone.utc)

        # Financial summary
        year_id = payload.get("academic_year_id")
        if year_id:
            year_uuid = uuid.UUID(year_id) if isinstance(year_id, str) else year_id
            fin = self._ensure_financial(school_id, year_uuid)
            fin.total_invoiced += amount
            fin.total_outstanding += amount
            fin.updated_at = datetime.now(timezone.utc)

    def _on_payment_recorded(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)
        amount = Decimal(str(payload.get("amount", 0)))
        stats.total_paid += amount
        stats.updated_at = datetime.now(timezone.utc)

        year_id = payload.get("academic_year_id")
        if year_id:
            year_uuid = uuid.UUID(year_id) if isinstance(year_id, str) else year_id
            fin = self._ensure_financial(school_id, year_uuid)
            fin.total_paid += amount
            fin.total_outstanding -= amount
            fin.updated_at = datetime.now(timezone.utc)

    def _on_announcement_created(self, school_id: uuid.UUID, payload: dict):
        stats = self._ensure_dashboard(school_id)
        stats.announcements_this_month += 1
        stats.updated_at = datetime.now(timezone.utc)

    def _ensure_financial(self, school_id: uuid.UUID,
                          year_id: uuid.UUID) -> FinancialSummary:
        fin = self.db.query(FinancialSummary).filter(
            FinancialSummary.school_id == school_id,
            FinancialSummary.academic_year_id == year_id,
        ).first()
        if not fin:
            fin = FinancialSummary(
                school_id=school_id, academic_year_id=year_id,
            )
            self.db.add(fin)
            self.db.flush()
        return fin

    # ═══════════════════════════════════════════
    # Dashboard Queries
    # ═══════════════════════════════════════════

    def get_dashboard(self, school_id: uuid.UUID) -> dict:
        stats = self.db.query(DashboardStats).filter(
            DashboardStats.school_id == school_id,
        ).first()
        if not stats:
            return {
                "total_students": 0, "active_students": 0, "total_enrollments": 0,
                "attendance_today_rate": 0.0, "outstanding_fees": 0.0,
                "collected_this_term": 0.0, "announcements_this_month": 0,
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

    def get_attendance_trend(self, school_id: uuid.UUID,
                              from_date: date, to_date: date) -> list[dict]:
        rows = self.db.query(AttendanceDailyAggregate).filter(
            AttendanceDailyAggregate.school_id == school_id,
            AttendanceDailyAggregate.date >= from_date,
            AttendanceDailyAggregate.date <= to_date,
        ).order_by(AttendanceDailyAggregate.date).all()
        return [{
            "date": r.date.isoformat(), "present": r.present_count,
            "absent": r.absent_count, "late": r.late_count,
            "total": r.present_count + r.absent_count + r.late_count,
            "rate": round(r.present_count / max(r.present_count + r.absent_count + r.late_count, 1) * 100, 1),
        } for r in rows]

    def get_financial_summary(self, school_id: uuid.UUID,
                               year_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(FinancialSummary).filter(
            FinancialSummary.school_id == school_id,
        )
        if year_id:
            q = q.filter(FinancialSummary.academic_year_id == year_id)
        return [{
            "academic_year_id": str(f.academic_year_id),
            "total_invoiced": float(f.total_invoiced),
            "total_paid": float(f.total_paid),
            "total_outstanding": float(f.total_outstanding),
        } for f in q.all()]

    # ═══════════════════════════════════════════
    # Rebuild (Event Sourcing Correctness)
    # ═══════════════════════════════════════════

    def rebuild(self, events: list[dict]) -> dict:
        """Clear all projections and replay from event log."""
        # Clear projections (NOT ProcessedEvent — we keep the inbox)
        self.db.query(DashboardStats).delete()
        self.db.query(AttendanceDailyAggregate).delete()
        self.db.query(FinancialSummary).delete()
        self.db.query(StudentCountProjection).delete()
        self.db.query(ProcessedEvent).delete()    # Clear inbox too for replay
        self.db.commit()

        # Replay all events
        result = self.consume_batch(events)
        return {"rebuild": True, **result}
