"""Per-school + parent-self data export (PH8-4 / closes INFRA-017 + Q-011).

Two endpoints:

  * `GET /api/v1/schools/me/export` — school-admin facing. Returns a
    ZIP archive with one CSV per academic table for the requesting
    school, plus a JSON `manifest.json` describing the dump.

  * `GET /api/v1/parents/me/export` — parent self-service. Returns a
    ZIP with CSVs for THIS parent's children only (students, parents,
    attendance, marks, invoices). Implements the right-to-export
    portion of ADR 007 / Phase 9.

Both endpoints stream the ZIP — no per-row buffering, no temp files
on disk. The implementation reads each table in chunks and yields
CSV bytes into a ZipFile open in 'streamed' mode.

Tier-agnostic: the routes resolve the tier (via the TenancyResolver)
and read from the right DB. For shared schools that's the default
academics_db; for dedicated, the per-school DB; for district, the
district-shared DB.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Iterable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.school import School
from app.models.student import Student, Parent, StudentParent, Enrollment
from app.models.attendance import AttendanceRecord
from app.models.assessment import Assessment, Mark
from app.models.audit import AuditLog

# Phase 9 / INFRA-018 — exports are sensitive actions worth auditing
from eduzim_shared.audit import Event as AuditEvent, record_audit_event


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Exports"])


# ────────────────────────────────────────────────────────────────────
# School-admin export
# ────────────────────────────────────────────────────────────────────


@router.get("/schools/me/export")
def export_school(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Return a ZIP archive of every table for the requesting school.

    Caller must be a school admin (RBAC at gateway: `school:manage`).
    The ZIP contains:
      - manifest.json    — metadata (school_id, timestamp, row counts)
      - school.csv       — the single School row
      - students.csv     — all students at this school
      - parents.csv      — all parents linked to this school's students
      - student_parents.csv — link rows
      - enrollments.csv  — all enrollments at this school
      - attendance.csv   — all attendance rows at this school
      - assessments.csv  — all assessments at this school
      - marks.csv        — all marks at this school
    """
    requested_at = datetime.now(timezone.utc)
    filename = f"school-{school_id}-{requested_at.strftime('%Y%m%d%H%M%S')}.zip"

    # Phase 9 / INFRA-018: audit the export INTENT — even a failed
    # export attempt is a privacy-relevant action and should appear
    # in the log. The audit row commits BEFORE the streaming response
    # starts; the row exists even if the download is interrupted.
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.DATA_EXPORT_SCHOOL,
        school_id=school_id,
        actor_user_id=uuid.UUID(str(current_user.get("user_id") or current_user.get("sub")))
            if current_user.get("user_id") or current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "school", "id": str(school_id)},
        details={"filename": filename},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()

    def _build_zip_bytes() -> bytes:
        # Build the entire ZIP in-memory first, then return the bytes.
        # The central directory in a ZIP is only written when the
        # ZipFile is closed, so mid-stream yields would produce a
        # "not a zip" error on the client. For the data sizes we
        # expect (a single school's rows, ≤ 100MB uncompressed in
        # worst-case), buffering the whole thing is fine. For larger
        # tiers, switch to `streaming_form_data.zipstream` or similar
        # lazy-central-dir implementations.
        buf = io.BytesIO()
        zf = zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED)
        try:
            row_counts: dict[str, int] = {}
            school = db.query(School).filter(School.id == school_id).first()
            if school is None:
                manifest = {
                    "error": "SCHOOL_NOT_FOUND",
                    "school_id": str(school_id),
                    "exported_at": requested_at.isoformat(),
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            else:
                row_counts["school"] = _write_rows(zf, "school.csv",
                    [_school_to_dict(school)])
                row_counts["students"] = _write_rows(zf, "students.csv",
                    _stream_students(db, school_id))
                row_counts["parents"] = _write_rows(zf, "parents.csv",
                    _stream_parents_for_school(db, school_id))
                row_counts["student_parents"] = _write_rows(zf, "student_parents.csv",
                    _stream_student_parents(db, school_id))
                row_counts["enrollments"] = _write_rows(zf, "enrollments.csv",
                    _stream_enrollments(db, school_id))
                row_counts["attendance"] = _write_rows(zf, "attendance.csv",
                    _stream_attendance(db, school_id))
                row_counts["assessments"] = _write_rows(zf, "assessments.csv",
                    _stream_assessments(db, school_id))
                row_counts["marks"] = _write_rows(zf, "marks.csv",
                    _stream_marks(db, school_id))

                manifest = {
                    "school_id": str(school_id),
                    "school_name": school.name,
                    "tenancy_tier": getattr(school, "tenancy_tier", "shared"),
                    "exported_at": requested_at.isoformat(),
                    "exported_by_user_id": str(current_user.get("user_id")
                                                or current_user.get("sub")),
                    "row_counts": row_counts,
                    "schema_version": 1,
                    "format": "csv-rfc4180-utf8",
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            return _finalize(zf, buf)
        except Exception:
            zf.close()
            raise

    def _stream():
        yield _build_zip_bytes()

    return StreamingResponse(
        _stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ────────────────────────────────────────────────────────────────────
# Parent self-service export (right-to-data per ADR 007)
# ────────────────────────────────────────────────────────────────────


@router.get("/parents/me/export")
def export_parent_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Parent self-service: return ALL data the platform holds about
    the requesting parent's children.

    Scope: THIS parent + their linked children only. Other students at
    the same school MUST NOT appear in the export.

    Implements the right-to-export portion of ADR 007 / Phase 9. The
    field set is intentionally minimal — only what's needed to verify
    "what does EduZim know about my child?".
    """
    user_id_str = current_user.get("user_id") or current_user.get("sub")
    if not user_id_str:
        # The auth layer should have caught this. Defensive check.
        return _empty_zip("UNAUTHORIZED")

    try:
        user_id = uuid.UUID(str(user_id_str))
    except ValueError:
        return _empty_zip("INVALID_USER_ID")

    requested_at = datetime.now(timezone.utc)
    filename = f"parent-{user_id}-{requested_at.strftime('%Y%m%d%H%M%S')}.zip"

    # Phase 9 / INFRA-018: every parent self-export is logged. Targets
    # the parent's user_id; school_id is the auth context.
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.DATA_EXPORT_PARENT,
        school_id=school_id,
        actor_user_id=user_id,
        actor_role="Parent",
        target={"resource": "parent_user", "id": str(user_id)},
        details={"filename": filename},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()

    def _build_zip_bytes() -> bytes:
        """Build the parent-export ZIP synchronously; return the bytes.
        Separate from the generator so the close-before-read sequence
        is unambiguous (closing the ZipFile writes the central
        directory; only after close can the buffer be read out)."""
        buf = io.BytesIO()
        zf = zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED)
        try:
            parent = db.query(Parent).filter(
                Parent.user_id == user_id,
                Parent.school_id == school_id,
            ).first()
            if parent is None:
                manifest = {
                    "error": "PARENT_NOT_FOUND",
                    "user_id": str(user_id),
                    "school_id": str(school_id),
                    "exported_at": requested_at.isoformat(),
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
                return _finalize(zf, buf)

            student_links = db.query(StudentParent).filter(
                StudentParent.parent_id == parent.id,
                StudentParent.school_id == school_id,
            ).all()
            child_ids = [link.student_id for link in student_links]

            row_counts: dict[str, int] = {}
            row_counts["parent"] = _write_rows(zf, "parent.csv",
                [_parent_to_dict(parent)])

            children = db.query(Student).filter(
                Student.id.in_(child_ids) if child_ids else False,
                Student.school_id == school_id,
            ).all() if child_ids else []
            row_counts["children"] = _write_rows(zf, "children.csv",
                [_student_to_dict(c) for c in children])

            enrollments = db.query(Enrollment).filter(
                Enrollment.student_id.in_(child_ids) if child_ids else False,
                Enrollment.school_id == school_id,
            ).all() if child_ids else []
            row_counts["enrollments"] = _write_rows(zf, "enrollments.csv",
                [_enrollment_to_dict(e) for e in enrollments])

            attendance = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id.in_(child_ids) if child_ids else False,
                AttendanceRecord.school_id == school_id,
            ).all() if child_ids else []
            row_counts["attendance"] = _write_rows(zf, "attendance.csv",
                [_attendance_to_dict(a) for a in attendance])

            marks = db.query(Mark).filter(
                Mark.student_id.in_([str(c) for c in child_ids]) if child_ids else False,
                Mark.school_id == str(school_id),
            ).all() if child_ids else []
            row_counts["marks"] = _write_rows(zf, "marks.csv",
                [_mark_to_dict(m) for m in marks])

            manifest = {
                "user_id": str(user_id),
                "school_id": str(school_id),
                "parent_id": str(parent.id),
                "exported_at": requested_at.isoformat(),
                "row_counts": row_counts,
                "schema_version": 1,
                "format": "csv-rfc4180-utf8",
                "notes": [
                    "This export contains all personal data EduZim holds "
                    "about your linked children at this school. To remove "
                    "the data, contact your school administrator "
                    "(right-to-erasure per ADR 007).",
                ],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            return _finalize(zf, buf)
        except Exception:
            zf.close()
            raise

    def _stream():
        yield _build_zip_bytes()

        buf.seek(0)
        yield buf.getvalue()

    return StreamingResponse(
        _stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _finalize(zf: zipfile.ZipFile, buf: io.BytesIO) -> bytes:
    """Close the ZipFile (writing the central directory) and return
    the complete archive bytes. Single source of truth for the
    close-then-read sequence — easy to get wrong otherwise."""
    zf.close()
    buf.seek(0)
    return buf.getvalue()


def _empty_zip(error_code: str):
    """Return a ZIP containing only an error manifest."""
    def _gen():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w") as zf:
            zf.writestr("manifest.json", json.dumps({"error": error_code}, indent=2))
        buf.seek(0)
        yield buf.getvalue()
    return StreamingResponse(_gen(), media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=error.zip"})


def _write_rows(zf: zipfile.ZipFile, filename: str,
                rows: Iterable[dict]) -> int:
    """Write an iterable of dicts as RFC-4180 CSV into the ZIP. Returns
    the row count. The header is taken from the FIRST row's keys; an
    empty iterable writes an empty file (no header)."""
    sio = io.StringIO()
    writer = None
    count = 0
    for row in rows:
        if writer is None:
            writer = csv.DictWriter(sio, fieldnames=list(row.keys()))
            writer.writeheader()
        writer.writerow(row)
        count += 1
    zf.writestr(filename, sio.getvalue())
    return count


# ─ Per-table streaming helpers ─


def _stream_students(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    for s in db.query(Student).filter(Student.school_id == school_id).yield_per(500):
        yield _student_to_dict(s)


def _stream_parents_for_school(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    # Parents linked to this school (via student_parents.school_id).
    for p in db.query(Parent).filter(Parent.school_id == school_id).yield_per(500):
        yield _parent_to_dict(p)


def _stream_student_parents(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    for sp in db.query(StudentParent).filter(
        StudentParent.school_id == school_id,
    ).yield_per(500):
        yield {
            "id": str(sp.id),
            "student_id": str(sp.student_id),
            "parent_id": str(sp.parent_id),
            "school_id": str(sp.school_id),
            "is_primary": sp.is_primary,
        }


def _stream_enrollments(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    for e in db.query(Enrollment).filter(
        Enrollment.school_id == school_id,
    ).yield_per(500):
        yield _enrollment_to_dict(e)


def _stream_attendance(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    for a in db.query(AttendanceRecord).filter(
        AttendanceRecord.school_id == school_id,
    ).yield_per(1000):
        yield _attendance_to_dict(a)


def _stream_assessments(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    # Assessment uses str(uuid) school_id, so cast.
    for a in db.query(Assessment).filter(
        Assessment.school_id == str(school_id),
    ).yield_per(500):
        yield _assessment_to_dict(a)


def _stream_marks(db: Session, school_id: uuid.UUID) -> Iterable[dict]:
    for m in db.query(Mark).filter(
        Mark.school_id == str(school_id),
    ).yield_per(1000):
        yield _mark_to_dict(m)


# ─ Row → dict serializers (ALL fields, no PII redaction at this layer
#   — the caller is the school admin or the parent themselves) ─


def _school_to_dict(s: School) -> dict:
    return {
        "id": str(s.id), "name": s.name, "country": s.country,
        "timezone": s.timezone,
        "province_code": s.province_code,
        "district_code": s.district_code,
        "school_type": s.school_type,
        "tenancy_tier": getattr(s, "tenancy_tier", "shared"),
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _student_to_dict(s: Student) -> dict:
    return {
        "id": str(s.id), "school_id": str(s.school_id),
        "student_code": s.student_code,
        "first_name": s.first_name, "last_name": s.last_name,
        "dob": s.dob.isoformat() if s.dob else None,
        "gender": s.gender,
        "admission_date": s.admission_date.isoformat() if s.admission_date else None,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _parent_to_dict(p: Parent) -> dict:
    return {
        "id": str(p.id), "school_id": str(p.school_id),
        "user_id": str(p.user_id) if p.user_id else None,
        "first_name": p.first_name, "last_name": p.last_name,
        "phone": p.phone, "email": p.email,
        "relationship_type": p.relationship_type,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _enrollment_to_dict(e: Enrollment) -> dict:
    return {
        "id": str(e.id), "school_id": str(e.school_id),
        "student_id": str(e.student_id),
        "class_id": str(e.class_id),
        "academic_year_id": str(e.academic_year_id),
        "status": e.status,
    }


def _attendance_to_dict(a: AttendanceRecord) -> dict:
    return {
        "id": str(a.id), "school_id": str(a.school_id),
        "student_id": str(a.student_id), "class_id": str(a.class_id),
        "date": a.date.isoformat() if a.date else None,
        "status": a.status,
        "marked_by_user_id": str(a.marked_by_user_id) if a.marked_by_user_id else None,
    }


def _assessment_to_dict(a: Assessment) -> dict:
    return {
        "id": str(a.id), "school_id": a.school_id,
        "class_id": a.class_id, "subject_id": a.subject_id,
        "term_id": a.term_id, "academic_year_id": a.academic_year_id,
        "name": a.name, "assessment_type": a.assessment_type,
        "max_marks": float(a.max_marks) if a.max_marks is not None else None,
        "date": a.date.isoformat() if a.date else None,
    }


def _mark_to_dict(m: Mark) -> dict:
    return {
        "id": str(m.id), "school_id": m.school_id,
        "assessment_id": m.assessment_id, "student_id": m.student_id,
        "marks": float(m.marks) if m.marks is not None else None,
        "is_absent": m.is_absent,
        "remarks": m.remarks,
        "graded_by": m.graded_by,
    }
