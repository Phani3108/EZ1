"""School Service API Routes — Standard {data, meta} envelope on all responses."""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.dependencies import get_current_user, get_school_id
from app.services.school_service import SchoolService
from app.events import publish_event

router = APIRouter(tags=["School"])

_settings = get_settings()


def verify_internal_token(x_internal_token: str = Header(...)) -> str:
    """Validate X-Internal-Token header on internal endpoints."""
    if x_internal_token != _settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    return x_internal_token


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request, status_code: int = 400):
    """BUG-009 / Phase 4 / Q-006: see note in student_routes.py — the
    previous tuple-return pattern silently turned 404s into 200s."""
    body = {
        "error": {
            "code": code,
            "message": msg,
            "details": {},
            "request_id": _meta(request)["request_id"],
        }
    }
    return JSONResponse(content=body, status_code=status_code)


# ───── Schemas ─────

class SchoolCreate(BaseModel):
    name: str = Field(..., max_length=255)
    country: str = Field("ZW", max_length=5)
    timezone: str = Field("Africa/Harare", max_length=100)

class AcademicYearCreate(BaseModel):
    name: str = Field(..., max_length=50)
    start_date: date
    end_date: date
    is_active: bool = False

class AcademicYearUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None

class TermCreate(BaseModel):
    academic_year_id: uuid.UUID
    name: str = Field(..., max_length=100)
    start_date: date
    end_date: date
    is_active: bool = False

class TermUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None

class ClassCreate(BaseModel):
    name: str = Field(..., max_length=100)
    section: str = Field("A", max_length=20)
    capacity: Optional[int] = None

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    section: Optional[str] = None
    capacity: Optional[int] = None

class SubjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=50)

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

class ClassTeacherCreate(BaseModel):
    class_id: uuid.UUID
    teacher_user_id: uuid.UUID
    academic_year_id: uuid.UUID


class SchoolGeoUpdate(BaseModel):
    province_code: Optional[str] = Field(default=None, max_length=8)
    district_code: Optional[str] = Field(default=None, max_length=16)
    school_type: Optional[str] = Field(default=None, max_length=20)
    principal_name: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    founded_year: Optional[int] = None


# ───── School ─────

