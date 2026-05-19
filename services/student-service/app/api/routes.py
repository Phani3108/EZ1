"""Student Service API Routes — Standard {data, meta} envelope."""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id, get_token
from app.services.student_service import StudentService
from app.services.school_client import HttpSchoolServiceClient
from app.events import publish_event

router = APIRouter(tags=["Students"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request):
    return {"error": {"code": code, "message": msg, "details": {}, "request_id": _meta(request)["request_id"]}}


def _svc(db: Session) -> StudentService:
    return StudentService(db, school_client=HttpSchoolServiceClient())


# ───── Schemas ─────

class StudentCreate(BaseModel):
    student_code: str = Field(..., max_length=50)
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    dob: Optional[date] = None
    gender: Optional[str] = None
    admission_date: Optional[date] = None

class StudentUpdate(BaseModel):
    student_code: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    status: Optional[str] = None

class ParentCreate(BaseModel):
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=20)
    email: Optional[str] = None
    relationship_type: str = Field("GUARDIAN", max_length=20)

class ParentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class ParentLink(BaseModel):
    is_primary: bool = False

class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: uuid.UUID
    academic_year_id: uuid.UUID

class EnrollmentUpdate(BaseModel):
    status: Optional[str] = None
    class_id: Optional[uuid.UUID] = None


# ───── Students ─────

@router.post("/students")
def create_student(data: StudentCreate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.create_student(school_id, data.student_code, data.first_name,
                                 data.last_name, data.dob, data.gender, data.admission_date)
    if "error" in result:
        return _err(result["error"], result["message"], request), 409
    publish_event("eduzim.student.student.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/students")
def list_students(request: Request, page: int = Query(1, ge=1),
                  page_size: int = Query(50, ge=1, le=100),
                  status: str = Query(None), query: str = Query(None),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    students, total = svc.list_students(school_id, page, page_size, status, query)
    meta = _meta(request)
    meta.update({"page": page, "page_size": page_size, "total": total,
                 "has_next": (page * page_size) < total})
    return {"data": students, "meta": meta}


@router.get("/students/{student_id}")
def get_student(student_id: uuid.UUID, request: Request,
                db: Session = Depends(get_db),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.get_student(student_id, school_id)
    if not result:
        return _err("NOT_FOUND", "Student not found", request), 404
    return {"data": result, "meta": _meta(request)}


@router.put("/students/{student_id}")
def update_student(student_id: uuid.UUID, data: StudentUpdate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.update_student(student_id, school_id, data.first_name, data.last_name,
                                 data.dob, data.gender, data.status, data.student_code)
    if result is None:
        return _err("NOT_FOUND", "Student not found", request), 404
    if "error" in result:
        return _err(result["error"], result["message"], request), 409
    return {"data": result, "meta": _meta(request)}


@router.delete("/students/{student_id}")
def delete_student(student_id: uuid.UUID, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.soft_delete_student(student_id, school_id)
    if result is None:
        return _err("NOT_FOUND", "Student not found", request), 404
    if "error" in result:
        return _err(result["error"], result["message"], request), 409
    return {"data": result, "meta": _meta(request)}


# ───── Parent Self-Service ─────

@router.get("/parents/me/children")
def get_my_children(request: Request,
                    db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user),
                    school_id: uuid.UUID = Depends(get_school_id)):
    user_id = current_user.get("sub")
    if not user_id:
        return _err("UNAUTHORIZED", "User identity not found in token", request), 401
    svc = _svc(db)
    result = svc.get_children_by_user_id(uuid.UUID(user_id), school_id)
    if result is None:
        return _err("NOT_FOUND", "No parent profile linked to this account", request), 404
    return {"data": result, "meta": _meta(request)}


# ───── Parents ─────

@router.post("/parents")
def create_parent(data: ParentCreate, request: Request,
                  db: Session = Depends(get_db),
                  current_user: dict = Depends(get_current_user),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.create_parent(school_id, data.first_name, data.last_name,
                                data.phone, data.email, data.relationship_type)
    if "error" in result:
        return _err(result["error"], result["message"], request), 409
    return {"data": result, "meta": _meta(request)}


@router.get("/parents")
def list_parents(request: Request,
                 limit: int = Query(100, ge=1, le=500),
                 offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    return {"data": svc.list_parents(school_id, limit=limit, offset=offset),
            "meta": _meta(request)}


@router.put("/parents/{parent_id}")
def update_parent(parent_id: uuid.UUID, data: ParentUpdate, request: Request,
                  db: Session = Depends(get_db),
                  current_user: dict = Depends(get_current_user),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.update_parent(parent_id, school_id, data.first_name, data.last_name,
                                data.phone, data.email)
    if result is None:
        return _err("NOT_FOUND", "Parent not found", request), 404
    if "error" in result:
        return _err(result["error"], result["message"], request), 409
    return {"data": result, "meta": _meta(request)}


# ───── Parent Linking ─────

@router.post("/students/{student_id}/parents/{parent_id}")
def link_parent(student_id: uuid.UUID, parent_id: uuid.UUID,
                data: ParentLink, request: Request,
                db: Session = Depends(get_db),
                current_user: dict = Depends(get_current_user),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.link_parent(school_id, student_id, parent_id, data.is_primary)
    if "error" in result:
        code = 404 if result["error"] == "NOT_FOUND" else 409
        return _err(result["error"], result["message"], request), code
    publish_event("eduzim.student.parent.linked.v1", str(student_id), result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


# ───── Enrollment ─────

@router.post("/enrollments")
def create_enrollment(data: EnrollmentCreate, request: Request,
                      db: Session = Depends(get_db),
                      current_user: dict = Depends(get_current_user),
                      school_id: uuid.UUID = Depends(get_school_id),
                      token: str = Depends(get_token)):
    svc = StudentService(db, school_client=HttpSchoolServiceClient())
    result = svc.create_enrollment(school_id, data.student_id, data.class_id,
                                    data.academic_year_id, token)
    if "error" in result:
        code = 409 if result["error"] == "DUPLICATE_ENROLLMENT" else 422
        return _err(result["error"], result["message"], request), code
    publish_event("eduzim.student.enrollment.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/enrollments")
def list_enrollments(request: Request,
                     class_id: uuid.UUID = Query(None),
                     year_id: uuid.UUID = Query(None),
                     db: Session = Depends(get_db),
                     school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    return {"data": svc.list_enrollments(school_id, class_id, year_id), "meta": _meta(request)}


@router.put("/enrollments/{enrollment_id}")
def update_enrollment(enrollment_id: uuid.UUID, data: EnrollmentUpdate,
                      request: Request, db: Session = Depends(get_db),
                      current_user: dict = Depends(get_current_user),
                      school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.update_enrollment(enrollment_id, school_id, data.status,
                                    data.class_id)
    if result is None:
        return _err("NOT_FOUND", "Enrollment not found", request), 404
    if "error" in result:
        return _err(result["error"], result["message"], request), 422
    publish_event("eduzim.student.enrollment.updated.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


# ───── Internal: Parent-Child Authorization ─────

@router.get("/internal/parents/authorize")
def authorize_parent(request: Request,
                     user_id: uuid.UUID = Query(...),
                     student_id: uuid.UUID = Query(...),
                     db: Session = Depends(get_db),
                     school_id: uuid.UUID = Depends(get_school_id)):
    """Internal endpoint for other services to verify parent-child link.

    Returns {"authorized": true/false}.
    Not exposed via API gateway — service-to-service only.
    """
    svc = _svc(db)
    authorized = svc.verify_parent_child_link(user_id, student_id, school_id)
    return {"data": {"authorized": authorized}, "meta": _meta(request)}
