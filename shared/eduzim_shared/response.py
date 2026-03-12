"""
EduZim Response Envelope Helpers
=================================
Standardized response wrappers for all services.

Usage:
    from eduzim_shared.response import success_response, paginated_response, error_response

    @router.get("/students")
    def list_students(request: Request):
        students = ...
        return paginated_response(data=students, page=1, page_size=50, total=200, request=request)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse


def _get_request_id(request: Optional[Request] = None) -> str:
    """Extract X-Request-Id from request or generate one."""
    if request and hasattr(request, "state") and hasattr(request.state, "request_id"):
        return request.state.request_id
    if request:
        return request.headers.get("X-Request-Id", str(uuid.uuid4()))
    return str(uuid.uuid4())


def success_response(
    data: Any,
    request: Optional[Request] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Wrap data in the standard success envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "data": data,
            "meta": {
                "request_id": _get_request_id(request),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


def created_response(
    data: Any,
    request: Optional[Request] = None,
) -> JSONResponse:
    """201 Created with standard envelope."""
    return success_response(data=data, request=request, status_code=201)


def paginated_response(
    data: list[Any],
    page: int,
    page_size: int,
    total: int,
    request: Optional[Request] = None,
) -> JSONResponse:
    """Wrap paginated list data in the standard envelope."""
    return JSONResponse(
        status_code=200,
        content={
            "data": data,
            "meta": {
                "request_id": _get_request_id(request),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": (page * page_size) < total,
            },
        },
    )


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> JSONResponse:
    """Return a standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": _get_request_id(request),
            },
        },
    )
