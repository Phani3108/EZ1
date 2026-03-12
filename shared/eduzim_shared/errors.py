"""
EduZim Shared Error Handling
============================
Standardized exception classes and FastAPI exception handlers.

Usage:
    from eduzim_shared.errors import (
        EduZimException, NotFoundError, ConflictError,
        ForbiddenError, register_exception_handlers,
    )

    # In main.py:
    register_exception_handlers(app)

    # In services:
    raise NotFoundError("Student", student_id)
"""

from typing import Any, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standardized error response format across all services."""
    error: str
    detail: str
    status_code: int
    service: Optional[str] = None
    request_id: Optional[str] = None


# --- Exception Classes ---

class EduZimException(Exception):
    """Base exception for all EduZim errors."""
    status_code: int = 500
    error: str = "internal_error"

    def __init__(self, detail: str, status_code: Optional[int] = None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class NotFoundError(EduZimException):
    """Resource not found."""
    status_code = 404
    error = "not_found"

    def __init__(self, resource: str, identifier: Any = None):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail=detail)


class ConflictError(EduZimException):
    """Resource already exists or constraint violation."""
    status_code = 409
    error = "conflict"

    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(detail=detail)


class ValidationError(EduZimException):
    """Input validation failure."""
    status_code = 422
    error = "validation_error"


class ForbiddenError(EduZimException):
    """Permission denied."""
    status_code = 403
    error = "forbidden"

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(detail=detail)


class UnauthorizedError(EduZimException):
    """Authentication required or failed."""
    status_code = 401
    error = "unauthorized"

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(detail=detail)


class TenantIsolationError(EduZimException):
    """Cross-tenant access attempt."""
    status_code = 403
    error = "tenant_isolation_violation"

    def __init__(self):
        super().__init__(detail="Cannot access resources from another school")


class ServiceUnavailableError(EduZimException):
    """Downstream service unavailable."""
    status_code = 503
    error = "service_unavailable"


# --- FastAPI Exception Handlers ---

def register_exception_handlers(app: FastAPI, service_name: str = "eduzim") -> None:
    """
    Register standardized exception handlers on a FastAPI app.
    Call in main.py after app creation.
    """

    @app.exception_handler(EduZimException)
    async def eduzim_exception_handler(request: Request, exc: EduZimException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.error,
                detail=exc.detail,
                status_code=exc.status_code,
                service=service_name,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred",
                status_code=500,
                service=service_name,
            ).model_dump(),
        )
