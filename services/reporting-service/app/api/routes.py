"""Reporting Service API Routes — Dashboard, Attendance Trend, Financial Summary, Dropout, Rebuild."""
import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.reporting_service import ReportingService
from app.services.dropout_service import DropoutRiskEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reports"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ───── Dashboard ─────

@router.get("/reports/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db),
              school_id: uuid.UUID = Depends(get_school_id)):
    svc = ReportingService(db)
    return {"data": svc.get_dashboard(school_id), "meta": _meta(request)}


# ───── Attendance Trend ─────

@router.get("/reports/attendance/trend")
def attendance_trend(request: Request,
                     from_date: date = Query(..., alias="from"),
                     to_date: date = Query(..., alias="to"),
                     db: Session = Depends(get_db),
                     school_id: uuid.UUID = Depends(get_school_id)):
    svc = ReportingService(db)
    return {"data": svc.get_attendance_trend(school_id, from_date, to_date),
            "meta": _meta(request)}


# ───── Financial Summary ─────

@router.get("/reports/financial/summary")
def financial_summary(request: Request,
                      year_id: uuid.UUID = Query(None),
                      db: Session = Depends(get_db),
                      school_id: uuid.UUID = Depends(get_school_id)):
    svc = ReportingService(db)
    return {"data": svc.get_financial_summary(school_id, year_id),
            "meta": _meta(request)}


# ───── Rebuild (Admin Only) ─────

class RebuildRequest(BaseModel):
    events: List[dict]

@router.post("/reports/rebuild")
def rebuild(data: RebuildRequest, request: Request,
            db: Session = Depends(get_db),
            current_user: dict = Depends(get_current_user),
            school_id: uuid.UUID = Depends(get_school_id)):
    svc = ReportingService(db)
    result = svc.rebuild(data.events)
    return {"data": result, "meta": _meta(request)}


# ───── Internal: Consume Events ─────

class ConsumeRequest(BaseModel):
    events: List[dict]

@router.post("/reports/consume")
def consume_events(data: ConsumeRequest, request: Request,
                   db: Session = Depends(get_db)):
    svc = ReportingService(db)
    result = svc.consume_batch(data.events)
    return {"data": result, "meta": _meta(request)}


# ═══════════════════════════════════════════
# Dropout Intelligence — v1 Rules-Based
# ═══════════════════════════════════════════

DROPOUT_LOOKBACK_DAYS = 30


async def _fetch_students(school_id: str, token: str,
                          page: int = 1, page_size: int = 100) -> tuple[list[dict], int]:
    """Fetch active students from student-service."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.STUDENT_SERVICE_URL}/api/v1/students",
            params={"page": str(page), "page_size": str(page_size), "status": "ACTIVE"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return [], 0
        body = resp.json()
        return body.get("data", []), body.get("meta", {}).get("total", 0)


async def _fetch_student_trend(school_id: str, student_id: str,
                               from_date: str, to_date: str, token: str) -> dict:
    """Fetch attendance trend from attendance-service."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.ATTENDANCE_SERVICE_URL}/api/v1/attendance/student-trend",
            params={"student_id": student_id, "from": from_date, "to": to_date},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return {"days": []}
        return resp.json().get("data", {"days": []})


async def _fetch_invoices(school_id: str, student_id: str, token: str) -> list[dict]:
    """Fetch invoices from fees-service."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.FEES_SERVICE_URL}/api/v1/fees/invoices",
            params={"student_id": student_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("data", [])


async def _compute_student_risk(school_id: str, student_id: str,
                                token: str, today: date) -> dict:
    """Compute risk for a single student using live data."""
    from_date = (today - timedelta(days=DROPOUT_LOOKBACK_DAYS)).isoformat()
    to_date = today.isoformat()

    trend = await _fetch_student_trend(school_id, student_id, from_date, to_date, token)
    invoices = await _fetch_invoices(school_id, student_id, token)

    return DropoutRiskEngine.compute(
        attendance_days=trend.get("days", []),
        invoices=invoices,
        today=today,
    )


def _extract_token(request: Request) -> str:
    """Extract Bearer token from request headers."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


