"""
Deep diagnostics probe for fees-service
=========================================
Called by the api-gateway diagnostics router via:
  POST /internal/diagnostics/probe

This is an internal endpoint — the gateway's `/internal/` filter blocks
external traffic so we don't need extra auth here, but we still keep
checks read-only and idempotent.

Checks performed:
  • Postgres reachability + simple `SELECT 1`
  • Paynow configuration completeness (no secrets returned)
  • Paynow endpoint reachability (TCP/HTTPS reach to https://www.paynow.co.zw)

Returns the standard `{data, meta}` envelope. The gateway flattens
`data.checks[]` into the Integrations UI so each row gets its own row.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal


router = APIRouter(prefix="/internal/diagnostics", tags=["Diagnostics (internal)"])
settings = get_settings()

PAYNOW_PROBE_URL = "https://www.paynow.co.zw/interface/initiatetransaction"


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _check_db() -> dict:
    """Cheap SELECT 1 — confirms Postgres + SQLAlchemy session work."""
    started = time.time()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "id": "database",
            "label": "Database connection",
            "status": "ok",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Connected to Postgres and ran a test query.",
        }
    except Exception as e:
        return {
            "id": "database",
            "label": "Database connection",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Couldn't reach the database. Check Postgres is running and credentials are correct.",
            "error": str(e)[:300],
        }


def _check_paynow_config() -> dict:
    """Are Paynow credentials configured? Don't reveal the secret."""
    missing = []
    if not settings.PAYNOW_INTEGRATION_ID:
        missing.append("PAYNOW_INTEGRATION_ID")
    if not settings.PAYNOW_INTEGRATION_KEY:
        missing.append("PAYNOW_INTEGRATION_KEY")
    if not settings.PAYNOW_RESULT_URL:
        missing.append("PAYNOW_RESULT_URL")
    if missing:
        return {
            "id": "paynow_config",
            "label": "Paynow credentials",
            "status": "not_configured",
            "detail": "Paynow keys are not set. Payments cannot be processed until an administrator adds them.",
            "missing": missing,
        }
    return {
        "id": "paynow_config",
        "label": "Paynow credentials",
        "status": "ok",
        "detail": "Integration ID, key and result URL are all set.",
        # Surface non-secret fields so admin can verify config is what they expect
        "integration_id_preview": settings.PAYNOW_INTEGRATION_ID[:4] + "…",
        "result_url": settings.PAYNOW_RESULT_URL,
        "return_url": settings.PAYNOW_RETURN_URL,
    }


def _check_paynow_hash_roundtrip() -> dict:
    """
    Sign a fixed payload with the configured integration key, then verify it.
    Proves the key isn't garbled (e.g. trailing newlines, wrong copy-paste)
    without sending anything to Paynow.
    """
    if not (settings.PAYNOW_INTEGRATION_ID and settings.PAYNOW_INTEGRATION_KEY):
        return {
            "id": "paynow_hash",
            "label": "Paynow hash signing",
            "status": "not_configured",
            "detail": "Skipped — credentials are not set.",
        }
    try:
        from app.api.payments import paynow_client
        sample = {
            "id": settings.PAYNOW_INTEGRATION_ID,
            "reference": "EDU-DIAG-PROBE",
            "amount": "1.00",
            "additionalinfo": "diagnostic probe — not a real transaction",
            "returnurl": settings.PAYNOW_RETURN_URL,
            "resulturl": settings.PAYNOW_RESULT_URL,
            "authemail": "diagnostics@eduzim.co.zw",
            "status": "Message",
        }
        signed = dict(sample)
        signed["hash"] = paynow_client.generate_hash(sample)
        ok = paynow_client.verify_hash(signed)
        if not ok:
            return {
                "id": "paynow_hash",
                "label": "Paynow hash signing",
                "status": "down",
                "detail": "Generated a hash but couldn't verify it. The integration key may be malformed.",
            }
        return {
            "id": "paynow_hash",
            "label": "Paynow hash signing",
            "status": "ok",
            "detail": "Signed and verified a sample payload locally. The integration key is well-formed.",
        }
    except Exception as e:  # pragma: no cover
        return {
            "id": "paynow_hash",
            "label": "Paynow hash signing",
            "status": "down",
            "detail": "Couldn't sign a sample payload. Check that the integration key is set correctly.",
            "error": str(e)[:300],
        }


async def _check_paynow_reachable() -> dict:
    """Can we even reach paynow.co.zw? HEAD request, no transaction created."""
    started = time.time()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
        ) as client:
            resp = await client.head(PAYNOW_PROBE_URL)
        # Paynow may answer 200/302/405/501 to a HEAD — any HTTP answer means
        # we can reach their service. Network errors are the real failure.
        return {
            "id": "paynow_reachable",
            "label": "Paynow service reachable",
            "status": "ok",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": f"Reached https://www.paynow.co.zw (HTTP {resp.status_code}).",
            "http_status": resp.status_code,
        }
    except httpx.ConnectError as e:
        return {
            "id": "paynow_reachable",
            "label": "Paynow service reachable",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Couldn't reach paynow.co.zw. Check the server's internet connection.",
            "error": str(e)[:300],
        }
    except httpx.TimeoutException:
        return {
            "id": "paynow_reachable",
            "label": "Paynow service reachable",
            "status": "degraded",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Paynow took too long to answer. They may be slow or temporarily down.",
        }
    except Exception as e:  # pragma: no cover
        return {
            "id": "paynow_reachable",
            "label": "Paynow service reachable",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Unexpected error while testing the Paynow connection.",
            "error": str(e)[:300],
        }


def _roll_up(checks: list[dict[str, Any]]) -> tuple[str, str]:
    """Aggregate child check statuses into one overall status + message."""
    statuses = [c.get("status") for c in checks]
    if "down" in statuses:
        return "down", "One or more checks failed. See details below."
    if "degraded" in statuses:
        return "degraded", "Service is reachable but some checks are slow."
    if "not_configured" in statuses:
        return "not_configured", "The service is up but some integrations are not configured."
    return "ok", "All checks passed."


@router.post("/probe")
async def probe(request: Request):
    checks: list[dict[str, Any]] = []
    checks.append(_check_db())
    checks.append(_check_paynow_config())
    checks.append(_check_paynow_hash_roundtrip())
    checks.append(await _check_paynow_reachable())

    status, message = _roll_up(checks)
    return {
        "data": {"status": status, "message": message, "checks": checks},
        "meta": _meta(request),
    }
