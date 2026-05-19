"""
EduZim Payment Gateway Routes — Paynow (Zimbabwe) Integration
===============================================================
Paynow supports EcoCash, OneMoney, Mukuru, and Telecash mobile payments.

Flow:
  1. Frontend calls POST /fees/payments/initiate
       → we create a `PaymentTransaction` row (status=INITIATED)
       → call Paynow `remotetransaction` endpoint
       → on Ok, store poll_url + instructions, set status=SENT
       → on error, set status=FAILED, return GATEWAY_ERROR
  2. User completes payment on their phone (USSD/STK push).
  3. Paynow POSTs to /fees/payments/webhook/paynow
       → verify HMAC hash
       → look up transaction by `reference`
       → idempotently call FeesService.record_payment()
       → update transaction.status (PAID / CANCELLED / FAILED)
  4. Frontend can also poll GET /fees/payments/{ref}/status
     which falls back to Paynow's `pollurl` if the webhook is late.

All responses use the standard `{data, meta}` / `{error, meta}` envelopes.
Webhook responds with the literal `Ok` body Paynow expects on success.
"""
import uuid
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.config import get_settings
from app.models.fees import PaymentTransaction
from app.models.idempotency import IdempotencyKey
from eduzim_shared.idempotency import DbIdempotencyStore

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["Payments"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(request: Request, status_code: int, code: str, message: str, **details):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": _meta(request)["request_id"],
            },
        },
    )


# ─── Schemas ───

class PaymentInitiateRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: float = Field(..., gt=0)
    method: str = Field(..., pattern="^(ECOCASH|ONEMONEY|MUKURU|TELECASH|BANK)$")
    phone: str = Field(..., min_length=10, max_length=15)  # +263...
    return_url: Optional[str] = None


# ─── Paynow Client ───

PAYNOW_INITIATE_URL = "https://www.paynow.co.zw/interface/remotetransaction"


class PaynowClient:
    """Wrapper for the Paynow Zimbabwe payment gateway."""

    def __init__(self):
        self.integration_id = settings.PAYNOW_INTEGRATION_ID
        self.integration_key = settings.PAYNOW_INTEGRATION_KEY
        self.result_url = settings.PAYNOW_RESULT_URL
        self.return_url = settings.PAYNOW_RETURN_URL

    @property
    def configured(self) -> bool:
        return bool(self.integration_id and self.integration_key)

    def generate_hash(self, values: dict) -> str:
        """
        Paynow hash spec: concatenate values (excluding `hash`), append the
        integration key, SHA512, uppercase. We sort keys for deterministic
        output on outgoing requests; for incoming webhooks Paynow's reference
        implementation does the same after stripping `hash`.
        """
        concat = ""
        for key in sorted(values.keys()):
            if key == "hash":
                continue
            concat += str(values[key])
        concat += self.integration_key
        return hashlib.sha512(concat.encode("utf-8")).hexdigest().upper()

    def verify_hash(self, values: dict) -> bool:
        received = (values.get("hash") or "").upper()
        if not received:
            return False
        expected = self.generate_hash(values)
        # Constant-time compare to avoid timing attacks
        return hmac.compare_digest(received, expected)

    def initiate_mobile_payment(
        self, reference: str, amount: float, phone: str,
        method: str, email: str = "",
    ) -> dict:
        """Initiate a mobile money payment via Paynow's Express checkout."""
        import requests as req

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
        values["hash"] = self.generate_hash(values)

        try:
            resp = req.post(PAYNOW_INITIATE_URL, data=values, timeout=15)
        except Exception as e:
            logger.exception("Paynow initiate failed")
            return {"status": "Error", "error": f"network: {e}"}

        try:
            result = dict(
                item.split("=", 1) for item in resp.text.split("&") if "=" in item
            )
        except Exception:
            return {"status": "Error", "error": f"unparseable response: {resp.text[:200]}"}
        return result

    def poll(self, poll_url: str) -> dict:
        """Poll Paynow for the latest status of a transaction."""
        import requests as req
        try:
            resp = req.post(poll_url, timeout=10)
            return dict(
                item.split("=", 1) for item in resp.text.split("&") if "=" in item
            )
        except Exception as e:
            logger.exception("Paynow poll failed")
            return {"status": "Error", "error": str(e)}


