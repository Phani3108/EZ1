"""Phase 15a — Bulk fee-structure import.

CSV columns (one row per line item):
  * structure_name   — required. Multiple rows share a name → grouped
                       into one FeeStructure with N FeeItem rows.
  * academic_year_id — required (UUID).
  * term_id          — optional (UUID).
  * label            — required (e.g., "Tuition", "Books").
  * amount           — required (decimal).
  * currency         — optional, default USD.

Idempotency: the import is keyed on `(school_id, academic_year_id,
structure_name)`. Re-running with the same structure_name updates the
item list (deletes all items + re-inserts) rather than creating a
duplicate structure.

Dry-run mode validates rows + returns the would-be structures without
writing.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.fees import FeeStructure, FeeItem


router = APIRouter(tags=["Bulk Operations"])


REQUIRED = {"structure_name", "academic_year_id", "label", "amount"}
OPTIONAL = {"term_id", "currency"}
MAX_ROWS = 1000


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code: str, msg: str, request: Request, status: int = 400, details: dict | None = None):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": details or {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _validate(row: dict, row_num: int) -> list[dict]:
    errors = []
    for col in REQUIRED:
        if not (row.get(col, "") or "").strip():
            errors.append({"row": row_num, "field": col,
                           "error": f"{col} is required"})
    amt = (row.get("amount", "") or "").strip()
    if amt:
        try:
            v = Decimal(amt)
            if v < 0:
                errors.append({"row": row_num, "field": "amount",
                               "error": "must be non-negative"})
        except (InvalidOperation, ValueError):
            errors.append({"row": row_num, "field": "amount",
                           "error": "invalid decimal"})
    for col in ("academic_year_id", "term_id"):
        v = (row.get(col, "") or "").strip()
        if v:
            try:
                uuid.UUID(v)
            except (TypeError, ValueError):
                errors.append({"row": row_num, "field": col,
                               "error": "invalid UUID"})
    return errors


@router.post("/bulk/fee-structures")
async def import_fee_structures_csv(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only; do not write"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return _err("INVALID_FILE", "File must be a .csv", request)

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _err("ENCODING_ERROR", "File must be UTF-8 encoded", request)

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED - headers
    if missing:
        return _err(
            "MISSING_COLUMNS",
            f"Missing required columns: {', '.join(sorted(missing))}",
            request,
            details={"missing": sorted(missing), "found": sorted(headers)},
        )

    results = {
        "total_rows": 0,
        "structures_created": 0,
        "structures_updated": 0,
        "items_written": 0,
        "skipped": 0,
        "errors": [],
    }

    # Group rows by (structure_name, academic_year_id, term_id).
    groups: dict[tuple, list[dict]] = {}
    for row_num, row in enumerate(reader, start=2):
        if row_num > MAX_ROWS + 1:
            results["errors"].append(
                {"row": row_num, "error": f"Maximum {MAX_ROWS} rows exceeded"}
            )
            break
        results["total_rows"] += 1
        errs = _validate(row, row_num)
        if errs:
            results["errors"].extend(errs)
            results["skipped"] += 1
            continue
        key = (
            row["structure_name"].strip(),
            row["academic_year_id"].strip(),
            (row.get("term_id") or "").strip() or None,
        )
        groups.setdefault(key, []).append({
            "label": row["label"].strip(),
            "amount": Decimal(row["amount"].strip()),
            "currency": (row.get("currency") or "USD").strip() or "USD",
            "row_num": row_num,
        })

    if dry_run:
        results["structures_created"] = len(groups)
        results["items_written"] = sum(len(v) for v in groups.values())
        meta = _meta(request)
        meta["dry_run"] = True
        return {"data": results, "meta": meta}

    # Persist.
    for (name, ay_id, term_id), items in groups.items():
        try:
            existing = (
                db.query(FeeStructure)
                .filter(
                    FeeStructure.school_id == school_id,
                    FeeStructure.academic_year_id == uuid.UUID(ay_id),
                    FeeStructure.name == name,
                )
                .first()
            )
            if existing:
                # Replace the item list.
                db.query(FeeItem).filter(
                    FeeItem.fee_structure_id == existing.id
                ).delete()
                fs = existing
                results["structures_updated"] += 1
            else:
                fs = FeeStructure(
                    id=uuid.uuid4(),
                    school_id=school_id,
                    academic_year_id=uuid.UUID(ay_id),
                    term_id=uuid.UUID(term_id) if term_id else None,
                    name=name,
                    is_active=True,
                )
                db.add(fs)
                db.flush()
                results["structures_created"] += 1
            for item in items:
                fi = FeeItem(
                    id=uuid.uuid4(),
                    fee_structure_id=fs.id,
                    label=item["label"],
                    amount=item["amount"],
                    currency=item["currency"],
                )
                db.add(fi)
                results["items_written"] += 1
        except Exception as e:
            results["errors"].append({
                "structure_name": name, "error": str(e)[:200],
            })
            results["skipped"] += len(items)

    db.commit()
    meta = _meta(request)
    meta["dry_run"] = False
    return {"data": results, "meta": meta}
