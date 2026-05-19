"""
User preference endpoints
==========================
GET  /api/v1/me/preferences   — current user's accessibility/theme prefs
PATCH /api/v1/me/preferences  — update one or more fields (server validates
                                that `theme_pref` matches user's role tier)

Role → theme tier mapping (server-enforced — clients cannot escape persona):
  parent / student / guardian        → joyful
  teacher / head_teacher              → focus
  admin / school_admin / ministry /
  provincial_coordinator              → sovereign

If a user PATCHes a `theme_pref` outside their tier, we 403.
A row is lazily created on first PATCH; reads always return a value.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserPreference
from app.schemas.auth import UserPreferencesResponse, UserPreferencesUpdate


router = APIRouter(prefix="/me", tags=["Preferences"])


# Role → allowed theme tier. Matches packages/themes/src/index.ts ROLE_THEME_MAP.
_ROLE_THEME_TIER: dict[str, str] = {
    "parent": "joyful",
    "student": "joyful",
    "guardian": "joyful",
    "teacher": "focus",
    "head_teacher": "focus",
    "admin": "sovereign",
    "school_admin": "sovereign",
    "ministry": "sovereign",
    "provincial_coordinator": "sovereign",
}


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _default_theme_for_roles(role_names: list[str]) -> str:
    """Pick the strongest persona tier among the user's roles."""
    tiers = {_ROLE_THEME_TIER.get(r) for r in role_names}
    # Priority: sovereign > focus > joyful (admin trumps if user has multiple roles)
    if "sovereign" in tiers:
        return "sovereign"
    if "focus" in tiers:
        return "focus"
    if "joyful" in tiers:
        return "joyful"
    return "focus"


def _allowed_theme(role_names: list[str]) -> str:
    """Single theme tier this user is allowed to pick. Same as default."""
    return _default_theme_for_roles(role_names)


def _get_or_seed(db: Session, user: User) -> UserPreference:
    """Return the user's preferences row, creating it with role defaults if absent."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if pref:
        return pref

    role_names = [r.name for r in user.roles]
    theme = _default_theme_for_roles(role_names)
    text_size = "lg" if theme == "joyful" else "md"
    read_aloud = theme == "joyful"

    pref = UserPreference(
        user_id=user.id,
        language="en",
        theme_pref=theme,
        text_size=text_size,
        high_contrast=False,
        read_aloud_enabled=read_aloud,
        reduced_motion=False,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def _serialize(pref: UserPreference) -> dict:
    return {
        "language": pref.language,
        "theme_pref": pref.theme_pref,
        "text_size": pref.text_size,
        "high_contrast": pref.high_contrast,
        "read_aloud_enabled": pref.read_aloud_enabled,
        "reduced_motion": pref.reduced_motion,
    }


@router.get("/preferences")
def get_preferences(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's preferences (creating defaults if needed)."""
    user_id = uuid.UUID(current_user["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pref = _get_or_seed(db, user)
    return {"data": _serialize(pref), "meta": _meta(request)}


@router.patch("/preferences")
def update_preferences(
    payload: UserPreferencesUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update one or more preference fields. Server enforces persona tier."""
    user_id = uuid.UUID(current_user["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pref = _get_or_seed(db, user)

    # Validate theme switch against the user's role tier — cannot cross personas.
    if payload.theme_pref is not None:
        allowed = _allowed_theme([r.name for r in user.roles])
        if payload.theme_pref != allowed:
            raise HTTPException(
                status_code=403,
                detail=f"theme '{payload.theme_pref}' not permitted for this role; allowed: {allowed}",
            )
        pref.theme_pref = payload.theme_pref

    for field in ("language", "text_size", "high_contrast", "read_aloud_enabled", "reduced_motion"):
        value = getattr(payload, field)
        if value is not None:
            setattr(pref, field, value)

    db.commit()
    db.refresh(pref)
    return {"data": _serialize(pref), "meta": _meta(request)}
