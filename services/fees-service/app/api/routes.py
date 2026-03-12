"""Fees Service API Routes — Standard {data, meta} envelope."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.fees_service import FeesService
from app.events import publish_event

router = APIRouter(tags=["Fees"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request):
    return {"error": {"code": code, "message": msg, "details": {}, "request_id": _meta(request)["request_id"]}}


# ───── Schemas ─────

class FeeItemSchema(BaseModel):
    label: str = Field(..., max_length=255)
    amount: float
    currency: str = Field("USD", max_length=3)

class FeeStructureCreate(BaseModel):
    academic_year_id: uuid.UUID
    term_id: Optional[uuid.UUID] = None
    name: str = Field(..., max_length=255)
    items: List[FeeItemSchema]

class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    fee_structure_id: uuid.UUID
    due_date: date
    idempotency_key: Optional[str] = None

class PaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: float
    method: str = Field("CASH", max_length=50)
    reference: Optional[str] = None
    idempotency_key: Optional[str] = None


# ───── Fee Structures ─────

@router.post("/fees/structures")
def create_fee_structure(data: FeeStructureCreate, request: Request,
                         db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    items = [i.model_dump() for i in data.items]
    result = svc.create_fee_structure(school_id, data.academic_year_id,
                                       data.name, items, data.term_id)
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/structures")
def list_fee_structures(request: Request, year_id: uuid.UUID = Query(None),
                        db: Session = Depends(get_db),
                        school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_fee_structures(school_id, year_id), "meta": _meta(request)}


# ───── Invoices ─────

@router.post("/fees/invoices")
def create_invoice(data: InvoiceCreate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    result = svc.create_invoice(school_id, data.student_id,
                                 data.fee_structure_id, data.due_date,
                                 data.idempotency_key)
    if "error" in result:
        code = 409 if result["error"] == "DUPLICATE_INVOICE" else 422
        return _err(result["error"], result["message"], request), code
    publish_event("eduzim.fees.invoice.created.v1", result["id"], result,
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/invoices")
def list_invoices(request: Request, student_id: uuid.UUID = Query(None),
                  status: str = Query(None),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_invoices(school_id, student_id, status), "meta": _meta(request)}


@router.get("/fees/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, request: Request,
                db: Session = Depends(get_db),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    result = svc.get_invoice(invoice_id, school_id)
    if not result:
        return _err("NOT_FOUND", "Invoice not found", request), 404
    return {"data": result, "meta": _meta(request)}


# ───── Payments ─────

@router.post("/fees/payments")
def record_payment(data: PaymentCreate, request: Request,
                   db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    result = svc.record_payment(school_id, data.invoice_id,
                                 Decimal(str(data.amount)), data.method,
                                 data.reference, data.idempotency_key)
    if "error" in result:
        code = 409 if result["error"] in ("OVERPAYMENT", "ALREADY_PAID") else 422
        return _err(result["error"], result["message"], request), code
    publish_event("eduzim.fees.payment.recorded.v1",
                  result["payment"]["id"], result["payment"],
                  str(school_id), current_user["sub"])
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/payments")
def list_payments(request: Request, invoice_id: uuid.UUID = Query(None),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_payments(school_id, invoice_id), "meta": _meta(request)}


# ───── Defaulters ─────

@router.get("/fees/defaulters")
def get_defaulters(request: Request, as_of: date = Query(None),
                   db: Session = Depends(get_db),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.get_defaulters(school_id, as_of), "meta": _meta(request)}
