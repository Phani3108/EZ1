"""
EduZim Request-ID Middleware
============================
Ensures every request has an X-Request-Id header.
If the client doesn't send one, the gateway/service generates it.

Usage:
    from eduzim_shared.middleware import RequestIdMiddleware
    app.add_middleware(RequestIdMiddleware)
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures X-Request-Id is present on every request.
    - Reads from incoming header or generates a new UUID.
    - Stores on request.state.request_id for use in handlers/logging.
    - Adds it to the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
