"""Student Service API Routes — Standard {data, meta} envelope."""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id, get_token
from app.services.student_service import StudentService
# PH2-7: school models are now local to academics_db; use the in-process
# query helper instead of the old HTTP school-client.
from app.services.school_client import InProcessSchoolClient
from app.events import publish_event

# Phase 9 / INFRA-018 — audit log
from eduzim_shared.audit import Event as AuditEvent, record_audit_event
from app.models.audit import AuditLog

router = APIRouter(tags=["Students"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request, status_code: int = 400):
    """BUG-009 / Phase 4 / Q-006: returns a real JSONResponse with the
    given status_code. The previous implementation returned a plain
    dict; route handlers then did `return _err(..., status_code=404)` — but FastAPI
    treats a returned `(dict, int)` as a 2-element list serialised at
    HTTP 200. That meant every 404 / 409 path in academics was actually
    a 200 with a weird-shaped body. The cross-tenant Q-006 tests caught
    it on first run.
    """
    body = {
        "error": {
            "code": code,
            "message": msg,
            "details": {},
            "request_id": _meta(request)["request_id"],
        }
    }
    return JSONResponse(content=body, status_code=status_code)


def _svc(db: Session) -> StudentService:
    # PH2-7: in-process — no HTTP hop to school-service.
    return StudentService(db, school_client=InProcessSchoolClient(db))


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
        return _err(result["error"], result["message"], request, status_code=409)
    publish_event("eduzim.student.student.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    # Phase 9: audit row. Note: we DO NOT include the student's name/dob in
    # `details` (ADR 007 — minimise PII in audit log). Target identifies
    # the row; the full row is in the students table itself.
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.STUDENT_CREATED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "student", "id": result["id"]},
        details={"student_code": data.student_code},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
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


# Phase 12g / S-001: declared BEFORE the parameterised
# `/students/{student_id}` so FastAPI matches "/students/me" first
# instead of trying to parse "me" as a UUID.
@router.get("/students/me")
def get_my_student_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Student-role self-service: returns the student record linked to
    the caller's user_id. 404 if the caller hasn't been linked to a
    student yet."""
    from app.models.student import Student
    user_id_raw = current_user.get("sub")
    if not user_id_raw:
        return _err("UNAUTHORIZED", "User identity missing", request, status_code=401)
    try:
        user_id = uuid.UUID(str(user_id_raw))
    except (TypeError, ValueError):
        return _err("UNAUTHORIZED", "User identity malformed", request, status_code=401)
    s = (
        db.query(Student)
        .filter(Student.user_id == user_id, Student.school_id == school_id,
                Student.deleted_at.is_(None))
        .first()
    )
    if s is None:
        return _err(
            "NOT_FOUND",
            "No student record linked to this account.",
            request, status_code=404,
        )
    return {
        "data": {
            "id": str(s.id),
            "student_code": s.student_code,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "dob": s.dob.isoformat() if s.dob else None,
            "gender": s.gender,
            "status": s.status,
        },
        "meta": _meta(request),
    }


@router.get("/students/{student_id}")
def get_student(student_id: uuid.UUID, request: Request,
                db: Session = Depends(get_db),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.get_student(student_id, school_id)
    if not result:
        return _err("NOT_FOUND", "Student not found", request, status_code=404)
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
        return _err("NOT_FOUND", "Student not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    # Phase 9: audit row. `details` lists the FIELD NAMES that were
    # touched, not the values (the values themselves are PII; the
    # fact that an update happened is the audit signal).
    changed_fields = [
        k for k, v in data.model_dump(exclude_unset=True).items() if v is not None
    ]
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.STUDENT_UPDATED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "student", "id": str(student_id)},
        details={"changed_fields": changed_fields},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.delete("/students/{student_id}")
def delete_student(student_id: uuid.UUID, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.soft_delete_student(student_id, school_id)
    if result is None:
        return _err("NOT_FOUND", "Student not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    # Phase 9: audit row. Deletions are higher-sensitivity than updates;
    # we keep the audit even though the underlying student row was
    # soft-deleted (the audit row outlives the student record).
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.STUDENT_DELETED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "student", "id": str(student_id)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


# ───── Phase 12a / PH12-1 — Link student to identity User ─────


class StudentUserLink(BaseModel):
    """Recorded linkage between a Student row and an Identity User.

    User creation itself stays in identity-service (admin-web flow).
    Once created with the Student role, an admin calls this endpoint
    to associate the User with the academic Student record. That
    makes `current_user.sub` resolvable to a Student via the unique
    `students.user_id` column.
    """
    user_id: uuid.UUID


@router.post("/students/{student_id}/link-user")
def link_student_user(
    student_id: uuid.UUID, data: StudentUserLink, request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Admin-only. Records `students.user_id` so the named user can
    log in and resolve to this student's academic record."""
    from app.models.student import Student
    s = (
        db.query(Student)
        .filter(Student.id == student_id, Student.school_id == school_id,
                Student.deleted_at.is_(None))
        .first()
    )
    if s is None:
        return _err("NOT_FOUND", "Student not found", request, status_code=404)
    # Reject re-linking — if a student already has a user_id, the
    # admin must explicitly unlink first (a follow-up endpoint).
    if s.user_id is not None and s.user_id != data.user_id:
        return _err(
            "ALREADY_LINKED",
            "Student is already linked to a different user.",
            request, status_code=409,
        )
    # The `unique=True` constraint on user_id catches the case where
    # the same user is already linked to a different student.
    s.user_id = data.user_id
    actor = uuid.UUID(str(current_user["sub"]))
    from eduzim_shared.audit import record_audit_event
    from app.models.audit import AuditLog
    record_audit_event(
        db, AuditLog, event_type="student.user.linked",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "student", "id": str(student_id),
                "user_id": str(data.user_id)},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {
        "data": {"student_id": str(student_id), "user_id": str(data.user_id)},
        "meta": _meta(request),
    }


# ───── Parent Self-Service ─────

@router.get("/parents/me/children")
def get_my_children(request: Request,
                    db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user),
                    school_id: uuid.UUID = Depends(get_school_id)):
    user_id = current_user.get("sub")
    if not user_id:
        return _err("UNAUTHORIZED", "User identity not found in token", request, status_code=401)
    svc = _svc(db)
    result = svc.get_children_by_user_id(uuid.UUID(user_id), school_id)
    if result is None:
        return _err("NOT_FOUND", "No parent profile linked to this account", request, status_code=404)
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
        return _err(result["error"], result["message"], request, status_code=409)
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
        return _err("NOT_FOUND", "Parent not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
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
    # PH2-7: in-process query helper instead of HTTP call to school-service.
    svc = StudentService(db, school_client=InProcessSchoolClient(db))
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
                     limit: int = Query(200, ge=1, le=500),
                     offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db),
                     school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    return {"data": svc.list_enrollments(school_id, class_id, year_id,
                                          limit=limit, offset=offset),
            "meta": _meta(request)}


@router.put("/enrollments/{enrollment_id}")
def update_enrollment(enrollment_id: uuid.UUID, data: EnrollmentUpdate,
                      request: Request, db: Session = Depends(get_db),
                      current_user: dict = Depends(get_current_user),
                      school_id: uuid.UUID = Depends(get_school_id)):
    svc = _svc(db)
    result = svc.update_enrollment(enrollment_id, school_id, data.status,
                                    data.class_id)
    if result is None:
        return _err("NOT_FOUND", "Enrollment not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=422)
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
