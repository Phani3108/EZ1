"""
Assessment Service — API Routes
===================================
Endpoints:
  POST   /assessments                  — Create assessment (teacher auth)
  GET    /assessments                  — List assessments by class/term
  GET    /assessments/{id}             — Get assessment with marks grid
  POST   /assessments/{id}/marks/bulk  — Bulk upsert marks (teacher auth)
  GET    /students/{id}/marks          — Student marks grouped by subject
  GET    /classes/{id}/performance     — Class performance summary
"""
import uuid
from datetime import date as DateType
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_school_id,
    is_teacher_role,
    is_parent_role,
    verify_teacher_class_authorization,
    verify_parent_student_authorization,
)
from app.services.assessment_service import AssessmentService
from eduzim_shared.idempotency import DbIdempotencyStore
from app.models.idempotency import IdempotencyKey

router = APIRouter(tags=["assessments"])


# ───────────── Helpers ─────────────

def _meta(request: Request) -> dict:
    return {"request_path": str(request.url.path), "method": request.method}


def _err(code: int, message: str, request: Request) -> dict:
    return {"error": {"code": code, "message": message}, "meta": _meta(request)}


# ───────────── Schemas ─────────────

class CreateAssessmentRequest(BaseModel):
    academic_year_id: str = Field(..., description="Academic year UUID")
    term_id: str = Field(..., description="Term UUID")
    class_id: str = Field(..., description="Class UUID")
    subject_id: str = Field(..., description="Subject UUID")
    name: str = Field(..., min_length=1, max_length=200, description="Assessment name")
    assessment_type: str = Field(..., description="QUIZ | TEST | EXAM | ASSIGNMENT")
    assessment_date: DateType = Field(..., alias="date", description="Assessment date")
    max_marks: float = Field(..., gt=0, le=9999, description="Maximum marks")

    model_config = {"populate_by_name": True}


class MarkEntry(BaseModel):
    student_id: str = Field(..., description="Student UUID")
    marks: Optional[float] = Field(None, ge=0, description="Marks obtained")
    is_absent: bool = Field(False, description="Student absent")
    remarks: Optional[str] = Field(None, max_length=500)


class BulkMarksRequest(BaseModel):
    marks: list[MarkEntry] = Field(..., min_length=1, description="List of marks")


# ───────────── 1. Create Assessment ─────────────

@router.post("/assessments")
async def create_assessment(
    body: CreateAssessmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Validate assessment_type
    valid_types = {"QUIZ", "TEST", "EXAM", "ASSIGNMENT"}
    if body.assessment_type.upper() not in valid_types:
        raise HTTPException(status_code=400, detail=f"assessment_type must be one of {valid_types}")

    # Teacher auth: must be assigned to the class
    if is_teacher_role(current_user):
        authorized = await verify_teacher_class_authorization(
            uuid.UUID(current_user["sub"]),
            uuid.UUID(body.class_id),
            school_id,
        )
        if not authorized:
            raise HTTPException(status_code=403, detail="Not authorized for this class")
    elif "Admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Only teachers or admins can create assessments")

    svc = AssessmentService(db)
    result = svc.create_assessment(
        school_id=school_id,
        academic_year_id=uuid.UUID(body.academic_year_id),
        term_id=uuid.UUID(body.term_id),
        class_id=uuid.UUID(body.class_id),
        subject_id=uuid.UUID(body.subject_id),
        name=body.name,
        assessment_type=body.assessment_type.upper(),
        date=body.assessment_date,
        max_marks=Decimal(str(body.max_marks)),
        created_by=uuid.UUID(current_user["sub"]),
    )
    return {"data": result, "meta": _meta(request)}


# ───────────── 2. List Assessments ─────────────

@router.get("/assessments")
def list_assessments(
    request: Request,
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    svc = AssessmentService(db)
    result = svc.list_assessments(school_id, class_id, term_id, subject_id,
                                   limit=limit, offset=offset)
    return {"data": result, "meta": _meta(request)}


# ───────────── 3. Get Assessment (with marks) ─────────────

@router.get("/assessments/{assessment_id}")
def get_assessment(
    assessment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    svc = AssessmentService(db)
    result = svc.get_assessment(school_id, assessment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"data": result, "meta": _meta(request)}


# ───────────── 4. Bulk Upsert Marks (with idempotency) ─────────────

@router.post("/assessments/{assessment_id}/marks/bulk")
async def bulk_upsert_marks(
    assessment_id: uuid.UUID,
    body: BulkMarksRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # ── Idempotency check via X-Request-Id header ──
    request_id = request.headers.get("X-Request-Id")
    if request_id:
        idem_store = DbIdempotencyStore(db, IdempotencyKey)
        idem_key = f"marks-bulk:{request_id}"
        if idem_store.is_duplicate(idem_key):
            cached = idem_store.get_cached_response(idem_key)
            if cached:
                cached["already_processed"] = True
                return {"data": cached, "meta": _meta(request)}
            return {
                "data": {"accepted": 0, "updated": 0, "errors": [], "already_processed": True},
                "meta": _meta(request),
            }

    # Verify assessment exists to get class_id for auth
    svc = AssessmentService(db)
    assessment = svc.get_assessment(school_id, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Teacher auth
    if is_teacher_role(current_user):
        authorized = await verify_teacher_class_authorization(
            uuid.UUID(current_user["sub"]),
            uuid.UUID(assessment["class_id"]),
            school_id,
        )
        if not authorized:
            raise HTTPException(status_code=403, detail="Not authorized for this class")
    elif "Admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="Only teachers or admins can grade")

    result = svc.bulk_upsert_marks(
        school_id=school_id,
        assessment_id=assessment_id,
        marks_data=[m.model_dump() for m in body.marks],
        graded_by=uuid.UUID(current_user["sub"]),
    )

    # ── Record idempotency key ──
    if request_id:
        idem_store = DbIdempotencyStore(db, IdempotencyKey)
        idem_key = f"marks-bulk:{request_id}"
        idem_store.mark_processed(idem_key, result)

    return {"data": result, "meta": _meta(request)}


# ───────────── 5. Student Marks ─────────────

@router.get("/assessments/students/{student_id}/marks")
async def student_marks(
    student_id: uuid.UUID,
    request: Request,
    term_id: uuid.UUID = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Parent auth: can only see linked child
    if is_parent_role(current_user):
        authorized = await verify_parent_student_authorization(
            uuid.UUID(current_user["sub"]),
            student_id,
            school_id,
        )
        if not authorized:
            raise HTTPException(status_code=403, detail="Not authorized for this student")

    svc = AssessmentService(db)
    result = svc.student_marks(school_id, student_id, term_id)
    return {"data": result, "meta": _meta(request)}


# ───────────── 6. Class Performance ─────────────

@router.get("/assessments/classes/{class_id}/performance")
def class_performance(
    class_id: uuid.UUID,
    request: Request,
    term_id: uuid.UUID = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    svc = AssessmentService(db)
    result = svc.class_performance(school_id, class_id, term_id)
    return {"data": result, "meta": _meta(request)}
