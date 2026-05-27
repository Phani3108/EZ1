"""Ministry (MoPSE) cross-school aggregation endpoints — Phase 14.

DEC-013: Ministry is viewer + auditor only. NO write/update/delete verbs.
Every endpoint here is GET. Every query spans MULTIPLE schools — this is
the one place in academics where the usual `school_id` scoping is
deliberately broken; the substitute defence is:

  1. Gateway RBAC: `ministry:read` permission required on every path
     under `/api/v1/ministry/...`. The Ministry role is the only one
     that holds this permission.
  2. Route layer (this file): every endpoint asserts that the actor has
     the `Ministry` role explicitly via `_require_ministry`. Defence-
     in-depth — if RBAC is misconfigured at the gateway, callers still
     hit a 403 here.
  3. Audit: every aggregation call is recorded (target = scope code,
     details = endpoint name + counts; per ADR 018, NO names / NO row
     ids / NO PII are logged).

Aggregation grain:
  * district  — group by district_code
  * province  — group by province_code
  * national  — single row covering all schools the actor can see

The actor's `X-School-Id` header is IGNORED on these endpoints — there
is no single tenant. The header `X-Permissions: ministry:read` plus the
`Ministry` role is what unlocks the surface.

M-001 — role provisioning lives in scripts/seed-baseline.sh.
M-002 — this whole file is the aggregation API.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.school import (
    School, Province, District, Class, ClassTeacherAssignment, Subject,
)
from app.models.student import Student, StudentStatus
from app.models.attendance import AttendanceRecord
from app.models.assessment import Assessment, Mark
from app.models.compliance import (
    ComplianceReportTemplate, ComplianceReportSubmission,
)
from app.models.community import Sponsorship, Sponsor
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
from eduzim_shared.auth import ActorContext


router = APIRouter(tags=["Ministry"])


VALID_SCOPES = {"district", "province", "national"}

# Cross-school sentinel: the AuditLog school_id column is NOT NULL by
# legacy invariant (every domain row carries a tenant). Ministry queries
# span all schools; we use a deterministic non-zero UUID5 as the
# "no single tenant" marker so the audit row still satisfies NOT NULL
# AND can be filtered out of any per-school audit dashboard with a
# WHERE school_id = '<this constant>' predicate. Documented in ADR 020.
#
# All-zeros UUID is deliberately avoided here — it round-trips poorly
# through some sqlalchemy/sqlite stacks (the column value can come back
# as integer 0 rather than the UUID, breaking uuid.UUID(hex=…)).
CROSS_SCHOOL_SENTINEL = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code: str, msg: str, request: Request, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request: Request):
    return {"data": data, "meta": _meta(request)}


def _require_ministry(current_user, request: Request):
    """Route-layer Ministry-role gate. Returns None on success, or a
    JSONResponse (403) that the caller should immediately return.

    Defence-in-depth: gateway RBAC already enforces `ministry:read`, but
    a misconfigured RBAC map would silently expose cross-school data.
    This gate is the second wall.
    """
    has_role = False
    if isinstance(current_user, ActorContext):
        has_role = current_user.has_role("Ministry")
    elif hasattr(current_user, "get"):
        roles = current_user.get("roles", []) or []
        has_role = "Ministry" in roles
    if not has_role:
        return _err(
            "FORBIDDEN",
            "Ministry role required for cross-school aggregation.",
            request, status_code=403,
        )
    return None


def _actor_id(current_user) -> Optional[uuid.UUID]:
    if isinstance(current_user, ActorContext):
        return current_user.user_id
    try:
        return uuid.UUID(str(current_user["sub"]))
    except Exception:
        return None


def _audit(db: Session, current_user, event_type: str, scope: str, count: int):
    """Audit a Ministry read. Per ADR 018: NO row ids, NO names, NO PII
    in `details`. We log:
      - target = the scope label ("national", "province:HRE", etc.)
      - details = {"endpoint": event_type, "rows": <int>}
    """
    actor = _actor_id(current_user)
    try:
        record_audit_event(
            db,
            AuditLog,
            event_type=event_type,
            actor_user_id=actor,
            school_id=CROSS_SCHOOL_SENTINEL,   # see ADR 020
            target=scope,
            details={"endpoint": event_type, "rows": int(count)},
        )
        # Ministry endpoints are read-only — they make no other db
        # changes, so we must commit explicitly here or the audit row is
        # lost when the request session closes.
        db.commit()
    except Exception:
        # Audit must never break a read.
        try:
            db.rollback()
        except Exception:
            pass


# ─── M-002 — Schools index (scope + counts; no PII) ────────────────


@router.get("/ministry/schools")
def ministry_schools_index(
    request: Request,
    province_code: Optional[str] = Query(None),
    district_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Light index of schools visible to Ministry.

    Returns: id, name, province_code, district_code, school_type,
    is_active. Does NOT return contact info, principal name, address
    — Ministry sees aggregates, not staff PII.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    q = db.query(School)
    if province_code:
        q = q.filter(School.province_code == province_code)
    if district_code:
        q = q.filter(School.district_code == district_code)
    q = q.order_by(School.name.asc())
    rows = q.all()
    out = [
        {
            "id": str(s.id),
            "name": s.name,
            "province_code": s.province_code,
            "district_code": s.district_code,
            "school_type": s.school_type,
            "is_active": bool(s.is_active),
        }
        for s in rows
    ]
    _audit(db, current_user, "ministry.schools.indexed",
           f"province:{province_code or '*'}|district:{district_code or '*'}",
           len(out))
    return _ok(out, request)


# ─── M-002 — Enrolment rollup ──────────────────────────────────────


@router.get("/ministry/enrolment")
def ministry_enrolment(
    request: Request,
    scope: str = Query("national", description="district | province | national"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Active student count grouped by scope.

    - scope=district  → rows = [{district_code, district_name, schools, students}, ...]
    - scope=province  → rows = [{province_code, province_name, schools, students}, ...]
    - scope=national  → single row {schools, students}
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE",
                    f"scope must be one of {sorted(VALID_SCOPES)}",
                    request, status_code=400)

    active = StudentStatus.ACTIVE.value

    if scope == "national":
        schools_n = db.query(func.count(distinct(School.id))).scalar() or 0
        students_n = (
            db.query(func.count(Student.id))
            .filter(Student.status == active)
            .scalar() or 0
        )
        out = {"schools": int(schools_n), "students": int(students_n)}
        _audit(db, current_user, "ministry.enrolment.read", "national", 1)
        return _ok(out, request)

    if scope == "province":
        # Join schools→provinces; aggregate students per province via
        # a correlated subquery on Student.school_id ∈ schools-in-province.
        rows = (
            db.query(
                School.province_code.label("code"),
                Province.name.label("name"),
                func.count(distinct(School.id)).label("schools"),
            )
            .outerjoin(Province, Province.code == School.province_code)
            .group_by(School.province_code, Province.name)
            .all()
        )
        # Student counts: join Student → School(province_code).
        st = (
            db.query(
                School.province_code.label("code"),
                func.count(Student.id).label("students"),
            )
            .join(Student, Student.school_id == School.id)
            .filter(Student.status == active)
            .group_by(School.province_code)
            .all()
        )
        st_map = {r.code: int(r.students) for r in st}
        out = [
            {
                "province_code": r.code,
                "province_name": r.name,
                "schools": int(r.schools),
                "students": st_map.get(r.code, 0),
            }
            for r in rows
        ]
        _audit(db, current_user, "ministry.enrolment.read", "province", len(out))
        return _ok(out, request)

    # district
    rows = (
        db.query(
            School.district_code.label("code"),
            District.name.label("name"),
            District.province_code.label("province_code"),
            func.count(distinct(School.id)).label("schools"),
        )
        .outerjoin(District, District.code == School.district_code)
        .group_by(School.district_code, District.name, District.province_code)
        .all()
    )
    st = (
        db.query(
            School.district_code.label("code"),
            func.count(Student.id).label("students"),
        )
        .join(Student, Student.school_id == School.id)
        .filter(Student.status == active)
        .group_by(School.district_code)
        .all()
    )
    st_map = {r.code: int(r.students) for r in st}
    out = [
        {
            "district_code": r.code,
            "district_name": r.name,
            "province_code": r.province_code,
            "schools": int(r.schools),
            "students": st_map.get(r.code, 0),
        }
        for r in rows
    ]
    _audit(db, current_user, "ministry.enrolment.read", "district", len(out))
    return _ok(out, request)


# ─── M-002 — Attendance rate rollup ────────────────────────────────


@router.get("/ministry/attendance")
def ministry_attendance(
    request: Request,
    scope: str = Query("national"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Attendance rate over a trailing window, grouped by scope.

    Rate = P / (P + A + L). Status codes: P=present, A=absent, L=late.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE", "scope invalid", request, status_code=400)

    since = date.today() - timedelta(days=days)
    present_n = func.sum(case((AttendanceRecord.status == "P", 1), else_=0))
    total_n = func.count(AttendanceRecord.id)

    # NOTE: SQLAlchemy 2.0 deprecates `Row.t` / `Row.c` etc. — using
    # underscore-prefixed labels avoids the conflict.

    if scope == "national":
        agg = (
            db.query(
                present_n.label("present_n"),
                total_n.label("total_n"),
            )
            .select_from(AttendanceRecord)
            .join(School, School.id == AttendanceRecord.school_id)
            .filter(AttendanceRecord.date >= since)
            .one()
        )
        p, t = int(agg.present_n or 0), int(agg.total_n or 0)
        out = {
            "days": days,
            "records": t,
            "present": p,
            "rate": (round(p / t, 4) if t else None),
        }
        _audit(db, current_user, "ministry.attendance.read", "national", t)
        return _ok(out, request)

    if scope == "province":
        rows = (
            db.query(
                School.province_code.label("code"),
                present_n.label("present_n"),
                total_n.label("total_n"),
            )
            .select_from(AttendanceRecord)
            .join(School, School.id == AttendanceRecord.school_id)
            .filter(AttendanceRecord.date >= since)
            .group_by(School.province_code)
            .all()
        )
        out = [
            {
                "province_code": r.code,
                "records": int(r.total_n or 0),
                "present": int(r.present_n or 0),
                "rate": (
                    round(int(r.present_n or 0) / int(r.total_n), 4)
                    if r.total_n else None
                ),
            }
            for r in rows
        ]
        _audit(db, current_user, "ministry.attendance.read", "province", len(out))
        return _ok(out, request)

    rows = (
        db.query(
            School.district_code.label("code"),
            present_n.label("present_n"),
            total_n.label("total_n"),
        )
        .select_from(AttendanceRecord)
        .join(School, School.id == AttendanceRecord.school_id)
        .filter(AttendanceRecord.date >= since)
        .group_by(School.district_code)
        .all()
    )
    out = [
        {
            "district_code": r.code,
            "records": int(r.total_n or 0),
            "present": int(r.present_n or 0),
            "rate": (
                round(int(r.present_n or 0) / int(r.total_n), 4)
                if r.total_n else None
            ),
        }
        for r in rows
    ]
    _audit(db, current_user, "ministry.attendance.read", "district", len(out))
    return _ok(out, request)


# ─── M-002 — Geography reference ───────────────────────────────────


@router.get("/ministry/geography")
def ministry_geography(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Province + district reference data (for client geomap labels)."""
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    provs = db.query(Province).order_by(Province.name.asc()).all()
    dists = db.query(District).order_by(District.name.asc()).all()
    out = {
        "provinces": [
            {"code": p.code, "name": p.name, "region": p.region,
             "capital": p.capital, "country": p.country}
            for p in provs
        ],
        "districts": [
            {"code": d.code, "name": d.name, "province_code": d.province_code}
            for d in dists
        ],
    }
    _audit(db, current_user, "ministry.geography.read",
           "national", len(out["provinces"]) + len(out["districts"]))
    return _ok(out, request)


