"""
Diagnostics endpoints (admin-only)
====================================
Surface the health and configuration of every downstream service in one
place so admin-web can render a friendly "Integrations" hub.

Endpoints (all require `report:admin` permission via RBAC map):
  GET  /api/v1/diagnostics/services     → list every service with health
  POST /api/v1/diagnostics/probe/{name} → run a deeper probe (provider-specific)

Probes call the downstream service's `/internal/diagnostics/probe` endpoint
(blocked from external traffic by the existing `/internal/` filter in main.py).
For services where we don't have a custom probe yet, fall back to /health.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_settings
from app.routes import SERVICE_ROUTES
from app.middleware.stack import validate_jwt


def require_admin(request: Request) -> dict:
    """
    Diagnostics router lives outside the catch-all proxy and therefore does
    not get the gateway's RBAC for free. Enforce admin permission here so
    these endpoints can never be reached by a teacher or parent token.
    """
    auth_header = request.headers.get("authorization", "")
    payload = validate_jwt(auth_header)
    perms = set(payload.get("permissions", []))
    roles = {(r or "").lower() for r in payload.get("roles", [])}
    if "*" in perms or "report:admin" in perms:
        return payload
    if {"admin", "schooladmin", "school_admin", "ministry"} & roles:
        return payload
    raise HTTPException(status_code=403, detail="Diagnostics is admin-only")


router = APIRouter(
    prefix="/diagnostics",
    tags=["Diagnostics"],
    dependencies=[Depends(require_admin)],
)
settings = get_settings()


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# Curated list — what we expose in the Integrations UI.
# label/category are surfaced to the frontend so we don't hardcode copy there.
INTEGRATIONS = [
    {
        # PH2-2: id and url_key updated to the renamed `identity` service.
        "id": "identity",
        "label": "Authentication",
        "category": "platform",
        "url_key": "IDENTITY_SERVICE_URL",
        "description": "User sign-in, sessions and permissions.",
    },
    {
        # PH2-10: four service cards (school / student / attendance / assessment)
        # consolidated into one `academics` card now that all academic domains
        # are served by the same service.
        "id": "academics",
        "label": "Academics (school · students · attendance · assessments)",
        "category": "platform",
        "url_key": "ACADEMICS_SERVICE_URL",
        "description": (
            "Schools, terms, classes, subjects, students, parents, enrolments, "
            "attendance, assessments + marks, plus Zimbabwe geo reference."
        ),
    },
    {
        # PH2-3: id and url_key updated to the renamed `finance` service.
        "id": "finance",
        "label": "Fees & Paynow",
        "category": "money",
        "url_key": "FINANCE_SERVICE_URL",
        "description": "Invoices, payments and Paynow integration.",
    },
    {
        # PH2-4: id and url_key updated to the renamed `communications` service.
        "id": "communications",
        "label": "Messaging (SMS, WhatsApp, Email)",
        "category": "messaging",
        "url_key": "COMMUNICATIONS_SERVICE_URL",
        "description": "Announcements and message delivery.",
    },
    # PH2-11: the reporting-service HTTP card is gone. /api/v1/reports/*
    # is now served by academics; the reporting-service container is a
    # pure Kafka consumer (no /health endpoint). Its liveness shows up
    # implicitly in the academics card's read latency — when the consumer
    # falls behind, the dashboard tile freezes, which is the signal
    # operators actually want.
]


async def _probe_health(url: str, timeout: float = 3.0) -> dict:
    """Hit /health on a downstream service. Returns a normalised dict."""
    started = time.time()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=2.0),
        ) as client:
            resp = await client.get(f"{url}/health")
        latency_ms = round((time.time() - started) * 1000, 1)
        if resp.status_code == 200:
            return {"status": "ok", "latency_ms": latency_ms, "http_status": 200}
        return {
            "status": "degraded",
            "latency_ms": latency_ms,
            "http_status": resp.status_code,
            "message": f"Unexpected status {resp.status_code} from /health",
        }
    except httpx.ConnectError as e:
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "message": f"Cannot reach service: {e}",
        }
    except httpx.TimeoutException:
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "message": "Service did not respond in time.",
        }
    except Exception as e:  # pragma: no cover — defensive
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "message": f"Unexpected error: {e}",
        }


async def _probe_deep(url: str, integration_id: str, timeout: float = 8.0) -> dict:
    """Call the service's deep-probe endpoint if it exists, else health."""
    started = time.time()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=3.0),
        ) as client:
            resp = await client.post(
                f"{url}/internal/diagnostics/probe",
                json={"integration_id": integration_id},
            )
        latency_ms = round((time.time() - started) * 1000, 1)
        if resp.status_code == 404:
            # Service hasn't implemented deep probe yet — fall back to health.
            base = await _probe_health(url, timeout=3.0)
            base["deep_probe"] = False
            return base
        if resp.status_code == 200:
            body = resp.json() if resp.content else {}
            data = body.get("data", body)
            return {
                "status": data.get("status", "ok"),
                "latency_ms": latency_ms,
                "http_status": 200,
                "deep_probe": True,
                "checks": data.get("checks", []),
                "message": data.get("message"),
            }
        return {
            "status": "degraded",
            "latency_ms": latency_ms,
            "http_status": resp.status_code,
            "deep_probe": True,
            "message": (resp.text or "")[:300],
        }
    except httpx.ConnectError as e:
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "deep_probe": False,
            "message": f"Cannot reach service: {e}",
        }
    except httpx.TimeoutException:
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "deep_probe": False,
            "message": "Probe did not finish in time.",
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "deep_probe": False,
            "message": f"Unexpected error: {e}",
        }


@router.get("/services")
async def list_services(request: Request):
    """List every integration with a quick health probe."""
    results: list[dict[str, Any]] = []
    for spec in INTEGRATIONS:
        url = getattr(settings, spec["url_key"], None)
        if not url:
            results.append(
                {
                    **spec,
                    "status": "not_configured",
                    "message": f"Environment variable {spec['url_key']} is not set.",
                }
            )
            continue
        probe = await _probe_health(url)
        results.append({**spec, **probe})

    return {"data": {"integrations": results}, "meta": _meta(request)}


@router.post("/probe/{integration_id}")
async def probe_integration(integration_id: str, request: Request):
    """Run a deep probe for a single integration."""
    spec = next((s for s in INTEGRATIONS if s["id"] == integration_id), None)
    if not spec:
        raise HTTPException(
            status_code=404, detail=f"Unknown integration '{integration_id}'"
        )
    url = getattr(settings, spec["url_key"], None)
    if not url:
        return {
            "data": {
                "id": integration_id,
                "status": "not_configured",
                "message": f"Environment variable {spec['url_key']} is not set.",
            },
            "meta": _meta(request),
        }

    probe = await _probe_deep(url, integration_id=integration_id)
    return {
        "data": {"id": integration_id, "label": spec["label"], **probe},
        "meta": _meta(request),
    }
