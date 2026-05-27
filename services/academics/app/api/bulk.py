"""
Bulk Operations — CSV Import, Bulk Enroll, Academic Year Rollover
"""
import csv
import io
import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.student_service import StudentService
# PH2-7: HttpSchoolServiceClient was the inter-service HTTP client. After
# PH2-7 the school models live next door (academics_db), so we use the
# in-process query helper instead — same Protocol shape so the service
# layer is unchanged.
from app.services.school_client import InProcessSchoolClient
from app.events import publish_event

router = APIRouter(tags=["Bulk Operations"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _svc(db: Session) -> StudentService:
    # PH2-7: client now uses the caller's DB session — no HTTP hop.
    return StudentService(db, school_client=InProcessSchoolClient(db))


# ─── CSV Import ───

REQUIRED_COLUMNS = {"first_name", "last_name", "student_code"}
OPTIONAL_COLUMNS = {"dob", "gender", "admission_date", "parent_first_name",
                     "parent_last_name", "parent_phone", "parent_email", "class_name"}
VALID_GENDERS = {"M", "F", "MALE", "FEMALE", "OTHER", ""}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")
MAX_ROWS = 1000


@router.post("/students/import")
async def import_students_csv(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only, do not import"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """
    Import students from a CSV file with server-side validation.

    Required columns: first_name, last_name, student_code
    Optional: dob, gender, admission_date, parent_first_name, parent_last_name,
              parent_phone, parent_email, class_name
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return {"error": {"code": "INVALID_FILE", "message": "File must be a .csv",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 400

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # Handle BOM
    except UnicodeDecodeError:
        return {"error": {"code": "ENCODING_ERROR", "message": "File must be UTF-8 encoded",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 400

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])

    # Validate required columns
    missing = REQUIRED_COLUMNS - headers
    if missing:
        return {"error": {"code": "MISSING_COLUMNS",
                          "message": f"Missing required columns: {', '.join(sorted(missing))}",
                          "details": {"missing": sorted(missing), "found": sorted(headers)},
                          "request_id": _meta(request)["request_id"]}}, 400

    svc = _svc(db)
    results = {"total": 0, "created": 0, "skipped": 0, "errors": []}

    for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        if row_num > MAX_ROWS + 1:
            results["errors"].append({"row": row_num, "error": f"Maximum {MAX_ROWS} rows exceeded"})
            break

        results["total"] += 1
        row_errors = _validate_row(row, row_num)

        if row_errors:
            results["errors"].extend(row_errors)
            results["skipped"] += 1
            continue

        if dry_run:
            results["created"] += 1
            continue

        # Create student
        try:
            student_data = {
                "student_code": row["student_code"].strip(),
                "first_name": row["first_name"].strip(),
                "last_name": row["last_name"].strip(),
            }
            if row.get("dob"):
                student_data["dob"] = row["dob"].strip()
            if row.get("gender"):
                g = row["gender"].strip().upper()
                student_data["gender"] = "M" if g in ("M", "MALE") else "F" if g in ("F", "FEMALE") else g
            if row.get("admission_date"):
                student_data["admission_date"] = row["admission_date"].strip()

            result = svc.create_student(
                school_id=school_id,
                student_code=student_data["student_code"],
                first_name=student_data["first_name"],
                last_name=student_data["last_name"],
                dob=student_data.get("dob"),
                gender=student_data.get("gender"),
                admission_date=student_data.get("admission_date"),
            )

            if isinstance(result, dict) and "error" in result:
                results["errors"].append({"row": row_num, "error": result["message"]})
                results["skipped"] += 1
            else:
                results["created"] += 1
                publish_event("eduzim.student.student.created.v1",
                              result.get("id", ""), result,
                              str(school_id), current_user["sub"])

                # Create parent if provided
                if row.get("parent_first_name") and row.get("parent_last_name"):
                    _create_parent_for_student(
                        svc, school_id, result["id"], row, current_user["sub"]
                    )

        except Exception as e:
            results["errors"].append({"row": row_num, "error": str(e)[:200]})
            results["skipped"] += 1

    meta = _meta(request)
    meta["dry_run"] = dry_run
    return {"data": results, "meta": meta}


def _validate_row(row: dict, row_num: int) -> list[dict]:
    errors = []
    for col in REQUIRED_COLUMNS:
        if not row.get(col, "").strip():
            errors.append({"row": row_num, "field": col, "error": f"{col} is required"})

    if row.get("dob") and not DATE_PATTERN.match(row["dob"].strip()):
        errors.append({"row": row_num, "field": "dob", "error": "Date format must be YYYY-MM-DD"})

    if row.get("admission_date") and not DATE_PATTERN.match(row["admission_date"].strip()):
        errors.append({"row": row_num, "field": "admission_date", "error": "Date format must be YYYY-MM-DD"})

    if row.get("gender") and row["gender"].strip().upper() not in VALID_GENDERS:
        errors.append({"row": row_num, "field": "gender", "error": "Gender must be M, F, or OTHER"})

    if row.get("parent_phone") and not PHONE_PATTERN.match(row["parent_phone"].strip().replace(" ", "")):
        errors.append({"row": row_num, "field": "parent_phone", "error": "Invalid phone number format"})

    return errors


def _create_parent_for_student(svc, school_id, student_id, row, actor_id):
    try:
        parent = svc.create_parent(
            school_id=school_id,
            first_name=row["parent_first_name"].strip(),
            last_name=row["parent_last_name"].strip(),
            phone=row.get("parent_phone", "").strip() or "+263700000000",
            email=row.get("parent_email", "").strip() or None,
            relationship_type="GUARDIAN",
        )
        if parent and "id" in parent:
            svc.link_parent_to_student(student_id, parent["id"], school_id)
    except Exception:
        pass  # Parent creation is best-effort during import


# ─── Bulk Enroll ───

class BulkEnrollRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    class_id: uuid.UUID
    academic_year_id: uuid.UUID


@router.post("/students/bulk-enroll")
def bulk_enroll(
    data: BulkEnrollRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Enroll multiple students into a class at once."""
    svc = _svc(db)
    results = {"enrolled": 0, "skipped": 0, "errors": []}

    for student_id in data.student_ids:
        try:
            result = svc.create_enrollment(
                school_id=school_id,
                student_id=student_id,
                class_id=data.class_id,
                academic_year_id=data.academic_year_id,
            )
            if isinstance(result, dict) and "error" in result:
                results["errors"].append({"student_id": str(student_id), "error": result["message"]})
                results["skipped"] += 1
            else:
                results["enrolled"] += 1
        except Exception as e:
            results["errors"].append({"student_id": str(student_id), "error": str(e)[:200]})
            results["skipped"] += 1

    return {"data": results, "meta": _meta(request)}


# ─── Academic Year Rollover / Promotion ───

class PromotionRequest(BaseModel):
    from_academic_year_id: uuid.UUID
    to_academic_year_id: uuid.UUID
    promotions: list[dict] = Field(
        ...,
        description="List of {from_class_id, to_class_id} mappings",
        min_length=1,
    )


@router.post("/students/promote")
def promote_students(
    data: PromotionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """
    Academic year rollover: promote students from one year's classes to next year's.
    Each mapping specifies from_class_id → to_class_id.
    Students with status ACTIVE in the old enrollment are enrolled in the new class.
    """
    svc = _svc(db)
    results = {"promoted": 0, "retained": 0, "errors": []}

    for mapping in data.promotions:
        from_class = mapping.get("from_class_id")
        to_class = mapping.get("to_class_id")
        if not from_class or not to_class:
            results["errors"].append({"error": "Both from_class_id and to_class_id are required"})
            continue

        # Get current enrollments for the source class and year.
        # Use the upper cap; class promotion needs all students at once.
        enrollments = svc.list_enrollments(
            school_id=school_id,
            class_id=uuid.UUID(from_class),
            academic_year_id=data.from_academic_year_id,
            limit=500,
        )

        for enr in enrollments:
            if enr.get("status") != "ACTIVE":
                results["retained"] += 1
                continue

            try:
                new_enr = svc.create_enrollment(
                    school_id=school_id,
                    student_id=uuid.UUID(enr["student_id"]),
                    class_id=uuid.UUID(to_class),
                    academic_year_id=data.to_academic_year_id,
                )
                if isinstance(new_enr, dict) and "error" in new_enr:
                    results["errors"].append({
                        "student_id": enr["student_id"],
                        "error": new_enr["message"],
                    })
                else:
                    results["promoted"] += 1
            except Exception as e:
                results["errors"].append({
                    "student_id": enr["student_id"],
                    "error": str(e)[:200],
                })

    return {"data": results, "meta": _meta(request)}