# ─── M-004 — Compliance dashboard (cross-school) ───────────────────


@router.get("/ministry/compliance")
def ministry_compliance(
    request: Request,
    period_label: Optional[str] = Query(
        None,
        description="Optional period to filter on (e.g., '2026-Q1', '2026'). "
                    "If omitted, returns rollup across all periods.",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Compliance report submission status — which schools filed what.

    For each (school_id, template_code) pair, returns the submission
    counts by status. The admin-web Ministry dashboard renders this as
    a "schools missing reports" view by joining with the geography
    reference data.

    Each row:
      * school_id       — UUID (string)
      * template_code   — template's `code` (e.g., 'ANNUAL_STAT_RETURN')
      * template_title  — human-readable title (no PII)
      * draft           — count of submissions in 'draft' state
      * submitted       — count of submissions in 'submitted' state
      * accepted        — count of submissions in 'accepted' state
      * rejected        — count of submissions in 'rejected' state
      * total           — sum of the four counts

    PII invariant: no submitter names, no payload contents, no
    rejection_notes are returned. Just counts + the school's UUID +
    the template code/title (template title is non-PII — it's the
    Ministry-side template name).
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e

    # Pull template metadata once (small — at most a few dozen rows).
    templates = db.query(ComplianceReportTemplate).all()
    tpl_by_id = {t.id: t for t in templates}

    q = (
        db.query(
            ComplianceReportSubmission.school_id.label("school_id"),
            ComplianceReportSubmission.template_id.label("template_id"),
            ComplianceReportSubmission.status.label("status"),
            func.count(ComplianceReportSubmission.id).label("n"),
        )
        .group_by(
            ComplianceReportSubmission.school_id,
            ComplianceReportSubmission.template_id,
            ComplianceReportSubmission.status,
        )
    )
    if period_label:
        q = q.filter(ComplianceReportSubmission.period_label == period_label)

    rows = q.all()

    # Reshape: one row per (school, template), with all statuses as cols.
    grouped: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (str(r.school_id), str(r.template_id))
        tpl = tpl_by_id.get(r.template_id)
        sl = grouped.setdefault(key, {
            "school_id": str(r.school_id),
            "template_id": str(r.template_id),
            "template_code": tpl.code if tpl else "(unknown)",
            "template_title": tpl.title if tpl else "(unknown)",
            "draft": 0, "submitted": 0, "accepted": 0, "rejected": 0,
            "total": 0,
        })
        n = int(r.n or 0)
        if r.status in ("draft", "submitted", "accepted", "rejected"):
            sl[r.status] = n
        sl["total"] = sl["draft"] + sl["submitted"] + sl["accepted"] + sl["rejected"]

    out = sorted(grouped.values(),
                 key=lambda x: (x["school_id"], x["template_code"]))
    _audit(db, current_user, "ministry.compliance.read",
           f"period:{period_label or '*'}", len(out))
    return _ok(out, request)


# ─── M-005 — Dropout heatmap by district / province ────────────────


# Status values that indicate a student is no longer actively enrolled
# in this school. GRADUATED is NOT a dropout — it's a successful exit.
DROPOUT_STATUSES = (
    StudentStatus.INACTIVE.value,
    StudentStatus.TRANSFERRED.value,
)


@router.get("/ministry/dropouts")
def ministry_dropouts(
    request: Request,
    scope: str = Query("district"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dropout / inactive student counts grouped by scope.

    A student counts as a dropout if their `status` is INACTIVE or
    TRANSFERRED. GRADUATED is explicitly excluded (successful exit).

    Returns one row per scope key with:
      * active           — count of ACTIVE students
      * dropouts         — count of INACTIVE + TRANSFERRED students
      * dropout_rate     — dropouts / (active + dropouts), rounded 4dp.
                           Null when denominator is 0.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE", "scope invalid", request, status_code=400)

    active_n = func.sum(
        case((Student.status == StudentStatus.ACTIVE.value, 1), else_=0)
    )
    drop_n = func.sum(
        case((Student.status.in_(DROPOUT_STATUSES), 1), else_=0)
    )

    def _shape(active, drop):
        denom = active + drop
        return (
            round(drop / denom, 4) if denom > 0 else None
        )

    if scope == "national":
        agg = (
            db.query(active_n.label("a"), drop_n.label("d"))
            .select_from(Student)
            .join(School, School.id == Student.school_id)
            .one()
        )
        a, d = int(agg.a or 0), int(agg.d or 0)
        out = {"active": a, "dropouts": d, "dropout_rate": _shape(a, d)}
        _audit(db, current_user, "ministry.dropouts.read", "national", 1)
        return _ok(out, request)

    if scope == "province":
        rows = (
            db.query(
                School.province_code.label("code"),
                active_n.label("a"),
                drop_n.label("d"),
            )
            .select_from(Student)
            .join(School, School.id == Student.school_id)
            .group_by(School.province_code)
            .all()
        )
        out = [
            {
                "province_code": r.code,
                "active": int(r.a or 0),
                "dropouts": int(r.d or 0),
                "dropout_rate": _shape(int(r.a or 0), int(r.d or 0)),
            }
            for r in rows
        ]
        _audit(db, current_user, "ministry.dropouts.read", "province", len(out))
        return _ok(out, request)

    rows = (
        db.query(
            School.district_code.label("code"),
            active_n.label("a"),
            drop_n.label("d"),
        )
        .select_from(Student)
        .join(School, School.id == Student.school_id)
        .group_by(School.district_code)
        .all()
    )
    out = [
        {
            "district_code": r.code,
            "active": int(r.a or 0),
            "dropouts": int(r.d or 0),
            "dropout_rate": _shape(int(r.a or 0), int(r.d or 0)),
        }
        for r in rows
    ]
    _audit(db, current_user, "ministry.dropouts.read", "district", len(out))
    return _ok(out, request)


# ─── M-006 — Subject pass-rate by region ───────────────────────────


# Pass threshold: 50% of max_marks. Configurable per-country via a
# future settings table; hard-coded to Zimbabwe ZIMSEC convention
# (50 % = E grade boundary) for now.
PASS_THRESHOLD_RATIO = 0.5


@router.get("/ministry/pass-rate")
def ministry_pass_rate(
    request: Request,
    scope: str = Query("province"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Subject pass-rate aggregated by scope.

    A mark is a PASS if `marks >= max_marks * 0.5` AND `is_absent =
    False`. Absent marks (is_absent=True) are excluded from the
    denominator entirely — they're neither pass nor fail.

    Returns one row per (scope_code, subject_id):
      * subject_id    — UUID string. The Subject row is per-school in
                        academics, so the same subject CODE may have
                        several IDs across schools; this endpoint
                        returns IDs (the admin-web client can
                        de-duplicate by name if needed).
      * subject_name  — non-PII
      * graded        — count of non-absent marks
      * passes        — count of marks at or above 50 % of max_marks
      * pass_rate     — passes / graded, 4dp; null when graded=0
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE", "scope invalid", request, status_code=400)

    pass_predicate = case(
        (
            (Mark.is_absent == False)  # noqa: E712
            & (Mark.marks >= Assessment.max_marks * PASS_THRESHOLD_RATIO),
            1,
        ),
        else_=0,
    )
    graded_predicate = case((Mark.is_absent == False, 1), else_=0)  # noqa: E712

    # NOTE: Mark.school_id / Assessment.subject_id are `String(36)`
    # (UUID_STR) while School.id / Subject.id are `UUID(as_uuid=True)`.
    # On SQLite these store different hex shapes (32 chars no-hyphens
    # vs 36 chars with-hyphens), so cross-type DB-level joins are
    # unreliable. We aggregate first with string-only joins, then look
    # up Subject + School metadata in separate queries and merge in
    # Python — this is the same shape PostgreSQL would produce in
    # production (both columns are UUIDs there).
    rows = (
        db.query(
            Mark.school_id.label("school_id"),
            Assessment.subject_id.label("subject_id"),
            func.sum(graded_predicate).label("graded"),
            func.sum(pass_predicate).label("passes"),
        )
        .select_from(Mark)
        .join(Assessment, Assessment.id == Mark.assessment_id)
        .group_by(Mark.school_id, Assessment.subject_id)
        .all()
    )

    # Build subject_id (str) → subject_name map.
    subjects = db.query(Subject.id, Subject.name).all()
    subject_name_by_id: dict[str, str] = {str(sid): name for (sid, name) in subjects}

    # Build school_id (str) → (province_code, district_code) map.
    schools = db.query(School.id, School.province_code, School.district_code).all()
    school_geo: dict[str, tuple[Optional[str], Optional[str]]] = {
        str(sid): (pc, dc) for (sid, pc, dc) in schools
    }

    def _shape(graded, passes):
        g, p = int(graded or 0), int(passes or 0)
        return g, p, (round(p / g, 4) if g else None)

    if scope == "national":
        agg: dict[str, dict] = {}
        for r in rows:
            sid = str(r.subject_id)
            cur = agg.setdefault(sid, {
                "subject_id": sid,
                "subject_name": subject_name_by_id.get(sid, "(unknown)"),
                "graded": 0,
                "passes": 0,
            })
            cur["graded"] += int(r.graded or 0)
            cur["passes"] += int(r.passes or 0)
        for row in agg.values():
            g, p, rate = _shape(row["graded"], row["passes"])
            row["graded"] = g
            row["passes"] = p
            row["pass_rate"] = rate
        out = list(agg.values())
        _audit(db, current_user, "ministry.pass_rate.read", "national", len(out))
        return _ok(out, request)

    # province / district: bucket by (scope_code, subject_id)
    code_key = "province_code" if scope == "province" else "district_code"
    bucket: dict[tuple, dict] = {}
    for r in rows:
        prov, dist = school_geo.get(str(r.school_id), (None, None))
        code = prov if scope == "province" else dist
        sid = str(r.subject_id)
        key = (code, sid)
        cur = bucket.setdefault(key, {
            code_key: code,
            "subject_id": sid,
            "subject_name": subject_name_by_id.get(sid, "(unknown)"),
            "graded": 0,
            "passes": 0,
        })
        cur["graded"] += int(r.graded or 0)
        cur["passes"] += int(r.passes or 0)
    for row in bucket.values():
        g, p, rate = _shape(row["graded"], row["passes"])
        row["graded"] = g
        row["passes"] = p
        row["pass_rate"] = rate
    out = list(bucket.values())
    _audit(db, current_user, "ministry.pass_rate.read", scope, len(out))
    return _ok(out, request)


# ─── M-007 — Resource allocation (PTR for v1) ──────────────────────


@router.get("/ministry/ptr")
def ministry_ptr(
    request: Request,
    scope: str = Query("district"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Pupil:Teacher Ratio (PTR) by scope.

    PTR = active students / distinct active teachers, where a teacher
    is any `ClassTeacherAssignment.teacher_user_id` for an active
    class in the school.

    Returns one row per scope key:
      * active_students  — count of ACTIVE students
      * teachers         — count of distinct teacher_user_id with
                           at least one class assignment
      * ptr              — students / teachers, rounded 2dp; null
                           when teachers = 0

    NOTE on M-007 scope: device counts and electricity coverage are
    NOT in this endpoint — they need a `SchoolFacility` model that
    has not been built yet. The Ministry dashboard renders PTR now
    and will add devices/electricity in a follow-up sub-phase. The
    placeholder fields are returned as `null` so the client contract
    is stable.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE", "scope invalid", request, status_code=400)

    active = StudentStatus.ACTIVE.value

    def _shape(students, teachers):
        return {
            "active_students": int(students),
            "teachers": int(teachers),
            "ptr": (
                round(students / teachers, 2)
                if teachers > 0 else None
            ),
            # M-007 follow-up — not yet wired:
            "devices_per_school": None,
            "electricity_coverage": None,
        }

    # Two sub-queries (students by scope, teachers by scope), then
    # merged in Python. Doing this with a single SQL would require
    # FULL OUTER JOIN which sqlite lacks.
    if scope == "national":
        students_n = (
            db.query(func.count(Student.id))
            .filter(Student.status == active)
            .scalar() or 0
        )
        teachers_n = (
            db.query(func.count(distinct(ClassTeacherAssignment.teacher_user_id)))
            .scalar() or 0
        )
        out = {**_shape(students_n, teachers_n)}
        _audit(db, current_user, "ministry.ptr.read", "national", 1)
        return _ok(out, request)

    if scope == "province":
        s_rows = (
            db.query(
                School.province_code.label("code"),
                func.count(Student.id).label("n"),
            )
            .select_from(Student)
            .join(School, School.id == Student.school_id)
            .filter(Student.status == active)
            .group_by(School.province_code)
            .all()
        )
        t_rows = (
            db.query(
                School.province_code.label("code"),
                func.count(distinct(ClassTeacherAssignment.teacher_user_id)).label("n"),
            )
            .select_from(ClassTeacherAssignment)
            .join(School, School.id == ClassTeacherAssignment.school_id)
            .group_by(School.province_code)
            .all()
        )
        smap = {r.code: int(r.n or 0) for r in s_rows}
        tmap = {r.code: int(r.n or 0) for r in t_rows}
        codes = set(smap) | set(tmap)
        out = [
            {"province_code": c, **_shape(smap.get(c, 0), tmap.get(c, 0))}
            for c in sorted(codes, key=lambda x: (x is None, x))
        ]
        _audit(db, current_user, "ministry.ptr.read", "province", len(out))
        return _ok(out, request)

    s_rows = (
        db.query(
            School.district_code.label("code"),
            func.count(Student.id).label("n"),
        )
        .select_from(Student)
        .join(School, School.id == Student.school_id)
        .filter(Student.status == active)
        .group_by(School.district_code)
        .all()
    )
    t_rows = (
        db.query(
            School.district_code.label("code"),
            func.count(distinct(ClassTeacherAssignment.teacher_user_id)).label("n"),
        )
        .select_from(ClassTeacherAssignment)
        .join(School, School.id == ClassTeacherAssignment.school_id)
        .group_by(School.district_code)
        .all()
    )
    smap = {r.code: int(r.n or 0) for r in s_rows}
    tmap = {r.code: int(r.n or 0) for r in t_rows}
    codes = set(smap) | set(tmap)
    out = [
        {"district_code": c, **_shape(smap.get(c, 0), tmap.get(c, 0))}
        for c in sorted(codes, key=lambda x: (x is None, x))
    ]
    _audit(db, current_user, "ministry.ptr.read", "district", len(out))
    return _ok(out, request)


# ─── M-008 — Comparative view (per-school, anonymisable) ───────────


@router.get("/ministry/comparative")
def ministry_comparative(
    request: Request,
    province_code: Optional[str] = Query(None),
    district_code: Optional[str] = Query(None),
    anonymize: bool = Query(
        False,
        description="If true, school names are replaced with pseudonyms "
                    "('School-A', 'School-B', …) and contact info is "
                    "stripped. Ministry uses this for inter-school "
                    "comparison reports they don't want to publish "
                    "with names attached.",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Per-school side-by-side comparative metrics.

    For each school in the (optional) filter scope, return:
      * label              — school name OR pseudonym (when anonymized)
      * province_code, district_code
      * active_students    — count of ACTIVE students
      * dropouts           — count of INACTIVE + TRANSFERRED
      * teachers           — distinct teachers with class assignments
      * ptr                — students / teachers (null when teachers=0)

    Use this for "compare 5 schools in District X" style charts.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e

    q = db.query(School)
    if province_code:
        q = q.filter(School.province_code == province_code)
    if district_code:
        q = q.filter(School.district_code == district_code)
    schools = q.order_by(School.name.asc()).all()
    school_ids = [s.id for s in schools]

    if not school_ids:
        return _ok([], request)

    # Student aggregations grouped by school_id.
    active = StudentStatus.ACTIVE.value
    stu = (
        db.query(
            Student.school_id.label("sid"),
            func.sum(case((Student.status == active, 1), else_=0)).label("a"),
            func.sum(
                case((Student.status.in_(DROPOUT_STATUSES), 1), else_=0)
            ).label("d"),
        )
        .filter(Student.school_id.in_(school_ids))
        .group_by(Student.school_id)
        .all()
    )
    stu_map = {str(r.sid): (int(r.a or 0), int(r.d or 0)) for r in stu}

    # Teacher counts by school.
    t = (
        db.query(
            ClassTeacherAssignment.school_id.label("sid"),
            func.count(distinct(ClassTeacherAssignment.teacher_user_id)).label("n"),
        )
        .filter(ClassTeacherAssignment.school_id.in_(school_ids))
        .group_by(ClassTeacherAssignment.school_id)
        .all()
    )
    t_map = {str(r.sid): int(r.n or 0) for r in t}

    out = []
    for idx, s in enumerate(schools):
        sid = str(s.id)
        active_n, drop_n = stu_map.get(sid, (0, 0))
        t_n = t_map.get(sid, 0)
        label = f"School-{chr(ord('A') + idx % 26)}{idx // 26 or ''}" if anonymize else s.name
        out.append({
            "school_id": None if anonymize else sid,
            "label": label,
            "province_code": s.province_code,
            "district_code": s.district_code,
            "active_students": active_n,
            "dropouts": drop_n,
            "teachers": t_n,
            "ptr": (round(active_n / t_n, 2) if t_n else None),
        })

    _audit(
        db, current_user, "ministry.comparative.read",
        f"province:{province_code or '*'}|district:{district_code or '*'}"
        f"|anonymize:{str(anonymize).lower()}",
        len(out),
    )
    return _ok(out, request)


# ─── M-009 — Policy impact (before/after) ──────────────────────────


@router.get("/ministry/policy-impact")
def ministry_policy_impact(
    request: Request,
    metric: str = Query(
        "attendance_rate",
        description="attendance_rate | dropout_rate",
    ),
    before_start: date = Query(...),
    before_end: date = Query(...),
    after_start: date = Query(...),
    after_end: date = Query(...),
    province_code: Optional[str] = Query(None),
    district_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Compute a metric for two date windows (before / after) so the
    Ministry can quantify the effect of a policy intervention.

    Supported metrics:
      * attendance_rate — present / total attendance records in the window.
      * dropout_rate    — INACTIVE+TRANSFERRED students whose record was
                          last updated in the window.

    Returns:
      {
        "metric": <name>,
        "before": {"value": <float|null>, "n": <int>,
                   "window": [<from>, <to>]},
        "after":  {"value": <float|null>, "n": <int>,
                   "window": [<from>, <to>]},
        "delta":  <after - before, or null>,
      }
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if metric not in ("attendance_rate", "dropout_rate"):
        return _err("INVALID_METRIC",
                    "metric must be attendance_rate or dropout_rate",
                    request, status_code=400)
    if before_start >= before_end or after_start >= after_end:
        return _err("INVALID_WINDOW",
                    "each window must have start < end", request,
                    status_code=400)

    # Optionally filter to schools in scope.
    school_q = db.query(School.id)
    if province_code:
        school_q = school_q.filter(School.province_code == province_code)
    if district_code:
        school_q = school_q.filter(School.district_code == district_code)
    in_scope_ids = [r[0] for r in school_q.all()]

    def _attendance_window(start: date, end: date):
        q = db.query(
            func.count(AttendanceRecord.id).label("total"),
            func.sum(case((AttendanceRecord.status == "P", 1), else_=0)).label("present"),
        ).filter(
            AttendanceRecord.date >= start,
            AttendanceRecord.date < end,
        )
        if province_code or district_code:
            q = q.filter(AttendanceRecord.school_id.in_(in_scope_ids))
        row = q.one()
        total = int(row.total or 0)
        present = int(row.present or 0)
        return {
            "value": (round(present / total, 4) if total else None),
            "n": total,
            "window": [start.isoformat(), end.isoformat()],
        }

    def _dropout_window(start: date, end: date):
        # Use Student.updated_at as the "as of" timestamp. Counts
        # students whose status is currently a dropout AND were last
        # touched in the window. Approximate by definition — see ADR
        # 020 follow-up notes.
        q = db.query(func.count(Student.id)).filter(
            Student.status.in_(DROPOUT_STATUSES),
            Student.updated_at >= start,
            Student.updated_at < end,
        )
        if province_code or district_code:
            q = q.filter(Student.school_id.in_(in_scope_ids))
        n = int(q.scalar() or 0)
        # Denominator: total students who were active OR dropped out in
        # the same window (counted by updated_at, same logic).
        total_q = db.query(func.count(Student.id)).filter(
            Student.status.in_(
                tuple(DROPOUT_STATUSES) + (StudentStatus.ACTIVE.value,)
            ),
            Student.updated_at >= start,
            Student.updated_at < end,
        )
        if province_code or district_code:
            total_q = total_q.filter(Student.school_id.in_(in_scope_ids))
        denom = int(total_q.scalar() or 0)
        return {
            "value": (round(n / denom, 4) if denom else None),
            "n": denom,
            "window": [start.isoformat(), end.isoformat()],
        }

    if metric == "attendance_rate":
        before = _attendance_window(before_start, before_end)
        after = _attendance_window(after_start, after_end)
    else:
        before = _dropout_window(before_start, before_end)
        after = _dropout_window(after_start, after_end)

    delta = None
    if before["value"] is not None and after["value"] is not None:
        delta = round(after["value"] - before["value"], 4)

    out = {
        "metric": metric,
        "before": before,
        "after": after,
        "delta": delta,
    }
    _audit(db, current_user, "ministry.policy_impact.read",
           f"metric:{metric}|scope:p={province_code or '*'};d={district_code or '*'}",
           1)
    return _ok(out, request)


# ─── M-010 — Donor / NGO impact (Sponsorships) ─────────────────────


@router.get("/ministry/donors")
def ministry_donors(
    request: Request,
    scope: str = Query("national"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Sponsor / donor impact by scope.

    Aggregates from Phase 13d's `sponsorships` table — each row is one
    commitment from a sponsor to a school. We sum committed and
    received cents per scope, and return counts of active sponsorships.

    PII: this endpoint returns AMOUNTS (sponsor commitments and
    receipts ARE the audit story for a donor-impact dashboard — per
    ADR 018 it's a money story). No sponsor names are returned. No
    rejection notes.

    Returned amounts are in **dollars** (committed_cents / 100), to
    match the rest of the Ministry dashboard's display units.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e
    if scope not in VALID_SCOPES:
        return _err("INVALID_SCOPE", "scope invalid", request, status_code=400)

    # Build school_id (str) → geo map; sponsorship.school_id is
    # String(36) so we group by it then merge in Python.
    schools = db.query(School.id, School.province_code, School.district_code).all()
    geo = {str(sid): (pc, dc) for (sid, pc, dc) in schools}

    rows = (
        db.query(
            Sponsorship.school_id.label("sid"),
            func.count(Sponsorship.id).label("n"),
            func.coalesce(func.sum(Sponsorship.committed_cents), 0).label("committed"),
            func.coalesce(func.sum(Sponsorship.received_cents), 0).label("received"),
        )
        .group_by(Sponsorship.school_id)
        .all()
    )

    def _to_dollars(cents):
        return round((int(cents or 0)) / 100.0, 2)

    if scope == "national":
        committed = sum(int(r.committed or 0) for r in rows)
        received = sum(int(r.received or 0) for r in rows)
        n = sum(int(r.n or 0) for r in rows)
        out = {
            "sponsorships": n,
            "committed": _to_dollars(committed),
            "received": _to_dollars(received),
            "fulfilment_rate": (
                round(received / committed, 4) if committed else None
            ),
        }
        _audit(db, current_user, "ministry.donors.read", "national", 1)
        return _ok(out, request)

    bucket: dict[Optional[str], dict] = {}
    code_key = "province_code" if scope == "province" else "district_code"
    for r in rows:
        prov, dist = geo.get(str(r.sid), (None, None))
        code = prov if scope == "province" else dist
        cur = bucket.setdefault(code, {
            code_key: code,
            "sponsorships": 0,
            "committed_cents": 0,
            "received_cents": 0,
        })
        cur["sponsorships"] += int(r.n or 0)
        cur["committed_cents"] += int(r.committed or 0)
        cur["received_cents"] += int(r.received or 0)

    out = []
    for row in bucket.values():
        committed = row.pop("committed_cents")
        received = row.pop("received_cents")
        row["committed"] = _to_dollars(committed)
        row["received"] = _to_dollars(received)
        row["fulfilment_rate"] = (
            round(received / committed, 4) if committed else None
        )
        out.append(row)
    _audit(db, current_user, "ministry.donors.read", scope, len(out))
    return _ok(out, request)


# ─── M-011 — UNESCO / UNICEF export snapshot ───────────────────────


@router.get("/ministry/exports/unesco")
def ministry_exports_unesco(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Canonical national-level snapshot in a UNESCO-aligned schema.

    Returns a single JSON object suitable for direct attachment to
    annual UNESCO / UNICEF statistical returns:

      {
        "country_code": "ZW",
        "reporting_year": <year>,
        "schools": {
          "total": <int>,
          "by_type": {"PRIMARY": <int>, "SECONDARY": <int>, "COMBINED": <int>, "OTHER": <int>}
        },
        "enrolment": {
          "total_active": <int>,
          "by_province": [{"province_code": <str>, "active": <int>}, …]
        },
        "teachers": {
          "total": <int>,
        },
        "attendance": {
          "national_rate_trailing_30d": <float|null>,
        },
        "dropouts": {
          "national_count": <int>,
          "national_rate": <float|null>,
        },
        "generated_at": <ISO8601 UTC>
      }

    The shape is deliberately stable so downstream report builders
    (DocuSign filings, the Ministry website XML feed) can target a
    fixed contract. Adding fields is OK; removing or renaming is
    not — bump the version path component when that's needed.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e

    active = StudentStatus.ACTIVE.value

    # Schools — total + by school_type
    schools = db.query(School.school_type, func.count(School.id)).group_by(
        School.school_type
    ).all()
    schools_total = sum(int(c or 0) for (_t, c) in schools)
    by_type = {"PRIMARY": 0, "SECONDARY": 0, "COMBINED": 0, "OTHER": 0}
    for t, c in schools:
        key = (t or "OTHER")
        if key not in by_type:
            key = "OTHER"
        by_type[key] += int(c or 0)

    # Enrolment — total active + by province
    total_active = (
        db.query(func.count(Student.id))
        .filter(Student.status == active)
        .scalar() or 0
    )
    prov_rows = (
        db.query(School.province_code.label("code"),
                 func.count(Student.id).label("n"))
        .select_from(Student)
        .join(School, School.id == Student.school_id)
        .filter(Student.status == active)
        .group_by(School.province_code)
        .all()
    )
    by_province = [
        {"province_code": r.code, "active": int(r.n or 0)} for r in prov_rows
    ]

    # Teachers — distinct teacher_user_id with class assignments
    teachers_total = (
        db.query(func.count(distinct(ClassTeacherAssignment.teacher_user_id)))
        .scalar() or 0
    )

    # Attendance — trailing 30d national rate
    since = date.today() - timedelta(days=30)
    att_row = (
        db.query(
            func.count(AttendanceRecord.id).label("total"),
            func.sum(case((AttendanceRecord.status == "P", 1), else_=0)).label("present"),
        )
        .filter(AttendanceRecord.date >= since)
        .one()
    )
    att_total = int(att_row.total or 0)
    att_present = int(att_row.present or 0)
    att_rate = round(att_present / att_total, 4) if att_total else None

    # Dropouts — national count + rate
    drop_count = (
        db.query(func.count(Student.id))
        .filter(Student.status.in_(DROPOUT_STATUSES))
        .scalar() or 0
    )
    drop_rate = (
        round(int(drop_count) / (int(drop_count) + int(total_active)), 4)
        if (int(drop_count) + int(total_active)) > 0 else None
    )

    out = {
        "country_code": "ZW",
        "reporting_year": year,
        "schools": {
            "total": int(schools_total),
            "by_type": by_type,
        },
        "enrolment": {
            "total_active": int(total_active),
            "by_province": by_province,
        },
        "teachers": {
            "total": int(teachers_total),
        },
        "attendance": {
            "national_rate_trailing_30d": att_rate,
        },
        "dropouts": {
            "national_count": int(drop_count),
            "national_rate": drop_rate,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _audit(db, current_user, "ministry.exports.unesco.read",
           f"year:{year}", 1)
    return _ok(out, request)