# ───── Dropout Summary ─────

@router.get("/reports/dropout/summary")
async def dropout_summary(request: Request,
                          school_id: uuid.UUID = Depends(get_school_id)):
    """
    Aggregated dropout risk summary for the school.
    Returns: total students, at-risk count, band breakdown, top signals.
    """
    token = _extract_token(request)
    today = date.today()
    sid = str(school_id)

    # Fetch all active students (paginated, up to 500 for v1)
    students, total = await _fetch_students(sid, token, page=1, page_size=500)

    band_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    signal_freq: dict[str, int] = {}
    at_risk = 0

    for student in students:
        student_id = student.get("id")
        if not student_id:
            continue
        risk = await _compute_student_risk(sid, student_id, token, today)
        band = risk["risk_band"]
        band_counts[band] = band_counts.get(band, 0) + 1
        if band != "LOW":
            at_risk += 1
        for sig in risk["signals"]:
            code = sig["code"]
            signal_freq[code] = signal_freq.get(code, 0) + 1

    # Top signals sorted by frequency
    top_signals = sorted(
        [{"code": k, "count": v} for k, v in signal_freq.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    return {
        "data": {
            "total_students": len(students),
            "at_risk_count": at_risk,
            "band_breakdown": band_counts,
            "top_signals": top_signals,
        },
        "meta": _meta(request),
    }


# ───── Dropout Students List ─────

@router.get("/reports/dropout/students")
async def dropout_students(request: Request,
                           page: int = Query(1, ge=1),
                           page_size: int = Query(20, ge=1, le=100),
                           band: Optional[str] = Query(None),
                           sort: str = Query("risk_score"),
                           order: str = Query("desc"),
                           school_id: uuid.UUID = Depends(get_school_id)):
    """
    Paginated list of students with dropout risk scores.
    Optional filter by band, sortable by risk_score.
    """
    token = _extract_token(request)
    today = date.today()
    sid = str(school_id)

    # Fetch all active students
    all_students, total = await _fetch_students(sid, token, page=1, page_size=500)

    # Compute risk for each student
    enriched = []
    for student in all_students:
        student_id = student.get("id")
        if not student_id:
            continue
        risk = await _compute_student_risk(sid, student_id, token, today)
        enriched.append({
            "student_id": student_id,
            "student_code": student.get("student_code", ""),
            "first_name": student.get("first_name", ""),
            "last_name": student.get("last_name", ""),
            "risk_score": risk["risk_score"],
            "risk_band": risk["risk_band"],
            "signal_count": len(risk["signals"]),
            "top_signal": max(risk["signals"], key=lambda s: s["points"])["label"] if risk["signals"] else None,
        })

    # Filter by band
    if band:
        band_upper = band.upper()
        enriched = [s for s in enriched if s["risk_band"] == band_upper]

    # Sort
    reverse = order.lower() == "desc"
    enriched.sort(key=lambda s: s.get(sort, 0), reverse=reverse)

    # Paginate
    total_filtered = len(enriched)
    start = (page - 1) * page_size
    page_data = enriched[start:start + page_size]

    meta = _meta(request)
    meta.update({
        "page": page,
        "page_size": page_size,
        "total": total_filtered,
        "has_next": (page * page_size) < total_filtered,
    })

    return {"data": page_data, "meta": meta}


# ───── Dropout Student Detail ─────

@router.get("/reports/dropout/student/{student_id}")
async def dropout_student_detail(student_id: uuid.UUID, request: Request,
                                 school_id: uuid.UUID = Depends(get_school_id)):
    """
    Full dropout risk breakdown for a single student.
    Returns: risk_score, risk_band, all signals with evidence.
    """
    token = _extract_token(request)
    today = date.today()
    sid = str(school_id)

    risk = await _compute_student_risk(sid, str(student_id), token, today)

    return {
        "data": {
            "student_id": str(student_id),
            "risk_score": risk["risk_score"],
            "risk_band": risk["risk_band"],
            "signals": risk["signals"],
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": DROPOUT_LOOKBACK_DAYS,
        },
        "meta": _meta(request),
    }
