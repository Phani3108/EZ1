"""Q-007 (Phase 4) — concurrency invariants for academics.

Same design choice as the finance concurrency tests: deterministic
two-session interleaves rather than `threading.Thread`. SQLite +
StaticPool serializes writes through one connection, so real
multi-thread races can't materialize; the deterministic version
exercises the same logical scenarios (idempotency dedup,
already-processed return paths, fan-out invariants).

The endpoints under test:
  * `AttendanceService.process_sync_batch` — batch idempotency on
    `(school_id, device_id, sync_batch_id)` and per-event idempotency
    on `client_event_id`.
  * `AssessmentService.bulk_upsert_marks` — per-(assessment, student)
    upsert, with a guarantee that two batches submitting the same
    (assessment, student) pair don't create duplicate rows.
"""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_concurrency.db")
os.environ.setdefault("REPORTING_DATABASE_URL", "sqlite:///./test_academics_concurrency_r.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine_and_factory():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def db(engine_and_factory):
    _, SessionLocal = engine_and_factory
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


SCHOOL_A = uuid.uuid4()


def _student(db, code="STU001"):
    from app.services.student_service import StudentService
    return StudentService(db).create_student(
        school_id=SCHOOL_A,
        student_code=code,
        first_name="John",
        last_name="Doe",
        dob=date(2012, 5, 15),
        gender="MALE",
    )


def _class(db, name="Grade 6 A"):
    from app.models.school import AcademicYear, Class
    year = AcademicYear(
        school_id=SCHOOL_A, name="2026",
        start_date=date(2026, 1, 15), end_date=date(2026, 12, 15),
        is_active=True,
    )
    db.add(year)
    db.flush()
    cls = Class(school_id=SCHOOL_A, name=name, section="A")
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


# ════════════════════════════════════════════════════════════════
# Attendance — batch idempotency under repeated submission
# ════════════════════════════════════════════════════════════════


class TestAttendanceBatchIdempotency:

    def test_same_batch_id_yields_one_set_of_records(self, engine_and_factory, db):
        _, SessionLocal = engine_and_factory
        from app.services.attendance_service import AttendanceService

        s_a = _student(db, code="A001")
        cls = _class(db)
        sid = uuid.UUID(s_a["id"])
        device = "tablet-42"
        batch_id = f"batch-{uuid.uuid4()}"
        # 5 events across 5 distinct dates → 5 attendance rows.
        events = [
            {"student_id": str(sid), "class_id": str(cls.id),
             "date": f"2026-03-{15 + i:02d}", "status": "P",
             "client_event_id": f"evt-{i}"}
            for i in range(5)
        ]

        svc = AttendanceService(db)
        r1 = svc.process_sync_batch(SCHOOL_A, device, batch_id, events)
        assert r1["already_processed"] is False
        assert r1["accepted"] == 5

        # Submit the SAME batch a second time.
        r2 = svc.process_sync_batch(SCHOOL_A, device, batch_id, events)
        assert r2["already_processed"] is True
        assert r2["accepted"] == 5  # counters from the original processing

        # Final state: 5 attendance rows, 0 duplicates.
        from app.models.attendance import AttendanceRecord
        fresh = SessionLocal()
        try:
            rows = fresh.query(AttendanceRecord).filter(
                AttendanceRecord.school_id == SCHOOL_A,
                AttendanceRecord.student_id == sid,
            ).all()
            assert len(rows) == 5  # one per distinct date; no duplicates from rerun
        finally:
            fresh.close()

    def test_two_sessions_same_batch_dedupe(self, engine_and_factory, db):
        """Two sessions submit the SAME (device_id, batch_id) — the
        second must return already_processed=True."""
        _, SessionLocal = engine_and_factory
        from app.services.attendance_service import AttendanceService

        s_a = _student(db, code="A001")
        cls = _class(db)
        sid = uuid.UUID(s_a["id"])
        device = "tablet-99"
        batch_id = f"batch-{uuid.uuid4()}"
        events = [
            {"student_id": str(sid), "class_id": str(cls.id),
             "date": "2026-03-15", "status": "P",
             "client_event_id": "evt-0"}
        ]

        s1 = SessionLocal()
        s2 = SessionLocal()
        try:
            r1 = AttendanceService(s1).process_sync_batch(
                SCHOOL_A, device, batch_id, events,
            )
            assert r1["already_processed"] is False

            r2 = AttendanceService(s2).process_sync_batch(
                SCHOOL_A, device, batch_id, events,
            )
            assert r2["already_processed"] is True
        finally:
            s1.close()
            s2.close()

    def test_per_event_idempotency_via_client_event_id(self, engine_and_factory, db):
        """Distinct sync_batch_id's submitting overlapping client_event_ids:
        the duplicate events are filtered (not double-recorded)."""
        _, SessionLocal = engine_and_factory
        from app.services.attendance_service import AttendanceService

        s_a = _student(db, code="A001")
        cls = _class(db)
        sid = uuid.UUID(s_a["id"])
        device = "tablet-55"

        evt_id = f"evt-{uuid.uuid4()}"
        # First batch.
        AttendanceService(db).process_sync_batch(
            SCHOOL_A, device, "batch-1",
            [{"student_id": str(sid), "class_id": str(cls.id),
              "date": "2026-03-15", "status": "P",
              "client_event_id": evt_id}],
        )

        # Second batch with the SAME client_event_id but different batch_id.
        # The per-event idempotency layer must skip it.
        r2 = AttendanceService(db).process_sync_batch(
            SCHOOL_A, device, "batch-2",
            [{"student_id": str(sid), "class_id": str(cls.id),
              "date": "2026-03-15", "status": "A",  # Trying to change to A!
              "client_event_id": evt_id}],
        )
        assert r2["already_processed"] is False
        # Either ignored or accepted but not double-counted — depends on
        # service semantics. The invariant: exactly one record exists.
        from app.models.attendance import AttendanceRecord
        fresh = SessionLocal()
        try:
            rows = fresh.query(AttendanceRecord).filter(
                AttendanceRecord.school_id == SCHOOL_A,
                AttendanceRecord.student_id == sid,
                AttendanceRecord.date == date(2026, 3, 15),
            ).all()
            assert len(rows) == 1
        finally:
            fresh.close()


# ════════════════════════════════════════════════════════════════
# Marks bulk — per-(assessment, student) upsert idempotency
# ════════════════════════════════════════════════════════════════


class TestMarksBulkIdempotency:

    def _assessment(self, db, cls):
        from app.models.assessment import Assessment
        a = Assessment(
            school_id=str(SCHOOL_A),
            class_id=str(cls.id),
            subject_id=str(uuid.uuid4()),
            academic_year_id=str(uuid.uuid4()),
            term_id=str(uuid.uuid4()),
            name="Mid-term Math",
            assessment_type="EXAM",
            max_marks=100,
            date=date(2026, 3, 15),
            created_by=str(uuid.uuid4()),
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    def test_bulk_upsert_dedupes_repeat_submission(self, engine_and_factory, db):
        """Two separate bulk submissions with the SAME (assessment, student)
        marks should not create duplicate Mark rows — the unique constraint
        enforces upsert semantics."""
        _, SessionLocal = engine_and_factory
        from app.services.assessment_service import AssessmentService

        cls = _class(db)
        s_a = _student(db, code="A001")
        a = self._assessment(db, cls)

        svc = AssessmentService(db)
        marks = [{"student_id": s_a["id"], "marks": 85}]

        r1 = svc.bulk_upsert_marks(
            school_id=SCHOOL_A,
            assessment_id=a.id,
            marks_data=marks,
            graded_by=uuid.uuid4(),
        )
        assert r1["accepted"] == 1
        assert r1["updated"] == 0

        # Submit again with a different mark — should update, not insert.
        marks2 = [{"student_id": s_a["id"], "marks": 90}]
        r2 = svc.bulk_upsert_marks(
            school_id=SCHOOL_A,
            assessment_id=a.id,
            marks_data=marks2,
            graded_by=uuid.uuid4(),
        )
        assert r2["updated"] == 1
        assert r2["accepted"] == 0
        # Invariant: exactly ONE Mark row for this (assessment, student).
        from app.models.assessment import Mark
        fresh = SessionLocal()
        try:
            rows = fresh.query(Mark).filter(
                Mark.school_id == str(SCHOOL_A),
                Mark.assessment_id == str(a.id),
                Mark.student_id == s_a["id"],
            ).all()
            assert len(rows) == 1, \
                f"Mark double-recorded: {len(rows)} rows"
            assert float(rows[0].marks) == 90.0  # latest value wins
        finally:
            fresh.close()


# ════════════════════════════════════════════════════════════════
# Sync-batch fan-out — 50 distinct batches; aggregate invariants
# ════════════════════════════════════════════════════════════════


class TestSyncBatchFanOut:

    def test_fifty_batches_no_double_count(self, engine_and_factory, db):
        from app.services.attendance_service import AttendanceService
        from app.models.attendance import AttendanceRecord, SyncBatch

        cls = _class(db)
        # 50 students, one batch per student.
        students = [_student(db, code=f"FAN{i:03d}") for i in range(50)]
        device = "fan-tablet"
        svc = AttendanceService(db)

        for i, s in enumerate(students):
            svc.process_sync_batch(
                SCHOOL_A, device, f"batch-fan-{i}",
                [{"student_id": s["id"], "class_id": str(cls.id),
                  "date": "2026-03-15", "status": "P",
                  "client_event_id": f"evt-fan-{i}"}],
            )

        # Re-submit the same 50 batches — all should dedupe.
        for i, s in enumerate(students):
            r = svc.process_sync_batch(
                SCHOOL_A, device, f"batch-fan-{i}",
                [{"student_id": s["id"], "class_id": str(cls.id),
                  "date": "2026-03-15", "status": "P",
                  "client_event_id": f"evt-fan-{i}"}],
            )
            assert r["already_processed"] is True

        # Invariants: 50 batches, 50 attendance records, 0 duplicates.
        from sqlalchemy.orm import sessionmaker
        _, SessionLocal = engine_and_factory
        fresh = SessionLocal()
        try:
            batches = fresh.query(SyncBatch).filter(
                SyncBatch.school_id == SCHOOL_A,
            ).count()
            records = fresh.query(AttendanceRecord).filter(
                AttendanceRecord.school_id == SCHOOL_A,
            ).count()
            assert batches == 50
            assert records == 50
        finally:
            fresh.close()
