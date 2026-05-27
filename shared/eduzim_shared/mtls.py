"""Service-to-service mTLS helpers (INFRA-019 / Phase 5).

Reads cert paths from env at import time. Two consumers:

  1. The server side. `uvicorn_kwargs()` returns a dict suitable for
     `uvicorn.run(..., **mtls.uvicorn_kwargs())` — ssl_certfile,
     ssl_keyfile, ssl_ca_certs, ssl_cert_reqs. The app_factory's
     lifespan picks these up automatically.

  2. The client side. `httpx_kwargs()` returns a dict suitable for
     `httpx.AsyncClient(**mtls.httpx_kwargs())` — verify, cert. Any
     service-to-service HTTP call (academics → finance for dropout
     invoices, etc.) should funnel through this.

Both sides require the same env vars on each container:

    EDUZIM_TLS_ENABLED          true|false (default: false)
    EDUZIM_TLS_CA_CERT          path to the shared CA cert
    EDUZIM_TLS_SERVER_CERT      path to this service's leaf cert
    EDUZIM_TLS_SERVER_KEY       path to this service's leaf key

When EDUZIM_TLS_ENABLED=false, both functions return empty dicts so
calling code just gets normal (non-TLS) behaviour.

Production note: this module assumes a STATIC cert mount. Rotation is
a manual restart cycle (rerun `scripts/generate-mtls-certs.sh` then
`docker compose restart <service>`). For automated rotation, swap this
for cert-manager in k8s or for SPIFFE/SPIRE.
"""
from __future__ import annotations

import os
import ssl
from typing import Optional


def _enabled() -> bool:
    return os.environ.get("EDUZIM_TLS_ENABLED", "false").lower() == "true"


def _cert_path(env_key: str) -> Optional[str]:
    p = os.environ.get(env_key)
    if not p:
        return None
    if not os.path.exists(p):
        # Fail-loud so a misconfigured deploy doesn't silently fall back
        # to plain-text.
        raise RuntimeError(
            f"mTLS path {env_key}={p!r} does not exist. "
            f"Either set EDUZIM_TLS_ENABLED=false or mount the cert."
        )
    return p


def is_enabled() -> bool:
    """Public introspection — returns True iff TLS is wired."""
    return _enabled()


def uvicorn_kwargs() -> dict:
    """Server-side kwargs for `uvicorn.run`. Empty when disabled.

    With these set, uvicorn binds with TLS and requires a client cert
    chained to the configured CA (ssl_cert_reqs=CERT_REQUIRED → mutual
    TLS, not just one-way).
    """
    if not _enabled():
        return {}
    ca = _cert_path("EDUZIM_TLS_CA_CERT")
    cert = _cert_path("EDUZIM_TLS_SERVER_CERT")
    key = _cert_path("EDUZIM_TLS_SERVER_KEY")
    if not (ca and cert and key):
        raise RuntimeError(
            "EDUZIM_TLS_ENABLED=true but cert paths missing "
            "(EDUZIM_TLS_CA_CERT / EDUZIM_TLS_SERVER_CERT / EDUZIM_TLS_SERVER_KEY)"
        )
    return {
        "ssl_certfile": cert,
        "ssl_keyfile": key,
        "ssl_ca_certs": ca,
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }


def httpx_kwargs() -> dict:
    """Client-side kwargs for `httpx.AsyncClient` / `httpx.Client`.

    Returns:
      * `verify=<ca>` — verify the server's cert against our CA.
      * `cert=(client_cert, client_key)` — present our own cert (mTLS).
    """
    if not _enabled():
        return {}
    ca = _cert_path("EDUZIM_TLS_CA_CERT")
    cert = _cert_path("EDUZIM_TLS_SERVER_CERT")
    key = _cert_path("EDUZIM_TLS_SERVER_KEY")
    if not (ca and cert and key):
        raise RuntimeError(
            "EDUZIM_TLS_ENABLED=true but cert paths missing"
        )
    return {
        "verify": ca,
        "cert": (cert, key),
    }


def http_scheme() -> str:
    """Returns 'https' or 'http' depending on whether mTLS is enabled.

    Used by callers building URLs: `f"{http_scheme()}://{host}:{port}"`.
    """
    return "https" if _enabled() else "http"
