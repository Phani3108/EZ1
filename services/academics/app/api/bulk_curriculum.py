"""Phase 16a-4 — Bulk CSV import for curriculum (school-local) and the
Ministry-side National Curriculum.

CSV shape (one row per topic OR per unit-without-topic):
  * `subject_code`       — required.
  * `unit_code`          — required.
  * `unit_name`          — required when a new unit is being created.
  * `unit_sequence`      — optional integer.
  * `unit_grade_level`   — optional.
  * `topic_code`         — optional. When blank, only the unit is
                            upserted; useful for seeding empty units.
  * `topic_name`         — required when `topic_code` is set.
  * `topic_sequence`     — optional integer.
  * `learning_outcomes`  — optional free text.
  * `parent_topic_code`  — optional. References a topic_code within the
                            same unit; used for one-level sub-topics.

Idempotency
-----------
Each row is upserted by `(school_id, subject_id, unit_code)` for units
and `(school_id, unit_id, topic_code)` for topics. Re-running is a no-op
on rows that already match; rows with changed names/sequence/outcomes
ARE updated.

Two endpoints — school-local + Ministry-side — share the same CSV
shape. Ministry-side ignores `school_id` (rows are global). Both
support `?dry_run=true`.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.school import Subject
from app.models.curriculum import Unit, Topic
from app.models.national_curriculum import (
    NationalSubject, NationalUnit, NationalTopic,
)


router = APIRouter(tags=["Bulk Curriculum"])


REQUIRED_COLUMNS = {"subject_code", "unit_code"}
MAX_ROWS = 2000


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request, status=400, details=None):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": details or {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _parse_int(v) -> int:
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0


def _read_csv(file_bytes: bytes) -> tuple[Optional[list], Optional[set], Optional[str]]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, None, "File must be UTF-8 encoded"
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    rows = list(reader)
    return rows, headers, None


# ─── School-local bulk import ─────────────────────────────────────


@router.post("/bulk/curriculum")
async def bulk_curriculum(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Bulk-create school-local Units + Topics from CSV."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return _err("INVALID_FILE", "File must be a .csv", request)
    content = await file.read()
    rows, headers, dec_err = _read_csv(content)
    if dec_err:
        return _err("ENCODING_ERROR", dec_err, request)
    missing = REQUIRED_COLUMNS - headers
    if missing:
        return _err(
            "MISSING_COLUMNS",
            f"Missing required columns: {', '.join(sorted(missing))}",
            request,
            details={"missing": sorted(missing), "found": sorted(headers)},
        )

    actor = uuid.UUID(str(current_user["sub"]))
    results = {
        "total_rows": 0,
        "units_created": 0,
        "units_updated": 0,
        "topics_created": 0,
        "topics_updated": 0,
        "skipped": 0,
        "errors": [],
    }

    # Resolve subject_code → subject_id per request (small cache).
    subject_by_code: dict[str, Subject] = {}

    # First pass: upsert units (+ accumulate topic rows for second pass).
    pending_topics: list[dict] = []
    for row_num, row in enumerate(rows, start=2):
        if row_num > MAX_ROWS + 1:
            results["errors"].append(
                {"row": row_num, "error": f"Maximum {MAX_ROWS} rows exceeded"}
            )
            break
        results["total_rows"] += 1
        subj_code = (row.get("subject_code") or "").strip()
        unit_code = (row.get("unit_code") or "").strip()
        if not subj_code or not unit_code:
            results["errors"].append({
                "row": row_num,
                "error": "subject_code and unit_code are required",
            })
            results["skipped"] += 1
            continue
        # Subject lookup.
        subj = subject_by_code.get(subj_code)
        if not subj:
            subj = (
                db.query(Subject)
                .filter(
                    Subject.school_id == school_id,
                    Subject.code == subj_code,
                )
                .first()
            )
            if not subj:
                results["errors"].append({
                    "row": row_num,
                    "error": f"unknown subject_code '{subj_code}'",
                })
                results["skipped"] += 1
                continue
            subject_by_code[subj_code] = subj
        # Unit upsert.
        unit = (
            db.query(Unit)
            .filter(
                Unit.school_id == school_id,
                Unit.subject_id == subj.id,
                Unit.code == unit_code,
            )
            .first()
        )
        unit_name = (row.get("unit_name") or "").strip()
        unit_seq = _parse_int(row.get("unit_sequence"))
        unit_grade = (row.get("unit_grade_level") or "").strip() or None
        if unit:
            updated = False
            if unit_name and unit.name != unit_name:
                unit.name = unit_name
                updated = True
            if unit.sequence_order != unit_seq:
                unit.sequence_order = unit_seq
                updated = True
            if unit.grade_level != unit_grade:
                unit.grade_level = unit_grade
                updated = True
            if updated and not dry_run:
                results["units_updated"] += 1
        else:
            if not unit_name:
                results["errors"].append({
                    "row": row_num,
                    "error": "unit_name required when creating a new unit",
                })
                results["skipped"] += 1
                continue
            if not dry_run:
                unit = Unit(
                    id=uuid.uuid4(),
                    school_id=school_id,
                    subject_id=subj.id,
                    name=unit_name,
                    code=unit_code,
                    sequence_order=unit_seq,
                    grade_level=unit_grade,
                    created_by=actor,
                )
                db.add(unit)
                db.flush()
            results["units_created"] += 1
        # Topic — queue for second pass so we can resolve parent_topic_code.
        topic_code = (row.get("topic_code") or "").strip()
        if topic_code:
            pending_topics.append({
                "row_num": row_num,
                "subject_id": subj.id,
                "unit": unit,
                "code": topic_code,
                "name": (row.get("topic_name") or "").strip(),
                "sequence": _parse_int(row.get("topic_sequence")),
                "learning_outcomes": (row.get("learning_outcomes") or "").strip() or None,
                "parent_topic_code": (row.get("parent_topic_code") or "").strip() or None,
            })

    # Second pass: upsert topics; resolve parents within the same unit.
    for row in pending_topics:
        if not row["name"]:
            results["errors"].append({
                "row": row["row_num"],
                "error": "topic_name required when topic_code is set",
            })
            results["skipped"] += 1
            continue
        unit = row["unit"]
        if unit is None:
            # Dry-run + new unit: skip topic creation, but record it.
            if dry_run:
                results["topics_created"] += 1
            continue
        # Resolve parent_topic_id if asked.
        parent_topic_id = None
        if row["parent_topic_code"]:
            parent = (
                db.query(Topic)
                .filter(
                    Topic.school_id == school_id,
                    Topic.unit_id == unit.id,
                    Topic.code == row["parent_topic_code"],
                )
                .first()
            )
            if parent:
                parent_topic_id = parent.id
        existing = (
            db.query(Topic)
            .filter(
                Topic.school_id == school_id,
                Topic.unit_id == unit.id,
                Topic.code == row["code"],
            )
            .first()
        )
        if existing:
            updated = False
            if existing.name != row["name"]:
                existing.name = row["name"]
                updated = True
            if existing.sequence_order != row["sequence"]:
                existing.sequence_order = row["sequence"]
                updated = True
            if existing.learning_outcomes != row["learning_outcomes"]:
                existing.learning_outcomes = row["learning_outcomes"]
                updated = True
            if existing.parent_topic_id != parent_topic_id:
                existing.parent_topic_id = parent_topic_id
                updated = True
            if updated and not dry_run:
                results["topics_updated"] += 1
        else:
            if not dry_run:
                db.add(Topic(
                    id=uuid.uuid4(),
                    school_id=school_id,
                    subject_id=row["subject_id"],
                    unit_id=unit.id,
                    parent_topic_id=parent_topic_id,
                    name=row["name"],
                    code=row["code"],
                    sequence_order=row["sequence"],
                    learning_outcomes=row["learning_outcomes"],
                    created_by=actor,
                ))
            results["topics_created"] += 1

    if not dry_run:
        db.commit()

    meta = _meta(request)
    meta["dry_run"] = dry_run
    return {"data": results, "meta": meta}


# ─── Ministry-side bulk import ────────────────────────────────────


@router.post("/ministry/bulk/national-curriculum")
async def bulk_national_curriculum(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
    country: str = Query("ZW"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Bulk-create NationalSubject / Unit / Topic rows from CSV.

    Same column shape as the school-local importer, minus `school_id`
    scoping. New National subjects are created on the fly (with
    `name` defaulted to `subject_code` if no separate `subject_name`
    column is supplied — admins should re-edit afterwards). Subjects
    are NOT auto-published — call the publish endpoint when ready.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return _err("INVALID_FILE", "File must be a .csv", request)
    content = await file.read()
    rows, headers, dec_err = _read_csv(content)
    if dec_err:
        return _err("ENCODING_ERROR", dec_err, request)
    missing = REQUIRED_COLUMNS - headers
    if missing:
        return _err(
            "MISSING_COLUMNS",
            f"Missing required columns: {', '.join(sorted(missing))}",
            request,
            details={"missing": sorted(missing), "found": sorted(headers)},
        )

    results = {
        "total_rows": 0,
        "subjects_created": 0,
        "units_created": 0,
        "units_updated": 0,
        "topics_created": 0,
        "topics_updated": 0,
        "skipped": 0,
        "errors": [],
    }

    subject_by_code: dict[str, NationalSubject] = {}
    pending_topics: list[dict] = []

    for row_num, row in enumerate(rows, start=2):
        if row_num > MAX_ROWS + 1:
            results["errors"].append(
                {"row": row_num, "error": f"Maximum {MAX_ROWS} rows exceeded"}
            )
            break
        results["total_rows"] += 1
        subj_code = (row.get("subject_code") or "").strip()
        unit_code = (row.get("unit_code") or "").strip()
        if not subj_code or not unit_code:
            results["errors"].append({"row": row_num, "error": "subject_code and unit_code required"})
            results["skipped"] += 1
            continue
        subj = subject_by_code.get(subj_code)
        if not subj:
            subj = (
                db.query(NationalSubject)
                .filter(
                    NationalSubject.country == country,
                    NationalSubject.code == subj_code,
                )
                .first()
            )
            if not subj:
                # Auto-create.
                subj_name = (row.get("subject_name") or subj_code).strip()
                if not dry_run:
                    subj = NationalSubject(
                        id=uuid.uuid4(),
                        country=country,
                        code=subj_code,
                        name=subj_name,
                    )
                    db.add(subj)
                    db.flush()
                results["subjects_created"] += 1
            if subj:
                subject_by_code[subj_code] = subj
        # Unit upsert.
        unit = None
        if subj:
            unit = (
                db.query(NationalUnit)
                .filter(
                    NationalUnit.national_subject_id == subj.id,
                    NationalUnit.code == unit_code,
                )
                .first()
            )
        unit_name = (row.get("unit_name") or "").strip()
        unit_seq = _parse_int(row.get("unit_sequence"))
        unit_grade = (row.get("unit_grade_level") or "").strip() or None
        if unit:
            updated = False
            if unit_name and unit.name != unit_name:
                unit.name = unit_name
                updated = True
            if unit.sequence_order != unit_seq:
                unit.sequence_order = unit_seq
                updated = True
            if unit.grade_level != unit_grade:
                unit.grade_level = unit_grade
                updated = True
            if updated and not dry_run:
                results["units_updated"] += 1
        else:
            if not unit_name:
                results["errors"].append({"row": row_num, "error": "unit_name required for new unit"})
                results["skipped"] += 1
                continue
            if not dry_run and subj:
                unit = NationalUnit(
                    id=uuid.uuid4(),
                    national_subject_id=subj.id,
                    name=unit_name,
                    code=unit_code,
                    sequence_order=unit_seq,
                    grade_level=unit_grade,
                )
                db.add(unit)
                db.flush()
            results["units_created"] += 1
        topic_code = (row.get("topic_code") or "").strip()
        if topic_code:
            pending_topics.append({
                "row_num": row_num,
                "unit": unit,
                "code": topic_code,
                "name": (row.get("topic_name") or "").strip(),
                "sequence": _parse_int(row.get("topic_sequence")),
                "learning_outcomes": (row.get("learning_outcomes") or "").strip() or None,
                "parent_topic_code": (row.get("parent_topic_code") or "").strip() or None,
            })

    for row in pending_topics:
        if not row["name"]:
            results["errors"].append({
                "row": row["row_num"],
                "error": "topic_name required when topic_code set",
            })
            results["skipped"] += 1
            continue
        unit = row["unit"]
        if unit is None:
            if dry_run:
                results["topics_created"] += 1
            continue
        parent_topic_id = None
        if row["parent_topic_code"]:
            parent = (
                db.query(NationalTopic)
                .filter(
                    NationalTopic.national_unit_id == unit.id,
                    NationalTopic.code == row["parent_topic_code"],
                )
                .first()
            )
            if parent:
                parent_topic_id = parent.id
        existing = (
            db.query(NationalTopic)
            .filter(
                NationalTopic.national_unit_id == unit.id,
                NationalTopic.code == row["code"],
            )
            .first()
        )
        if existing:
            updated = False
            if existing.name != row["name"]:
                existing.name = row["name"]
                updated = True
            if existing.sequence_order != row["sequence"]:
                existing.sequence_order = row["sequence"]
                updated = True
            if existing.learning_outcomes != row["learning_outcomes"]:
                existing.learning_outcomes = row["learning_outcomes"]
                updated = True
            if existing.parent_topic_id != parent_topic_id:
                existing.parent_topic_id = parent_topic_id
                updated = True
            if updated and not dry_run:
                results["topics_updated"] += 1
        else:
            if not dry_run:
                db.add(NationalTopic(
                    id=uuid.uuid4(),
                    national_unit_id=unit.id,
                    parent_topic_id=parent_topic_id,
                    name=row["name"],
                    code=row["code"],
                    sequence_order=row["sequence"],
                    learning_outcomes=row["learning_outcomes"],
                ))
            results["topics_created"] += 1

    if not dry_run:
        db.commit()

    meta = _meta(request)
    meta["dry_run"] = dry_run
    return {"data": results, "meta": meta}
