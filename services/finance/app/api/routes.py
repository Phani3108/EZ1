"""Fees Service API Routes — Standard {data, meta} envelope."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.fees_service import FeesService
from app.services.pdf_renderer import build_invoice_pdf, build_receipt_pdf
from app.events import publish_event

# Phase 9 follow-up — write-side audit calls for fee structures, invoices,
# payments. See ADR 018 for the wiring policy + PII-minimisation rules.
from eduzim_shared.audit import Event, record_audit_event
from app.models.audit import AuditLog

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
    record_audit_event(
        db, AuditLog,
        event_type=Event.FEE_STRUCTURE_CREATED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "fee_structure", "id": result["id"]},
        details={
            # PII-minimisation: log structural metadata, not the price values.
            "name": data.name,
            "item_count": len(items),
        },
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/structures")
def list_fee_structures(request: Request, year_id: uuid.UUID = Query(None),
                        limit: int = Query(200, ge=1, le=500),
                        offset: int = Query(0, ge=0),
                        db: Session = Depends(get_db),
                        school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_fee_structures(school_id, year_id, limit=limit, offset=offset),
            "meta": _meta(request)}


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
    record_audit_event(
        db, AuditLog,
        event_type=Event.INVOICE_CREATED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "invoice", "id": result["id"],
                "student_id": str(data.student_id)},
        # PII-minimisation: never log the amount in audit (it's on the
        # invoice row already, ACL-scoped). Log the identifier only.
        details={"due_date": data.due_date.isoformat()},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/invoices")
def list_invoices(request: Request, student_id: uuid.UUID = Query(None),
                  status: str = Query(None),
                  limit: int = Query(100, ge=1, le=500),
                  offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_invoices(school_id, student_id, status, limit=limit, offset=offset),
            "meta": _meta(request)}


@router.get("/fees/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, request: Request,
                db: Session = Depends(get_db),
                school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    result = svc.get_invoice(invoice_id, school_id)
    if not result:
        return _err("NOT_FOUND", "Invoice not found", request), 404
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: uuid.UUID, request: Request,
                    db: Session = Depends(get_db),
                    school_id: uuid.UUID = Depends(get_school_id)):
    """Render an invoice as a printable PDF.

    The endpoint resolves the invoice's fee-structure line items so the
    document mirrors what parents would see in the portal.
    """
    from app.models.fees import FeeStructure
    from fastapi.responses import JSONResponse

    svc = FeesService(db)
    invoice = svc.get_invoice(invoice_id, school_id)
    if not invoice:
        return JSONResponse(
            status_code=404,
            content=_err("NOT_FOUND", "Invoice not found", request),
        )

    fs = db.query(FeeStructure).filter(
        FeeStructure.id == uuid.UUID(invoice["fee_structure_id"]),
    ).first()
    line_items = (
        [{"label": item.label, "amount": float(item.amount)} for item in fs.items]
        if fs else None
    )

    pdf = build_invoice_pdf(invoice=invoice, line_items=line_items)
    filename = f"invoice-{invoice['id'][:8]}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Request-Id": _meta(request)["request_id"],
        },
    )


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
    # PAYMENT_RECORDED is a security-relevant event — it moves money.
    # Capture ip + user-agent here even though we skip them on routine
    # writes elsewhere.
    record_audit_event(
        db, AuditLog,
        event_type=Event.PAYMENT_RECORDED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "payment", "id": result["payment"]["id"],
                "invoice_id": str(data.invoice_id)},
        details={
            # method matters for the audit story (cash vs paynow) — log it.
            # amount is logged here BY EXCEPTION to ADR 018's usual rule
            # because payment amount IS the audit story for a money move.
            "method": data.method,
            "amount": str(data.amount),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.get("/fees/payments")
def list_payments(request: Request, invoice_id: uuid.UUID = Query(None),
                  limit: int = Query(100, ge=1, le=500),
                  offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.list_payments(school_id, invoice_id, limit=limit, offset=offset),
            "meta": _meta(request)}


@router.get("/fees/payments/{payment_id}/receipt")
def get_payment_receipt_pdf(payment_id: uuid.UUID, request: Request,
                            db: Session = Depends(get_db),
                            school_id: uuid.UUID = Depends(get_school_id)):
    """Render a printable receipt PDF for a recorded payment."""
    from app.models.fees import Payment
    from fastapi.responses import JSONResponse

    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.school_id == school_id,
    ).first()
    if not payment:
        return JSONResponse(
            status_code=404,
            content=_err("NOT_FOUND", "Payment not found", request),
        )

    svc = FeesService(db)
    invoice = svc.get_invoice(payment.invoice_id, school_id)
    if not invoice:
        return JSONResponse(
            status_code=404,
            content=_err("NOT_FOUND", "Linked invoice not found", request),
        )

    payment_dict = svc._ser_payment(payment)
    pdf = build_receipt_pdf(payment=payment_dict, invoice=invoice)
    filename = f"receipt-{payment_dict['id'][:8]}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Request-Id": _meta(request)["request_id"],
        },
    )


# ───── Defaulters ─────

@router.get("/fees/defaulters")
def get_defaulters(request: Request, as_of: date = Query(None),
                   db: Session = Depends(get_db),
                   school_id: uuid.UUID = Depends(get_school_id)):
    svc = FeesService(db)
    return {"data": svc.get_defaulters(school_id, as_of), "meta": _meta(request)}
