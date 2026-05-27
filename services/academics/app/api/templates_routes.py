"""Phase 15b — CSV/Excel template downloads.

So admins don't have to guess column names for bulk imports. Each
template returns a file with the right header row + 2 example rows.

  * `GET /templates/students.csv`
  * `GET /templates/teachers.csv`
  * `GET /templates/parents.csv`
  * `GET /templates/fee-structures.csv`

(.xlsx variants are wired the same way using openpyxl. We skip them
in v1 — SheetJS on the admin-web client can convert CSV→Excel for
the school's user.)

Public-ish: requires authentication (any role in the school) but is
otherwise tenant-agnostic — these are just example files.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user


router = APIRouter(tags=["Templates"])


TEMPLATES = {
    "students": {
        "headers": [
            "first_name", "last_name", "student_code",
            "dob", "gender", "admission_date",
            "parent_first_name", "parent_last_name",
            "parent_phone", "parent_email", "class_name",
        ],
        "examples": [
            ["Tendai", "Mukoma", "S-001",
             "2012-04-15", "M", "2026-01-15",
             "Mai", "Mukoma", "+263770111111",
             "mai.mukoma@example.com", "Form 1A"],
            ["Chipo", "Sibanda", "S-002",
             "2011-08-22", "F", "2026-01-15",
             "Baba", "Sibanda", "+263770222222",
             "", "Form 2B"],
        ],
    },
    "teachers": {
        "headers": ["first_name", "last_name", "email", "phone", "class_codes"],
        "examples": [
            ["Mrs", "Ndlovu", "ndlovu@example.com",
             "+263770333333", "F1A,F1B"],
            ["Mr", "Moyo", "moyo@example.com",
             "+263770444444", "F2A"],
        ],
    },
    "parents": {
        "headers": [
            "first_name", "last_name", "phone", "email",
            "relationship_type", "student_code",
        ],
        "examples": [
            ["Mai", "Mukoma", "+263770111111",
             "mai.mukoma@example.com", "MOTHER", "S-001"],
            ["Baba", "Sibanda", "+263770222222",
             "", "FATHER", "S-002"],
        ],
    },
    "fee-structures": {
        "headers": [
            "structure_name", "academic_year_id", "term_id",
            "label", "amount", "currency",
        ],
        "examples": [
            ["Term 1 Tuition", "<uuid>", "<uuid>",
             "Tuition", "1500.00", "USD"],
            ["Term 1 Tuition", "<uuid>", "<uuid>",
             "Books", "200.00", "USD"],
        ],
    },
}


def _csv_response(name: str, headers: list[str], rows: list[list[str]]):
    """Stream a CSV file with the right headers + examples."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{name}-template.csv"',
        },
    )


@router.get("/templates/{entity}.csv")
def template_csv(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return a CSV template for the named entity."""
    tpl = TEMPLATES.get(entity)
    if not tpl:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "UNKNOWN_TEMPLATE",
                "message": f"No template for '{entity}'. "
                           f"Available: {sorted(TEMPLATES)}",
                "details": {},
                "request_id": str(uuid.uuid4()),
            }},
        )
    return _csv_response(entity, tpl["headers"], tpl["examples"])


@router.get("/templates")
def list_templates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Catalog of available templates with their column lists. Used
    by admin-web setup wizard to render the upload pages."""
    return {
        "data": [
            {
                "entity": k,
                "headers": v["headers"],
                "example_count": len(v["examples"]),
                "csv_url": f"/api/v1/templates/{k}.csv",
            }
            for k, v in TEMPLATES.items()
        ],
        "meta": {
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
