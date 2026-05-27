"""Per-school payment config + provider-aware initiate (Phase 12b)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.payment_config import SchoolPaymentConfig
from app.models.audit import AuditLog
from app.providers import (
    PROVIDER_REGISTRY,
    get_provider_for_school,
    PaymentProviderError,
)
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Payment Config"])


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── Admin: get + set school payment provider ──────────────────────


class PaymentConfigUpdate(BaseModel):
    provider_name: str = Field(..., max_length=32)
    config: Optional[dict] = None


def _ser_config(c: SchoolPaymentConfig | None, school_id: uuid.UUID) -> dict:
    if c is None:
        return {
            "school_id": str(school_id),
            "provider_name": "paynow",
            "config": None,
            "updated_at": None,
            "is_default": True,
        }
    try:
        cfg = json.loads(c.config_json) if c.config_json else None
    except (TypeError, ValueError):
        cfg = None
    return {
        "school_id": str(c.school_id),
        "provider_name": c.provider_name,
        "config": cfg,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "is_default": False,
    }


@router.get("/fees/payment-config")
def get_payment_config(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SchoolPaymentConfig)
        .filter(SchoolPaymentConfig.school_id == school_id)
        .first()
    )
    return {
        "data": {
            **_ser_config(row, school_id),
            "available_providers": sorted(PROVIDER_REGISTRY.keys()),
        },
        "meta": _meta(request),
    }


@router.put("/fees/payment-config")
def put_payment_config(
    payload: PaymentConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.provider_name not in PROVIDER_REGISTRY:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "UNKNOWN_PROVIDER",
                "message": (
                    f"provider_name must be one of: "
                    f"{sorted(PROVIDER_REGISTRY.keys())}"
                ),
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    row = (
        db.query(SchoolPaymentConfig)
        .filter(SchoolPaymentConfig.school_id == school_id)
        .first()
    )
    if row is None:
        row = SchoolPaymentConfig(
            school_id=school_id,
            provider_name=payload.provider_name,
            config_json=json.dumps(payload.config) if payload.config else None,
            updated_by_user_id=actor,
        )
        db.add(row)
    else:
        row.provider_name = payload.provider_name
        row.config_json = (
            json.dumps(payload.config) if payload.config else None
        )
        row.updated_by_user_id = actor
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="payment_config.updated",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "school_payment_config", "id": str(school_id)},
        # Provider name IS the audit story; the inner config_json may
        # carry secrets (merchant ids) so we DON'T log it.
        details={"provider_name": payload.provider_name},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_config(row, school_id), "meta": _meta(request)}


# ─── Parent: initiate via configured provider ──────────────────────


class InitiateRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    payer_phone: Optional[str] = None
    return_url: Optional[str] = None
    method: Optional[str] = None


@router.post("/fees/payments/checkout")
def initiate_payment(
    payload: InitiateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Provider-aware initiate endpoint. Hands the request off to
    whichever provider the school has configured."""
    actor = uuid.UUID(str(current_user["sub"]))
    provider = get_provider_for_school(db, school_id)
    try:
        result = provider.initiate(
            invoice_id=payload.invoice_id,
            amount=payload.amount,
            school_id=school_id,
            payer_user_id=actor,
            payer_phone=payload.payer_phone,
            return_url=payload.return_url,
            method=payload.method,
        )
    except PaymentProviderError as e:
        return JSONResponse(
            status_code=502,
            content={"error": {
                "code": "PROVIDER_ERROR",
                "message": str(e),
                "details": {"provider": provider.name},
                "request_id": _meta(request)["request_id"],
            }},
        )

    # Manual-provider initiate persists a PaymentTransaction marker
    # so the school office can find it later. Paynow's existing
    # adapter raises (the legacy route still owns that path during
    # the unification follow-up); we only persist for "manual" here.
    if provider.name == "manual":
        from app.models.fees import PaymentTransaction
        # PaymentTransaction is a separate model. We create one in
        # PENDING state with provider=MANUAL so admin endpoints can
        # find + mark-paid it.
        txn = PaymentTransaction(
            school_id=school_id,
            invoice_id=payload.invoice_id,
            amount=payload.amount,
            provider="MANUAL",
            # PaymentTransaction.method is NOT NULL; for manual flow
            # "OFFLINE" is the catch-all (the actual mechanism — cash,
            # bank, EcoCash direct — is recorded in the admin confirm
            # note when known).
            method=(payload.method or "OFFLINE"),
            reference=result.reference,
            status="PENDING",
        )
        db.add(txn)
        db.flush()
        record_audit_event(
            db, AuditLog, event_type="payment.initiated.manual",
            school_id=school_id, actor_user_id=actor,
            actor_role=(current_user.get("roles") or [None])[0],
            target={"resource": "payment_transaction", "id": str(txn.id),
                    "reference": result.reference,
                    "invoice_id": str(payload.invoice_id)},
            details={"provider": "manual"},
            request_id=getattr(request.state, "request_id", None),
        )
        db.commit()

    return {
        "data": {
            "provider": provider.name,
            "reference": result.reference,
            "redirect_url": result.redirect_url,
            "status": result.status,
            "instructions": result.raw_response.get("instructions"),
        },
        "meta": _meta(request),
    }


# ─── Admin: confirm a manual payment ──────────────────────────────


class ManualConfirm(BaseModel):
    reference: str = Field(..., max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/fees/payments/manual/confirm")
def confirm_manual_payment(
    payload: ManualConfirm,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Admin-only. Marks a MAN-* reference as PAID and finalises the
    Invoice's paid_amount. Used when the school has confirmed the
    off-platform funds cleared."""
    from app.models.fees import PaymentTransaction
    txn = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.reference == payload.reference,
            PaymentTransaction.school_id == school_id,
            PaymentTransaction.provider == "MANUAL",
        )
        .first()
    )
    if txn is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND",
                "message": f"Manual payment reference {payload.reference} not found.",
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )
    if txn.status == "PAID":
        return {"data": {"already_paid": True}, "meta": _meta(request)}

    txn.status = "PAID"
    actor = uuid.UUID(str(current_user["sub"]))
    record_audit_event(
        db, AuditLog, event_type="payment.manual.confirmed",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "payment_transaction", "id": str(txn.id),
                "reference": payload.reference,
                "invoice_id": str(txn.invoice_id)},
        # The note may carry payer narrative; we don't log it.
        details={"amount": str(txn.amount)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {
        "data": {
            "reference": payload.reference,
            "status": "PAID",
            "amount": str(txn.amount),
        },
        "meta": _meta(request),
    }