paynow_client = PaynowClient()


# ─── Status mapping ───

_PAYNOW_PAID = {"paid", "awaiting delivery", "delivered"}
_PAYNOW_CANCELLED = {"cancelled"}
_PAYNOW_FAILED = {"failed", "disputed", "refunded"}


def _classify_paynow_status(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in _PAYNOW_PAID:
        return "PAID"
    if s in _PAYNOW_CANCELLED:
        return "CANCELLED"
    if s in _PAYNOW_FAILED:
        return "FAILED"
    return "SENT"  # still in progress


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

    # Honour Idempotency-Key header so a retry of the same logical request
    # returns the original response instead of creating a duplicate
    # PaymentTransaction row.
    idem_header = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    idem_store: Optional[DbIdempotencyStore] = None
    idem_key: Optional[str] = None
    if idem_header:
        idem_key = f"fees:initiate:{school_id}:{idem_header}"
        idem_store = DbIdempotencyStore(db, IdempotencyKey)
        if idem_store.is_duplicate(idem_key):
            cached = idem_store.get_cached_response(idem_key) or {}
            return {"data": cached, "meta": {**_meta(request), "idempotent_replay": True}}

    svc = FeesService(db)

    invoice = svc.get_invoice(data.invoice_id, school_id)
    if not invoice:
        return _err(request, 404, "NOT_FOUND", "Invoice not found")
    balance = float(invoice.get("balance", 0))
    if balance <= 0:
        return _err(request, 400, "ALREADY_PAID", "Invoice already fully paid")
    if data.amount > balance:
        return _err(request, 400, "OVERPAYMENT",
                    "Amount exceeds invoice balance", balance=balance)

    # Persist BEFORE calling the gateway so we always have an audit row.
    txn_ref = f"EDU-{str(data.invoice_id)[:8].upper()}-{uuid.uuid4().hex[:6].upper()}"
    txn = PaymentTransaction(
        school_id=school_id,
        invoice_id=data.invoice_id,
        provider="PAYNOW",
        method=data.method,
        reference=txn_ref,
        amount=Decimal(str(data.amount)),
        currency=invoice.get("currency", "USD"),
        phone=data.phone,
        status="INITIATED",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    if not paynow_client.configured:
        # Demo mode — give the UI enough to render its next-step screen.
        txn.status = "SENT"
        txn.instructions = (
            f"Demo mode: payment {txn_ref} initiated for {data.method}. "
            "Configure Paynow credentials to process real transactions."
        )
        db.commit()
        payload = {
            "transaction_ref": txn_ref,
            "status": "PENDING",
            "poll_url": "",
            "instructions": txn.instructions,
            "demo_mode": True,
        }
        if idem_store and idem_key:
            idem_store.mark_processed(idem_key, payload)
        return {"data": payload, "meta": _meta(request)}

    result = paynow_client.initiate_mobile_payment(
        reference=txn_ref,
        amount=data.amount,
        phone=data.phone,
        method=data.method,
        email=current_user.get("email", "") if isinstance(current_user, dict) else "",
    )

    if (result.get("status") or "").lower() == "ok":
        txn.status = "SENT"
        txn.poll_url = result.get("pollurl", "")
        txn.instructions = result.get(
            "instructions", "Check your phone to complete payment."
        )
        db.commit()
        payload = {
            "transaction_ref": txn_ref,
            "status": "PENDING",
            "poll_url": txn.poll_url,
            "instructions": txn.instructions,
            "demo_mode": False,
        }
        if idem_store and idem_key:
            idem_store.mark_processed(idem_key, payload)
        return {"data": payload, "meta": _meta(request)}

    err_msg = result.get("error", "Payment gateway returned an error.")
    txn.status = "FAILED"
    txn.last_error = err_msg[:500]
    db.commit()
    return _err(request, 502, "PAYNOW_UNREACHABLE", err_msg, transaction_ref=txn_ref)


@router.post("/fees/payments/webhook/paynow")
async def paynow_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Paynow result webhook (server-to-server, no JWT).

    * If credentials are configured the hash MUST validate (400 otherwise so
      Paynow retries).
    * Look up the transaction by `reference`. Unknown ref → ack so Paynow
      stops retrying, but log loudly.
    * Idempotently insert a Payment via FeesService.record_payment using
      `paynow:{reference}:{paynow_reference}` as the idempotency key.
    * Persist gateway breadcrumbs on the transaction.

    Paynow expects the literal body `Ok` on success.
    """
    form = await request.form()
    values = {k: str(v) for k, v in form.items()}

    logger.info("Paynow webhook received: ref=%s status=%s",
                values.get("reference"), values.get("status"))

    if paynow_client.configured:
        if not paynow_client.verify_hash(values):
            logger.warning("Paynow webhook hash verification FAILED for ref=%s",
                           values.get("reference"))
            return PlainTextResponse("Invalid hash", status_code=400)

    reference = values.get("reference", "")
    if not reference:
        return PlainTextResponse("Missing reference", status_code=400)

    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.reference == reference,
    ).first()
    if not txn:
        logger.warning("Paynow webhook for unknown reference=%s — acking", reference)
        return PlainTextResponse("Ok")

    paynow_ref = values.get("paynowreference", "")
    new_status = _classify_paynow_status(values.get("status", ""))

    txn.paynow_reference = paynow_ref or txn.paynow_reference
    txn.status = new_status
    txn.updated_at = datetime.now(timezone.utc)

    if new_status == "PAID":
        idem = f"paynow:{reference}:{paynow_ref or 'NA'}"
        from app.services.fees_service import FeesService
        svc = FeesService(db)
        try:
            paid_amount = Decimal(str(values.get("amount", txn.amount)))
        except Exception:
            paid_amount = Decimal(str(txn.amount))

        result = svc.record_payment(
            school_id=txn.school_id,
            invoice_id=txn.invoice_id,
            amount=paid_amount,
            method=txn.method,
            reference=paynow_ref or reference,
            idempotency_key=idem,
        )
        if "error" in result:
            txn.status = "FAILED"
            txn.last_error = f"{result.get('error')}: {result.get('message', '')}"[:500]
            logger.error("Paynow PAID could not be recorded ref=%s err=%s",
                         reference, txn.last_error)
        else:
            payment = result.get("payment") or {}
            try:
                txn.payment_id = uuid.UUID(payment.get("id"))
            except Exception:
                pass
            txn.confirmed_at = datetime.now(timezone.utc)

    db.commit()
    return PlainTextResponse("Ok")


@router.get("/fees/payments/{transaction_ref}/status")
def check_payment_status(
    transaction_ref: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """
    Return current state of a payment transaction. If the gateway is
    configured and the transaction isn't terminal, also poll Paynow's
    poll_url so we don't depend on the webhook being on time.
    """
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.reference == transaction_ref,
        PaymentTransaction.school_id == school_id,
    ).first()
    if not txn:
        return _err(request, 404, "NOT_FOUND", "Transaction not found")

    terminal = txn.status in ("PAID", "CANCELLED", "FAILED", "EXPIRED")
    if not terminal and txn.poll_url and paynow_client.configured:
        polled = paynow_client.poll(txn.poll_url)
        new_status = _classify_paynow_status(polled.get("status", ""))
        if new_status != txn.status:
            txn.status = new_status
            txn.paynow_reference = polled.get("paynowreference") or txn.paynow_reference
            db.commit()

    return {
        "data": {
            "transaction_ref": txn.reference,
            "status": txn.status,
            "paynow_reference": txn.paynow_reference,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "method": txn.method,
            "instructions": txn.instructions,
            "last_error": txn.last_error,
            "initiated_at": txn.initiated_at.isoformat() if txn.initiated_at else None,
            "confirmed_at": txn.confirmed_at.isoformat() if txn.confirmed_at else None,
        },
        "meta": _meta(request),
    }