@router.post("/schools")
def create_school(data: SchoolCreate, request: Request, db: Session = Depends(get_db),
                  current_user: dict = Depends(get_current_user)):
    svc = SchoolService(db)
    school_id = uuid.uuid4()
    result = svc.create_school(school_id, data.name, data.country, data.timezone)
    publish_event("eduzim.school.school.created.v1", str(school_id), result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/schools/current")
def get_current_school(request: Request, db: Session = Depends(get_db),
                       school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.get_school(school_id)
    if not result:
        return _err("NOT_FOUND", "School not found", request, status_code=404)
    return {"data": result, "meta": _meta(request)}


# ───── Academic Years ─────

@router.post("/academics/years")
def create_academic_year(data: AcademicYearCreate, request: Request,
                         db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.create_academic_year(school_id, data.name, data.start_date,
                                       data.end_date, data.is_active)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    publish_event("eduzim.school.academic_year.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/academics/years")
def list_academic_years(request: Request, db: Session = Depends(get_db),
                        school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    return {"data": svc.list_academic_years(school_id), "meta": _meta(request)}


@router.put("/academics/years/{year_id}")
def update_academic_year(year_id: uuid.UUID, data: AcademicYearUpdate,
                         request: Request, db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.update_academic_year(year_id, school_id, data.name, data.start_date,
                                       data.end_date, data.is_active)
    if result is None:
        return _err("NOT_FOUND", "Academic year not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    return {"data": result, "meta": _meta(request)}


# ───── Terms ─────

@router.post("/academics/terms")
def create_term(data: TermCreate, request: Request,
                db: Session = Depends(get_db),
                current_user: dict = Depends(get_current_user),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.create_term(school_id, data.academic_year_id, data.name,
                              data.start_date, data.end_date, data.is_active)
    if "error" in result:
        code = 409 if result["error"] in ("OVERLAP",) else 422
        return _err(result["error"], result["message"], request), code
    publish_event("eduzim.school.term.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/academics/terms")
def list_terms(request: Request, year_id: uuid.UUID = Query(None),
               db: Session = Depends(get_db),
               school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    return {"data": svc.list_terms(school_id, year_id), "meta": _meta(request)}


@router.put("/academics/terms/{term_id}")
def update_term(term_id: uuid.UUID, data: TermUpdate, request: Request,
                db: Session = Depends(get_db),
                current_user: dict = Depends(get_current_user),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.update_term(term_id, school_id, data.name, data.start_date,
                              data.end_date, data.is_active)
    if result is None:
        return _err("NOT_FOUND", "Term not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    return {"data": result, "meta": _meta(request)}


# ───── Classes ─────

@router.post("/classes")
def create_class(data: ClassCreate, request: Request,
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.create_class(school_id, data.name, data.section, data.capacity)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    publish_event("eduzim.school.class.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/classes")
def list_classes(request: Request, page: int = Query(1, ge=1),
                 page_size: int = Query(50, ge=1, le=100),
                 db: Session = Depends(get_db),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    classes, total = svc.list_classes(school_id, page, page_size)
    meta = _meta(request)
    meta.update({"page": page, "page_size": page_size, "total": total,
                 "has_next": (page * page_size) < total})
    return {"data": classes, "meta": meta}


@router.put("/classes/{class_id}")
def update_class(class_id: uuid.UUID, data: ClassUpdate, request: Request,
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.update_class(class_id, school_id, data.name, data.section, data.capacity)
    if result is None:
        return _err("NOT_FOUND", "Class not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    return {"data": result, "meta": _meta(request)}


@router.delete("/classes/{class_id}")
def delete_class(class_id: uuid.UUID, request: Request,
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.soft_delete_class(class_id, school_id)
    if result is None:
        return _err("NOT_FOUND", "Class not found", request, status_code=404)
    return {"data": result, "meta": _meta(request)}


# ───── Subjects ─────

@router.post("/subjects")
def create_subject(data: SubjectCreate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.create_subject(school_id, data.name, data.code)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    publish_event("eduzim.school.subject.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/subjects")
def list_subjects(request: Request, db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    return {"data": svc.list_subjects(school_id), "meta": _meta(request)}


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: uuid.UUID, data: SubjectUpdate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.update_subject(subject_id, school_id, data.name, data.code)
    if result is None:
        return _err("NOT_FOUND", "Subject not found", request, status_code=404)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    return {"data": result, "meta": _meta(request)}


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: uuid.UUID, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.soft_delete_subject(subject_id, school_id)
    if result is None:
        return _err("NOT_FOUND", "Subject not found", request, status_code=404)
    return {"data": result, "meta": _meta(request)}


# ───── Class Teachers ─────

@router.post("/class-teachers")
def assign_class_teacher(data: ClassTeacherCreate, request: Request,
                         db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    result = svc.assign_class_teacher(school_id, data.class_id,
                                       data.teacher_user_id, data.academic_year_id)
    if "error" in result:
        return _err(result["error"], result["message"], request, status_code=409)
    publish_event("eduzim.school.class_teacher.assigned.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/class-teachers")
def list_class_teachers(request: Request, year_id: uuid.UUID = Query(None),
                        db: Session = Depends(get_db),
                        school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    return {"data": svc.list_class_teachers(school_id, year_id), "meta": _meta(request)}


@router.delete("/class-teachers/{assignment_id}")
def delete_class_teacher(assignment_id: uuid.UUID, request: Request,
                         db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = SchoolService(db)
    success = svc.delete_class_teacher(assignment_id, school_id)
    if not success:
        return _err("NOT_FOUND", "Assignment not found", request, status_code=404)
    return {"data": {"message": "Assignment removed"}, "meta": _meta(request)}


# ───── Teacher Self-Service ─────

@router.get("/teachers/me/classes")
def get_my_classes(request: Request, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    """Return classes assigned to the currently authenticated teacher."""
    teacher_user_id = uuid.UUID(current_user["sub"])
    svc = SchoolService(db)
    classes = svc.get_teacher_classes(teacher_user_id, school_id)
    return {"data": classes, "meta": _meta(request)}


# ───── Internal Endpoints (service-to-service) ─────

@router.get("/internal/teachers/authorize")
def authorize_teacher(request: Request,
                      teacher_user_id: uuid.UUID = Query(...),
                      class_id: uuid.UUID = Query(...),
                      school_id: uuid.UUID = Query(...),
                      db: Session = Depends(get_db),
                      _token: str = Depends(verify_internal_token)):
    """Internal: check if a teacher is assigned to a class. No JWT required."""
    svc = SchoolService(db)
    authorized = svc.is_teacher_authorized_for_class(teacher_user_id, class_id, school_id)
    return {"authorized": authorized}


@router.get("/internal/teachers/authorize-student")
def authorize_teacher_student(request: Request,
                              student_id: uuid.UUID = Query(...),
                              teacher_user_id: uuid.UUID = Query(...),
                              school_id: uuid.UUID = Query(...),
                              class_id: uuid.UUID = Query(...),
                              db: Session = Depends(get_db),
                              _token: str = Depends(verify_internal_token)):
    """Internal: check if a teacher can view a student (via class assignment).

    The caller provides the class_id from enrollment data. This endpoint verifies
    the teacher is assigned to that class in this school.
    """
    svc = SchoolService(db)
    authorized = svc.is_teacher_authorized_for_student(
        teacher_user_id, student_id, school_id, class_id
    )
    return {"authorized": authorized}


# ───── Provinces & Districts (read-only reference) ─────

@router.get("/provinces")
def list_provinces(request: Request, db: Session = Depends(get_db)):
    """Public-ish reference listing — no school_id needed. Auth still required."""
    svc = SchoolService(db)
    return {"data": svc.list_provinces(), "meta": _meta(request)}


@router.get("/provinces/{code}")
def get_province(code: str, request: Request, db: Session = Depends(get_db)):
    svc = SchoolService(db)
    p = svc.get_province(code)
    if not p:
        raise HTTPException(status_code=404, detail=_err("NOT_FOUND", "Province not found", request))
    districts = svc.list_districts(province_code=code)
    return {"data": {**p, "districts": districts}, "meta": _meta(request)}


@router.get("/districts")
def list_districts(request: Request,
                   province_code: Optional[str] = Query(default=None, max_length=8),
                   db: Session = Depends(get_db)):
    svc = SchoolService(db)
    return {"data": svc.list_districts(province_code=province_code), "meta": _meta(request)}


@router.patch("/schools/current/geo")
def update_current_school_geo(data: SchoolGeoUpdate, request: Request,
                              db: Session = Depends(get_db),
                              school_id: uuid.UUID = Depends(get_school_id),
                              current_user: dict = Depends(get_current_user)):
    """Set or update a school's geography + profile metadata."""
    svc = SchoolService(db)
    result = svc.update_school_geo(
        school_id,
        province_code=data.province_code,
        district_code=data.district_code,
        school_type=data.school_type,
        principal_name=data.principal_name,
        address=data.address,
        phone=data.phone,
        email=data.email,
        founded_year=data.founded_year,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=_err("NOT_FOUND", "School not found", request))
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=_err(result["error"], result["message"], request))
    return {"data": result, "meta": _meta(request)}
