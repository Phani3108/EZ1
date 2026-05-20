#!/usr/bin/env python3
"""Import EduZim master dataset into the microservice databases.

Reads ``scripts/data/eduzim_master.xlsx`` (produced by ``build_master_dataset.py``)
and seeds each service's database via SQLAlchemy Core.

Environment variables (any can be overridden individually):
  DATABASE_URL_BASE          (default: postgresql+psycopg2://eduzim:eduzim_secret@localhost:5432)
  DATABASE_URL_SCHOOL_DB     overrides school-service DB URL
  DATABASE_URL_STUDENT_DB    overrides student-service DB URL
  DATABASE_URL_FEES_DB       ...
  DATABASE_URL_ASSESSMENT_DB
  DATABASE_URL_ATTENDANCE_DB
  DATABASE_URL_COMMS_DB
  DATABASE_URL_AUTH_DB

Usage:
  python3 scripts/import_master.py                          # seed all services
  python3 scripts/import_master.py --services school,student
  python3 scripts/import_master.py --dry-run                # print counts only
  python3 scripts/import_master.py --workbook /path/to.xlsx
  python3 scripts/import_master.py --truncate               # wipe target tables first (dangerous)

The script is idempotent: it uses INSERT ... ON CONFLICT DO NOTHING (PostgreSQL)
or INSERT OR IGNORE (SQLite). Re-running will leave existing rows alone.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import openpyxl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ── workbook → service mapping ────────────────────────────────────────
SERVICE_DBS = {
    "school":     ("school_db",     "DATABASE_URL_SCHOOL_DB"),
    "student":    ("student_db",    "DATABASE_URL_STUDENT_DB"),
    "fees":       ("fees_db",       "DATABASE_URL_FEES_DB"),
    "assessment": ("assessment_db", "DATABASE_URL_ASSESSMENT_DB"),
    "attendance": ("attendance_db", "DATABASE_URL_ATTENDANCE_DB"),
    "comms":      ("comms_db",      "DATABASE_URL_COMMS_DB"),
}

BATCH_SIZE = 1000


def _resolve_url(service: str) -> str:
    dbname, env_key = SERVICE_DBS[service]
    if os.environ.get(env_key):
        return os.environ[env_key]
    base = os.environ.get(
        "DATABASE_URL_BASE",
        "postgresql+psycopg2://eduzim:eduzim_secret@localhost:5432",
    ).rstrip("/")
    return f"{base}/{dbname}"


def _engine(service: str) -> Engine:
    return create_engine(_resolve_url(service), future=True)


def _load_sheet(wb, name: str) -> tuple[list[str], list[list]]:
    ws = wb[name]
    rows = ws.iter_rows(values_only=True)
    headers = list(next(rows))
    data = [list(r) for r in rows if r is not None and any(c is not None for c in r)]
    return headers, data


def _is_sqlite(eng: Engine) -> bool:
    return eng.dialect.name == "sqlite"


def _on_conflict_clause(eng: Engine, columns: list[str], conflict_target: str) -> str:
    if _is_sqlite(eng):
        return ""  # caller uses INSERT OR IGNORE
    return f" ON CONFLICT ({conflict_target}) DO NOTHING"


def _bulk_insert(
    eng: Engine,
    table: str,
    cols: list[str],
    rows: Iterable[dict],
    conflict_target: str = "id",
    truncate: bool = False,
    dry_run: bool = False,
) -> int:
    rows = list(rows)
    if dry_run:
        print(f"  [dry-run] would insert {len(rows):>6} rows into {table}")
        return len(rows)
    if not rows:
        return 0
    with eng.begin() as conn:
        if truncate:
            conn.execute(text(f"DELETE FROM {table}"))
        prefix = "INSERT OR IGNORE INTO" if _is_sqlite(eng) else "INSERT INTO"
        col_list = ", ".join(cols)
        bind_list = ", ".join(f":{c}" for c in cols)
        suffix = _on_conflict_clause(eng, cols, conflict_target)
        stmt = text(f"{prefix} {table} ({col_list}) VALUES ({bind_list}){suffix}")
        for i in range(0, len(rows), BATCH_SIZE):
            conn.execute(stmt, rows[i : i + BATCH_SIZE])
    print(f"  ✓ inserted {len(rows):>6} rows into {table}")
    return len(rows)


def _row_dict(headers: list[str], row: list) -> dict:
    return {h: row[i] for i, h in enumerate(headers)}


def _stamp(d: dict, fields: tuple[str, ...] = ("created_at", "updated_at")) -> dict:
    now = datetime.now(timezone.utc)
    for f in fields:
        d.setdefault(f, now)
    return d


# ── per-service seeders ──────────────────────────────────────────────

def seed_school(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[school_db]")
    eng = _engine("school")

    # Provinces
    h, rows = _load_sheet(wb, "Provinces")
    payload = [{"code": r[h.index("code")], "name": r[h.index("name")],
                "region": r[h.index("region")], "capital": r[h.index("capital")],
                "country": "ZW", "created_at": datetime.now(timezone.utc)} for r in rows]
    _bulk_insert(eng, "provinces", list(payload[0].keys()), payload,
                 conflict_target="code", truncate=truncate, dry_run=dry_run)

    # Districts
    h, rows = _load_sheet(wb, "Districts")
    payload = [{"code": r[h.index("code")], "name": r[h.index("name")],
                "province_code": r[h.index("province_code")],
                "created_at": datetime.now(timezone.utc)} for r in rows]
    _bulk_insert(eng, "districts", list(payload[0].keys()), payload,
                 conflict_target="code", truncate=truncate, dry_run=dry_run)

    # Schools
    h, rows = _load_sheet(wb, "Schools")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append(_stamp({
            "id": d["id"], "name": d["name"], "country": "ZW",
            "timezone": "Africa/Harare",
            "province_code": d.get("province_code"),
            "district_code": d.get("district_code"),
            "school_type": d.get("type"),
            "principal_name": d.get("principal_name"),
            "address": d.get("address"),
            "phone": d.get("phone"),
            "email": d.get("email"),
            "founded_year": d.get("founded_year"),
            "is_active": True,
        }))
    _bulk_insert(eng, "schools", list(payload[0].keys()), payload,
                 conflict_target="id", truncate=truncate, dry_run=dry_run)

    # AcademicYears
    h, rows = _load_sheet(wb, "AcademicYears")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append(_stamp({
            "id": d["id"], "school_id": d["school_id"], "name": d["name"],
            "start_date": d["start_date"], "end_date": d["end_date"],
            "is_active": bool(d.get("is_active")),
        }))
    _bulk_insert(eng, "academic_years", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Terms
    h, rows = _load_sheet(wb, "Terms")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "academic_year_id": d["academic_year_id"], "name": d["name"],
            "start_date": d["start_date"], "end_date": d["end_date"],
            "is_active": bool(d.get("is_active")),
            "created_at": datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "terms", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Subjects
    h, rows = _load_sheet(wb, "Subjects")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "name": d["name"], "code": d["code"],
            "is_active": bool(d.get("is_active", True)),
            "created_at": datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "subjects", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Classes
    h, rows = _load_sheet(wb, "Classes")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append(_stamp({
            "id": d["id"], "school_id": d["school_id"],
            "name": d["name"], "section": d.get("section") or "A",
            "capacity": d.get("capacity"), "is_active": bool(d.get("is_active", True)),
        }))
    _bulk_insert(eng, "classes", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # ClassTeacherAssignments
    h, rows = _load_sheet(wb, "ClassTeacherAssignments")
    payload = [{
        "id": r[h.index("id")], "school_id": r[h.index("school_id")],
        "class_id": r[h.index("class_id")],
        "teacher_user_id": r[h.index("teacher_id")],
        "academic_year_id": r[h.index("academic_year_id")],
        "created_at": datetime.now(timezone.utc),
    } for r in rows]
    _bulk_insert(eng, "class_teacher_assignments", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


def seed_student(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[student_db]")
    eng = _engine("student")

    # Students
    h, rows = _load_sheet(wb, "Students")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append(_stamp({
            "id": d["id"], "school_id": d["school_id"],
            "student_code": d["student_code"],
            "first_name": d["first_name"], "last_name": d["last_name"],
            "dob": d.get("dob"), "gender": d.get("gender"),
            "admission_date": d.get("admission_date"),
            "status": d.get("status") or "ACTIVE",
        }))
    _bulk_insert(eng, "students", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Parents
    h, rows = _load_sheet(wb, "Parents")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "first_name": d["first_name"], "last_name": d["last_name"],
            "phone": d["phone"], "email": d.get("email"),
            "relationship_type": d.get("relationship_type") or "GUARDIAN",
            "created_at": datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "parents", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # StudentParents (link)
    h, rows = _load_sheet(wb, "StudentParents")
    payload = [{
        "id": r[h.index("id")], "school_id": r[h.index("school_id")],
        "student_id": r[h.index("student_id")],
        "parent_id": r[h.index("parent_id")],
        "is_primary": False,
        "created_at": datetime.now(timezone.utc),
    } for r in rows]
    _bulk_insert(eng, "student_parents", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Enrollments (schema has no updated_at — stamp created_at only)
    h, rows = _load_sheet(wb, "Enrollments")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "student_id": d["student_id"], "class_id": d["class_id"],
            "academic_year_id": d["academic_year_id"],
            "status": d.get("status") or "ENROLLED",
            "enrolled_at": d.get("enrolled_at") or datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "enrollments", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


def seed_fees(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[fees_db]")
    eng = _engine("fees")

    # FeeStructures
    h, rows = _load_sheet(wb, "FeeStructures")
    payload = [{
        "id": r[h.index("id")], "school_id": r[h.index("school_id")],
        "academic_year_id": r[h.index("academic_year_id")],
        "term_id": r[h.index("term_id")], "name": r[h.index("name")],
        "is_active": bool(r[h.index("is_active")]),
        "created_at": datetime.now(timezone.utc),
    } for r in rows]
    _bulk_insert(eng, "fee_structures", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # FeeItems
    h, rows = _load_sheet(wb, "FeeItems")
    payload = [{
        "id": r[h.index("id")],
        "fee_structure_id": r[h.index("fee_structure_id")],
        "label": r[h.index("label")], "amount": r[h.index("amount")],
        "currency": r[h.index("currency")] or "USD",
    } for r in rows]
    _bulk_insert(eng, "fee_items", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Invoices
    h, rows = _load_sheet(wb, "Invoices")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append(_stamp({
            "id": d["id"], "school_id": d["school_id"],
            "student_id": d["student_id"],
            "fee_structure_id": d["fee_structure_id"],
            "total_amount": d["total_amount"],
            "paid_amount": d.get("paid_amount") or 0,
            "currency": d.get("currency") or "USD",
            "due_date": d["due_date"],
            "status": d.get("status") or "PENDING",
        }))
    _bulk_insert(eng, "invoices", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Payments
    h, rows = _load_sheet(wb, "Payments")
    payload = [{
        "id": r[h.index("id")], "school_id": r[h.index("school_id")],
        "invoice_id": r[h.index("invoice_id")],
        "amount": r[h.index("amount")],
        "currency": r[h.index("currency")] or "USD",
        "method": r[h.index("method")] or "CASH",
        "reference": r[h.index("reference")],
        "paid_at": r[h.index("paid_at")],
        "created_at": datetime.now(timezone.utc),
    } for r in rows]
    _bulk_insert(eng, "payments", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


def seed_assessment(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[assessment_db]")
    eng = _engine("assessment")

    # Assessments
    h, rows = _load_sheet(wb, "Assessments")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "academic_year_id": d["academic_year_id"], "term_id": d["term_id"],
            "class_id": d["class_id"], "subject_id": d["subject_id"],
            "name": d["name"], "assessment_type": d.get("type") or "TEST",
            "date": d["date"], "max_marks": d.get("max_marks") or 100,
            "created_by": d.get("created_by"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "assessments", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)

    # Marks
    h, rows = _load_sheet(wb, "Marks")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "assessment_id": d["assessment_id"],
            "student_id": d["student_id"],
            "marks": d.get("marks"),
            "is_absent": bool(d.get("is_absent")),
            "remarks": d.get("remarks"),
            "graded_by": d.get("graded_by"),
            "graded_at": d.get("graded_at") or datetime.now(timezone.utc),
        })
    _bulk_insert(eng, "marks", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


def seed_attendance(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[attendance_db]")
    eng = _engine("attendance")
    h, rows = _load_sheet(wb, "Attendance")
    now = datetime.now(timezone.utc)
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "student_id": d["student_id"], "class_id": d["class_id"],
            "date": d["date"], "status": d.get("status") or "P",
            "marked_by_user_id": d.get("marked_by_user_id"),
            "device_id": d.get("device_id"),
            "last_modified_at": now, "created_at": now, "updated_at": now,
        })
    _bulk_insert(eng, "attendance_records", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


def seed_comms(wb, dry_run: bool, truncate: bool) -> None:
    print("\n[comms_db]")
    eng = _engine("comms")
    h, rows = _load_sheet(wb, "Announcements")
    payload = []
    for r in rows:
        d = _row_dict(h, r)
        payload.append({
            "id": d["id"], "school_id": d["school_id"],
            "title": d["title"], "body": d["body"],
            "audience_type": d.get("audience_type") or "ALL",
            "audience_class_id": d.get("audience_class_id"),
            "audience_role": d.get("audience_role"),
            "created_by": d.get("created_by"),
            "created_at": d.get("created_at") or datetime.now(timezone.utc),
        })
    if not payload:
        print("  (no announcements)")
        return
    _bulk_insert(eng, "announcements", list(payload[0].keys()), payload,
                 truncate=truncate, dry_run=dry_run)


SEEDERS: dict[str, Callable[[Any, bool, bool], None]] = {
    "school": seed_school,
    "student": seed_student,
    "fees": seed_fees,
    "assessment": seed_assessment,
    "attendance": seed_attendance,
    "comms": seed_comms,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workbook", default="scripts/data/eduzim_master.xlsx",
        help="Path to eduzim_master.xlsx",
    )
    parser.add_argument(
        "--services", default=",".join(SEEDERS.keys()),
        help="Comma-separated list of services to seed",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print row counts without writing to DBs")
    parser.add_argument("--truncate", action="store_true",
                        help="DELETE existing rows from each table first (destructive)")
    args = parser.parse_args()

    wb_path = Path(args.workbook)
    if not wb_path.exists():
        print(f"Workbook not found: {wb_path}", file=sys.stderr)
        return 2

    services = [s.strip() for s in args.services.split(",") if s.strip()]
    unknown = [s for s in services if s not in SEEDERS]
    if unknown:
        print(f"Unknown service(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Valid services: {', '.join(SEEDERS.keys())}", file=sys.stderr)
        return 2

    print(f"Loading workbook: {wb_path} (read-only)")
    wb = openpyxl.load_workbook(wb_path, read_only=True, data_only=True)

    for svc in services:
        try:
            SEEDERS[svc](wb, args.dry_run, args.truncate)
        except Exception as e:
            print(f"  ✗ {svc} failed: {e}", file=sys.stderr)
            if not args.dry_run:
                return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
