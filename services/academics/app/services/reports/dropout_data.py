"""Dropout intelligence — data-fetching layer.

PH2-11 — two of the three HTTP hops the old reporting-service made are
gone. Academics owns the student and attendance tables in-process, so the
gather step calls `StudentService.list_students` and
`AttendanceService.student_trend` directly. Only invoices still come from
finance (a separate service per ADR 006) — that hop remains.

Each helper returns the shape `DropoutRiskEngine.compute` expects.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.attendance_service import AttendanceService
from app.services.student_service import StudentService


logger = logging.getLogger(__name__)


LOOKBACK_DAYS = 30


def list_active_students(
    db: Session, school_id: uuid.UUID, page_size: int = 500
) -> list[dict]:
    """In-process replacement for the old HTTP GET /api/v1/students hop.

    The pre-PH2-11 dropout flow fetched at most 500 active students. We
    preserve that ceiling here — paginated rollouts are still future work.
    """
    svc = StudentService(db)
    items, _ = svc.list_students(
        school_id=school_id, page=1, page_size=page_size, status="ACTIVE"
    )
    return items


def fetch_student_trend(
    db: Session, school_id: uuid.UUID, student_id: uuid.UUID, today: date
) -> dict:
    """In-process replacement for the old HTTP GET /api/v1/attendance/student-trend hop."""
    svc = AttendanceService(db)
    from_date = today - timedelta(days=LOOKBACK_DAYS)
    return svc.student_trend(school_id, student_id, from_date, today)


async def fetch_invoices(
    school_id: uuid.UUID, student_id: uuid.UUID, token: str
) -> list[dict]:
    """Fees still live in finance — HTTP hop remains.

    On any failure (timeout, 5xx, network error) we return an empty list
    so the dropout score degrades gracefully (no fee signals) rather than
    failing the whole request.
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.FINANCE_SERVICE_URL}/api/v1/fees/invoices",
                params={"student_id": str(student_id)},
                headers={"Authorization": f"Bearer {token}"} if token else None,
            )
            if resp.status_code != 200:
                logger.info(
                    "dropout.invoices_fetch_non_200",
                    extra={"status": resp.status_code, "student_id": str(student_id)},
                )
                return []
            return resp.json().get("data", [])
    except Exception as exc:  # noqa: BLE001 — log + degrade, do not crash report
        logger.warning(
            "dropout.invoices_fetch_failed",
            extra={"err": str(exc), "student_id": str(student_id)},
        )
        return []


async def compute_student_risk(
    db: Session,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    token: str,
    today: Optional[date] = None,
) -> dict:
    """Gather all data + run the rules engine for a single student."""
    from app.services.reports.dropout_engine import DropoutRiskEngine

    today = today or date.today()
    trend = fetch_student_trend(db, school_id, student_id, today)
    invoices = await fetch_invoices(school_id, student_id, token)
    return DropoutRiskEngine.compute(
        attendance_days=trend.get("days", []),
        invoices=invoices,
        today=today,
    )
