"""
Attendance Sync Engine — Idempotent, Batch-Optimized, Conflict-Resolving
=========================================================================

Design principles:
1. Pre-fetch ALL existing records for the batch in 1 query (no per-event DB hits)
2. Pre-fetch ALL processed client_event_ids in 1 query
3. Process events in-memory, build insert/update lists
4. Execute in single transaction
5. Record SyncBatch for dedup

Conflict resolution: latest last_modified_at wins.
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case

from app.models.attendance import AttendanceRecord, SyncBatch, ProcessedClientEvent


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    # ───────────── Sync Engine ─────────────

    def process_sync_batch(
        self,
        school_id: uuid.UUID,
        device_id: str,
        sync_batch_id: str,
        events: list[dict],
        marked_by: uuid.UUID = None,
    ) -> dict:
        """
        Process offline sync batch idempotently.

        Returns {accepted, updated, ignored, batch_id, already_processed}.
        """
        # Step 0: Check batch-level idempotency
        existing_batch = self.db.query(SyncBatch).filter(
            SyncBatch.school_id == school_id,
            SyncBatch.device_id == device_id,
            SyncBatch.sync_batch_id == sync_batch_id,
        ).first()

        if existing_batch:
            return {
                "accepted": existing_batch.accepted_count,
                "updated": existing_batch.updated_count,
                "ignored": existing_batch.ignored_count,
                "total": existing_batch.total_events,
                "batch_id": str(existing_batch.id),
                "already_processed": True,
            }

        # Step 1: Collect all (student_id, date) and client_event_ids from batch
        student_date_pairs = set()
        client_event_ids = set()
        for e in events:
            student_date_pairs.add((uuid.UUID(str(e["student_id"])), e["date"]))
            if e.get("client_event_id"):
                client_event_ids.add(e["client_event_id"])

        # Step 2: Pre-fetch existing attendance records
        # For large batches, query by school + date range, then filter in-memory
        existing_records = {}
        if student_date_pairs:
            dates = {d for _, d in student_date_pairs}
            date_list = [d if isinstance(d, date) else date.fromisoformat(str(d)) for d in dates]
            rows = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.school_id == school_id,
                AttendanceRecord.date.in_(date_list),
            ).all()
            for r in rows:
                key = (r.student_id, r.date)
                if key in student_date_pairs:
                    existing_records[key] = r

        # Step 3: Pre-fetch processed client events (chunked for large batches)
        processed_events = set()
        if client_event_ids:
            eid_list = list(client_event_ids)
            chunk_size = 500
            for i in range(0, len(eid_list), chunk_size):
                chunk = eid_list[i:i + chunk_size]
                rows = self.db.query(ProcessedClientEvent.client_event_id).filter(
                    ProcessedClientEvent.school_id == school_id,
                    ProcessedClientEvent.device_id == device_id,
                    ProcessedClientEvent.client_event_id.in_(chunk),
                ).all()
                processed_events.update(r[0] for r in rows)

        # Step 4: Process events in-memory
        accepted = 0
        updated = 0
        ignored = 0
        new_records = []
        new_processed = []

        for e in events:
            client_eid = e.get("client_event_id")

            # Event-level idempotency
            if client_eid and client_eid in processed_events:
                ignored += 1
                continue

            student_id = uuid.UUID(str(e["student_id"]))
            class_id = uuid.UUID(str(e["class_id"]))
            evt_date = e["date"] if isinstance(e["date"], date) else date.fromisoformat(str(e["date"]))
            evt_status = e["status"]

            # Parse last_modified_at
            lma = e.get("last_modified_at")
            if isinstance(lma, datetime):
                last_mod = lma if lma.tzinfo else lma.replace(tzinfo=timezone.utc)
            elif isinstance(lma, str):
                last_mod = datetime.fromisoformat(lma)
                if last_mod.tzinfo is None:
                    last_mod = last_mod.replace(tzinfo=timezone.utc)
            else:
                last_mod = datetime.now(timezone.utc)

            key = (student_id, evt_date)
            existing = existing_records.get(key)

            if existing is None:
                # Insert new
                rec = AttendanceRecord(
                    school_id=school_id, student_id=student_id,
                    class_id=class_id, date=evt_date, status=evt_status,
                    marked_by_user_id=marked_by, device_id=device_id,
                    client_event_id=client_eid, last_modified_at=last_mod,
                )
                self.db.add(rec)
                existing_records[key] = rec  # Track for subsequent events in same batch
                accepted += 1
            else:
                # Conflict resolution: latest wins
                stored_lma = existing.last_modified_at
                if stored_lma and stored_lma.tzinfo is None:
                    stored_lma = stored_lma.replace(tzinfo=timezone.utc)

                if last_mod > (stored_lma or datetime.min.replace(tzinfo=timezone.utc)):
                    existing.status = evt_status
                    existing.last_modified_at = last_mod
                    existing.marked_by_user_id = marked_by
                    existing.device_id = device_id
                    existing.client_event_id = client_eid
                    updated += 1
                else:
                    ignored += 1

            # Mark client event as processed
            if client_eid and client_eid not in processed_events:
                pce = ProcessedClientEvent(
                    school_id=school_id, device_id=device_id,
                    client_event_id=client_eid,
                )
                self.db.add(pce)
                processed_events.add(client_eid)

        # Step 5: Record sync batch
        batch = SyncBatch(
            school_id=school_id, device_id=device_id,
            sync_batch_id=sync_batch_id,
            total_events=len(events),
            accepted_count=accepted, updated_count=updated,
            ignored_count=ignored,
        )
        self.db.add(batch)
        self.db.commit()

        return {
            "accepted": accepted,
            "updated": updated,
            "ignored": ignored,
            "total": len(events),
            "batch_id": str(batch.id),
            "already_processed": False,
        }

    # ───────────── Online Marking ─────────────

    def mark_attendance(
        self,
        school_id: uuid.UUID,
        records: list[dict],
        marked_by: uuid.UUID = None,
    ) -> dict:
        """Bulk online marking — uses sync engine with auto-generated batch."""
        batch_id = f"online-{uuid.uuid4()}"
        device_id = "web"
        for r in records:
            if "client_event_id" not in r:
                r["client_event_id"] = str(uuid.uuid4())
            if "last_modified_at" not in r:
                r["last_modified_at"] = datetime.now(timezone.utc)
        return self.process_sync_batch(school_id, device_id, batch_id, records, marked_by)

    # ───────────── Reporting ─────────────

    def daily_summary(self, school_id: uuid.UUID, target_date: date,
                      class_id: uuid.UUID = None) -> dict:
        q = self.db.query(
            AttendanceRecord.status,
            func.count(AttendanceRecord.id).label("count"),
        ).filter(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.date == target_date,
        )
        if class_id:
            q = q.filter(AttendanceRecord.class_id == class_id)
        q = q.group_by(AttendanceRecord.status)

        result = {"P": 0, "A": 0, "L": 0, "total": 0, "date": target_date.isoformat()}
        for status, count in q.all():
            result[status] = count
            result["total"] += count
        if result["total"] > 0:
            result["attendance_rate"] = round(result["P"] / result["total"] * 100, 1)
        else:
            result["attendance_rate"] = 0.0
        return result

    def student_trend(self, school_id: uuid.UUID, student_id: uuid.UUID,
                      from_date: date, to_date: date) -> dict:
        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.date >= from_date,
            AttendanceRecord.date <= to_date,
        ).order_by(AttendanceRecord.date).all()

        days = [{"date": r.date.isoformat(), "status": r.status} for r in records]
        total = len(records)
        present = sum(1 for r in records if r.status == "P")
        return {
            "student_id": str(student_id),
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "total_days": total,
            "present": present,
            "absent": sum(1 for r in records if r.status == "A"),
            "late": sum(1 for r in records if r.status == "L"),
            "attendance_rate": round(present / total * 100, 1) if total else 0.0,
            "days": days,
        }

    def class_summary(self, school_id: uuid.UUID, class_id: uuid.UUID,
                      from_date: date, to_date: date) -> dict:
        q = self.db.query(
            AttendanceRecord.date,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(case((AttendanceRecord.status == "P", 1), else_=0)).label("present"),
            func.sum(case((AttendanceRecord.status == "A", 1), else_=0)).label("absent"),
            func.sum(case((AttendanceRecord.status == "L", 1), else_=0)).label("late"),
        ).filter(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.date >= from_date,
            AttendanceRecord.date <= to_date,
        ).group_by(AttendanceRecord.date).order_by(AttendanceRecord.date)

        days = []
        for row in q.all():
            total = row.total or 0
            present = row.present or 0
            days.append({
                "date": row.date.isoformat(),
                "total": total, "present": present,
                "absent": row.absent or 0, "late": row.late or 0,
                "rate": round(present / total * 100, 1) if total else 0.0,
            })
        return {
            "class_id": str(class_id),
            "from": from_date.isoformat(), "to": to_date.isoformat(),
            "days": days,
        }

    # ───────────── Daily Records (per-student) ─────────────

    def daily_records(self, school_id: uuid.UUID, target_date: date,
                      class_id: uuid.UUID) -> list[dict]:
        """Return individual attendance records for a class on a given date."""
        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.date == target_date,
        ).order_by(AttendanceRecord.student_id).all()

        return [
            {
                "id": str(r.id),
                "student_id": str(r.student_id),
                "class_id": str(r.class_id),
                "date": r.date.isoformat(),
                "status": r.status,
                "marked_by_user_id": str(r.marked_by_user_id) if r.marked_by_user_id else None,
                "last_modified_at": r.last_modified_at.isoformat() if r.last_modified_at else None,
            }
            for r in records
        ]

    # ───────────── Sync Batch List ─────────────

    def list_sync_batches(self, school_id: uuid.UUID, limit: int = 20) -> list[dict]:
        """Return recent sync batches for admin debugging."""
        batches = self.db.query(SyncBatch).filter(
            SyncBatch.school_id == school_id,
        ).order_by(SyncBatch.received_at.desc()).limit(limit).all()

        return [
            {
                "id": str(b.id),
                "device_id": b.device_id,
                "sync_batch_id": b.sync_batch_id,
                "received_at": b.received_at.isoformat(),
                "total_events": b.total_events,
                "accepted_count": b.accepted_count,
                "updated_count": b.updated_count,
                "ignored_count": b.ignored_count,
            }
            for b in batches
        ]
