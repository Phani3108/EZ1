import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id, require_permission
from app.schemas.auth import (
    UserCreate, UserUpdate, PasswordReset,
    RoleCreate, RoleUpdate,
    PermissionAssignment,
)
from app.services.auth_service import AuthService
from app.events import publish_user_created

router = APIRouter(tags=["Users & RBAC"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ───────────────── Users ─────────────────

@router.post("/users")
def create_user(
    data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Create a new user (teacher, accountant, admin, etc.)."""
    # Force school_id from token, never from client
    data.school_id = school_id

    svc = AuthService(db)
    result = svc.create_user(data)

    if "error" in result:
        return {"error": {"code": result["error"], "message": result["message"],
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 409

    # Publish Kafka event
    publish_user_created(
        user_id=result["id"],
        school_id=result["school_id"],
        email=result["email"],
        full_name=result["full_name"],
        roles=[r["name"] for r in result.get("roles", [])],
        actor_user_id=current_user["sub"],
    )

    return {"data": result, "meta": _meta(request)}


@router.get("/users")
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """List users for the current school."""
    svc = AuthService(db)
    users, total = svc.list_users(school_id, page, page_size)
    meta = _meta(request)
    meta.update({"page": page, "page_size": page_size, "total": total,
                 "has_next": (page * page_size) < total})
    return {"data": users, "meta": meta}


@router.get("/users/{user_id}")
def get_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Get a user by ID (scoped to current school)."""
    svc = AuthService(db)
    result = svc.get_user(user_id, school_id)
    if result is None:
        return {"error": {"code": "NOT_FOUND", "message": "User not found",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 404
    return {"data": result, "meta": _meta(request)}


@router.put("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Update a user (scoped to current school)."""
    svc = AuthService(db)
    result = svc.update_user(user_id, school_id, data)
    if result is None:
        return {"error": {"code": "NOT_FOUND", "message": "User not found",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 404
    return {"data": result, "meta": _meta(request)}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    data: PasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Reset a user's password (admin action)."""
    svc = AuthService(db)
    success = svc.reset_password(user_id, school_id, data)
    if not success:
        return {"error": {"code": "NOT_FOUND", "message": "User not found",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 404
    return {"data": {"message": "Password reset successfully"}, "meta": _meta(request)}


# ───────────────── Roles ─────────────────

@router.get("/roles")
def list_roles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all roles."""
    svc = AuthService(db)
    return {"data": svc.list_roles(), "meta": _meta(request)}


@router.post("/roles")
def create_role(
    data: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new role."""
    svc = AuthService(db)
    result = svc.create_role(data)
    if "error" in result:
        return {"error": {"code": result["error"], "message": result["message"],
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 409
    return {"data": result, "meta": _meta(request)}


@router.put("/roles/{role_id}")
def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a role."""
    svc = AuthService(db)
    result = svc.update_role(role_id, data)
    if result is None:
        return {"error": {"code": "NOT_FOUND", "message": "Role not found",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 404
    return {"data": result, "meta": _meta(request)}


@router.post("/roles/{role_id}/permissions")
def assign_permission(
    role_id: uuid.UUID,
    data: PermissionAssignment,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Assign a permission to a role."""
    svc = AuthService(db)
    result = svc.assign_permission_to_role(role_id, data.permission_id)
    if result is None:
        return {"error": {"code": "NOT_FOUND", "message": "Role or permission not found",
                          "details": {}, "request_id": _meta(request)["request_id"]}}, 404
    return {"data": result, "meta": _meta(request)}


# ───────────────── Permissions ─────────────────

@router.get("/permissions")
def list_permissions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all available permissions."""
    svc = AuthService(db)
    return {"data": svc.list_permissions(), "meta": _meta(request)}
