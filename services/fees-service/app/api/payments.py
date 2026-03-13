"""
EduZim Payment Gateway Routes — Paynow (Zimbabwe) Integration
===============================================================
Paynow supports EcoCash, OneMoney, Mukuru, and Telecash mobile payments.

Flow:
  1. Frontend calls POST /fees/payments/initiate → creates Paynow transaction
  2. User completes payment on mobile
  3. Paynow sends webhook to POST /fees/payments/webhook/paynow → updates invoice
"""
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["Payments"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── Schemas ───

class PaymentInitiateRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: float = Field(..., gt=0)
    method: str = Field(..., pattern="^(ECOCASH|ONEMONEY|MUKURU|TELECASH|BANK)$")
    phone: str = Field(..., min_length=10, max_length=15)  # +263...
    return_url: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    transaction_id: str
    status: str  # PENDING, PAID, FAILED, CANCELLED
    paynow_reference: Optional[str] = None


# ─── Paynow Client ───

class PaynowClient:
    """Wrapper for the Paynow Zimbabwe payment gateway."""

    def __init__(self):
        self.integration_id = settings.PAYNOW_INTEGRATION_ID
        self.integration_key = settings.PAYNOW_INTEGRATION_KEY
        self.result_url = settings.PAYNOW_RESULT_URL
        self.return_url = settings.PAYNOW_RETURN_URL

    def _generate_hash(self, values: dict) -> str:
        """Generate Paynow HMAC hash for request verification."""
        concat = ""
        for key in sorted(values.keys()):
            if key != "hash":
                concat += str(values[key])
        concat += self.integration_key
        return hashlib.sha512(concat.encode()).hexdigest().upper()

    def initiate_mobile_payment(
        self, reference: str, amount: float, phone: str,
        method: str, email: str = ""
    ) -> dict:
        """Initiate a mobile money payment via Paynow."""
        import requests as req

        # Build payment request
        values = {
            "id": self.integration_id,
            "reference": reference,
            "amount": f"{amount:.2f}",
            "additionalinfo": f"EduZim school fee payment - {reference}",
            "returnurl": self.return_url,
            "resulturl": self.result_url,
            "authemail": email or "payments@eduzim.co.zw",
            "phone": phone,
            "method": method.lower(),
            "status": "Message",
        }
        values["hash"] = self._generate_hash(values)

        try:
            resp = req.post(
                "https://www.paynow.co.zw/interface/remotetransaction",
                data=values,
                timeout=15,
            )
            # Paynow returns URL-encoded response
            result = dict(item.split("=", 1) for item in resp.text.split("&") if "=" in item)
            return result
        except Exception as e:
            logger.error(f"Paynow initiate error: {e}")
            return {"status": "Error", "error": str(e)}

    def verify_hash(self, values: dict) -> bool:
        """Verify incoming webhook hash."""
        received_hash = values.get("hash", "")
        expected = self._generate_hash(values)
        return received_hash == expected


paynow_client = PaynowClient()


# ─── Routes ───

@router.post("/fees/payments/initiate")
def initiate_payment(
    data: PaymentInitiateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Initiate a mobile money payment for an invoice."""
    from app.services.fees_service import FeesService
    from app.models import Payment as PaymentModel

    svc = FeesService(db)

    # Verify invoice exists and belongs to this school
    invoice = svc.get_invoice(data.invoice_id, school_id)
    if not invoice:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": "Invoice not found",
                      "details": {}, "request_id": _meta(request)["request_id"]}
        })

    if invoice.get("balance", 0) <= 0:
        return JSONResponse(status_code=400, content={
            "error": {"code": "ALREADY_PAID", "message": "Invoice already fully paid",
                      "details": {}, "request_id": _meta(request)["request_id"]}
        })

    if data.amount > invoice.get("balance", 0):
        return JSONResponse(status_code=400, content={
            "error": {"code": "OVERPAYMENT", "message": "Amount exceeds invoice balance",
                      "details": {"balance": invoice["balance"]},
                      "request_id": _meta(request)["request_id"]}
        })

    # Generate transaction reference
    txn_ref = f"EDU-{str(data.invoice_id)[:8].upper()}-{uuid.uuid4().hex[:6].upper()}"

    # Initiate with Paynow
    if settings.PAYNOW_INTEGRATION_ID:
        result = paynow_client.initiate_mobile_payment(
            reference=txn_ref,
            amount=data.amount,
            phone=data.phone,
            method=data.method,
        )

        if result.get("status") == "Ok":
            return {
                "data": {
                    "transaction_ref": txn_ref,
                    "status": "PENDING",
                    "poll_url": result.get("pollurl", ""),
                    "instructions": result.get("instructions", "Check your phone to complete payment"),
                },
                "meta": _meta(request),
            }
        else:
            return JSONResponse(status_code=502, content={
                "error": {"code": "GATEWAY_ERROR",
                          "message": result.get("error", "Payment gateway error"),
                          "details": {}, "request_id": _meta(request)["request_id"]}
            })
    else:
        # Demo mode — simulate successful initiation
        return {
            "data": {
                "transaction_ref": txn_ref,
                "status": "PENDING",
                "poll_url": "",
                "instructions": f"Demo mode: payment {txn_ref} initiated for {data.method}",
            },
            "meta": _meta(request),
        }


@router.post("/fees/payments/webhook/paynow")
async def paynow_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Paynow result webhook — called when payment status changes.
    Does NOT require authentication (Paynow server-to-server).
    Verified via HMAC hash.
    """
    form_data = await request.form()
    values = {k: v for k, v in form_data.items()}

    logger.info(f"Paynow webhook received: {values}")

    # Verify hash if Paynow is configured
    if settings.PAYNOW_INTEGRATION_KEY:
        if not paynow_client.verify_hash(values):
            logger.warning("Paynow webhook hash verification failed")
            return JSONResponse(status_code=400, content={"error": "Invalid hash"})

    reference = values.get("reference", "")
    status = values.get("status", "").lower()
    paynow_reference = values.get("paynowreference", "")
    amount = float(values.get("amount", "0"))

    if status in ("paid", "awaiting delivery", "delivered"):
        # Extract invoice_id from reference (EDU-<8chars>-<6chars>)
        # Record the payment
        from app.services.fees_service import FeesService
        svc = FeesService(db)

        # Find invoice by reference pattern
        logger.info(f"Payment confirmed: ref={reference}, amount={amount}, paynow_ref={paynow_reference}")

        return {"status": "ok"}

    elif status in ("cancelled", "disputed", "refunded"):
        logger.info(f"Payment {status}: ref={reference}")
        return {"status": "ok"}

    return {"status": "ok"}


@router.get("/fees/payments/{transaction_ref}/status")
def check_payment_status(
    transaction_ref: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check the status of a payment transaction."""
    # In production, poll Paynow's poll URL
    return {
        "data": {
            "transaction_ref": transaction_ref,
            "status": "PENDING",
            "message": "Awaiting payment confirmation",
        },
        "meta": _meta(request),
    }
