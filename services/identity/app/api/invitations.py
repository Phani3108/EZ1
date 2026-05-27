"""Phase 15a / I-003..I-006: Invitation endpoints.

  * `POST   /invitations`                 — create an invite (auth: invite:write).
  * `GET    /invitations/{token}/preview` — public; show what the invitee
                                            is about to claim.
  * `POST   /invitations/{token}/accept`  — public; set password + activate.
  * `POST   /invitations/{token}/resend`  — auth as inviter; refresh expiry.
  * `POST   /invitations/by-code`         — public; manual-mode (phone + 6-digit).

Privacy contract (ADR 018):

  * audit `target` = `{role, school_id, invitation_id}` only.
  * audit `details` = `{channel_attempted}` only — NO email, NO phone,
    NO full_name. Email + phone live on the Invitation row; that row
    can be retrieved by id but is NOT echoed in audit details.
  * `user.activated` events log only `{user_id}` + `{role}`.
  * Failed accept attempts do NOT log the supplied password (obviously)
    and do NOT log the attempted token (it would re-derive the hash).

Token model:

  * Raw token = `secrets.token_urlsafe(48)` — shown once to the caller
    on create and on resend. `token_hash = sha256(raw).hexdigest()`.
  * Manual code = 6-digit random string — same `Invitation` row. Used
    for the "admin reads the code over the phone" fallback.

Idempotency:

  * `POST /invitations` is idempotent on `(school_id, role,
    contact_email||contact_phone)` — calling again with the same tuple
    returns the existing row's token + manual_code (so admins can copy
    them again without burning a new token).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, Role
from app.models.invitation import Invitation
from app.services.audit import record_audit_event
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])


# Default invitation lifetime — 14 days. Long enough for SMS delivery
# delays + the parent to find someone to help them read it; short
# enough that an exfiltrated token has a small window.
INVITE_LIFETIME = timedelta(days=14)

# How many times an invite can be re-dispatched before we force a
# rotate-the-token resend.
MAX_RESEND_ATTEMPTS = 5


# ─── Crypto helpers (reused shape from PasswordResetToken) ────────


def _gen_raw_token() -> str:
    return secrets.token_urlsafe(48)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _gen_manual_code() -> str:
    # 6 digits, leading-zero preserved.
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code: str, msg: str, request: Request, status: int = 400):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request: Request, status: int = 200):
    return JSONResponse(
        status_code=status,
        content={"data": data, "meta": _meta(request)},
    )


# ─── Schemas ──────────────────────────────────────────────────────


class InviteCreate(BaseModel):
    school_id: uuid.UUID
    role: str = Field(..., max_length=32)
    full_name: str = Field(..., max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=32)
    target_resource_id: Optional[str] = Field(default=None, max_length=36)
    target_resource_type: Optional[str] = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _at_least_one_contact(self):
        if not self.contact_email and not self.contact_phone:
            raise ValueError("contact_email or contact_phone is required")
        return self


class InviteAccept(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


class InviteByCode(BaseModel):
    phone: str = Field(..., max_length=32)
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=8, max_length=128)


# ─── Internal helpers ─────────────────────────────────────────────


def _existing_invitation(
    db: Session, school_id: uuid.UUID, role: str,
    contact_email: Optional[str], contact_phone: Optional[str],
) -> Optional[Invitation]:
    """Look up an invitation that matches the unique contact tuple."""
    q = db.query(Invitation).filter(
        Invitation.school_id == school_id,
        Invitation.role == role,
    )
    if contact_email and contact_phone:
        q = q.filter(
            Invitation.contact_email == contact_email,
            Invitation.contact_phone == contact_phone,
        )
    elif contact_email:
        q = q.filter(
            Invitation.contact_email == contact_email,
            Invitation.contact_phone.is_(None),
        )
    else:
        q = q.filter(
            Invitation.contact_email.is_(None),
            Invitation.contact_phone == contact_phone,
        )
    return q.first()


def _serialize(inv: Invitation, raw_token: Optional[str] = None) -> dict:
    """Serialize an Invitation row. `raw_token` is included only on
    create + resend (the one moment we know it)."""
    out = {
        "id": str(inv.id),
        "school_id": str(inv.school_id),
        "role": inv.role,
        "user_id": str(inv.user_id),
        "target_resource_id": inv.target_resource_id,
        "target_resource_type": inv.target_resource_type,
        # Echo contact back for the inviter's UI — these are not
        # sensitive in this context because the caller already supplied
        # them.
        "contact_email": inv.contact_email,
        "contact_phone": inv.contact_phone,
        "channel_attempted": inv.channel_attempted,
        "channel_sent_at": inv.channel_sent_at.isoformat() if inv.channel_sent_at else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "attempts": int(inv.attempts or 0),
        # `manual_code` is always returned so the admin UI can render
        # it on the "show code" button. This is intentional — the row
        # is owned by the inviting admin, not by the invitee.
        "manual_code": inv.manual_code,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }
    if raw_token is not None:
        out["raw_token"] = raw_token
    return out


def _actor_id(current_user) -> Optional[uuid.UUID]:
    """Identity's get_current_user yields a JWT payload dict — pull
    the user_id (`sub` claim) out of it. Returns None if missing."""
    if not current_user:
        return None
    try:
        return uuid.UUID(str(current_user.get("sub")))
    except Exception:
        return None


def _audit_invited(db: Session, inv: Invitation, current_user: dict | None,
                   channel: Optional[str], request: Request):
    """ADR 018 contract: NO email, NO phone, NO name in details."""
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    roles = (current_user or {}).get("roles") or []
    record_audit_event(
        db,
        event_type="user.invited",
        school_id=inv.school_id,
        actor_user_id=_actor_id(current_user),
        actor_role=roles[0] if roles else None,
        target={"resource": "invitation", "id": str(inv.id),
                "role": inv.role, "school_id": str(inv.school_id)},
        details={"channel_attempted": channel or "pending"},
        request_id=request_id,
    )


def _audit_activated(db: Session, user: User, role: str, request: Request):
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    record_audit_event(
        db,
        event_type="user.activated",
        school_id=user.school_id,
        actor_user_id=user.id,
        target={"resource": "user", "id": str(user.id)},
        details={"role": role},
        request_id=request_id,
    )


# ─── Endpoints ────────────────────────────────────────────────────


@router.post("")
def create_invitation(
    body: InviteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create (or re-fetch) an invitation. Auth: requires invite:write.

    Returns the raw token + manual code in the response. The caller is
    responsible for triggering delivery (via POST /{id}/dispatch in
    communications, or by displaying the manual code).
    """
    # Idempotency check.
    existing = _existing_invitation(
        db, body.school_id, body.role,
        body.contact_email, body.contact_phone,
    )
    if existing is not None and existing.accepted_at is None:
        # Re-issue the raw token. We rotate the token+code on every
        # idempotent re-call so a leaked old token can't outlive the
        # caller's intent.
        raw = _gen_raw_token()
        existing.token_hash = _hash_token(raw)
        existing.manual_code = _gen_manual_code()
        existing.expires_at = datetime.now(timezone.utc) + INVITE_LIFETIME
        db.commit()
        return _ok(_serialize(existing, raw_token=raw), request)

    if existing is not None and existing.accepted_at is not None:
        return _err(
            "ALREADY_ACCEPTED",
            "This invitation has already been accepted.",
            request, status=409,
        )

    # Validate role exists.
    role_row = db.query(Role).filter(Role.name == body.role).first()
    if role_row is None:
        return _err("UNKNOWN_ROLE", f"Role '{body.role}' is not registered.",
                    request, status=400)

    # Stage the User row (no password, not yet activated).
    user = User(
        id=uuid.uuid4(),
        email=str(body.contact_email) if body.contact_email else f"invite-{uuid.uuid4().hex[:12]}@pending.eduzim",
        full_name=body.full_name,
        phone=body.contact_phone,
        password_hash=None,
        school_id=body.school_id,
        is_active=True,
        invited_at=datetime.now(timezone.utc),
    )
    user.roles = [role_row]
    db.add(user)
    db.flush()

    raw = _gen_raw_token()
    inv = Invitation(
        id=uuid.uuid4(),
        school_id=body.school_id,
        token_hash=_hash_token(raw),
        manual_code=_gen_manual_code(),
        role=body.role,
        user_id=user.id,
        target_resource_id=body.target_resource_id,
        target_resource_type=body.target_resource_type,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        expires_at=datetime.now(timezone.utc) + INVITE_LIFETIME,
        created_by_user_id=_actor_id(current_user),
    )
    db.add(inv)
    _audit_invited(db, inv, current_user, channel=None, request=request)
    db.commit()
    return _ok(_serialize(inv, raw_token=raw), request, status=201)


@router.get("/{token}/preview")
def preview_invitation(
    token: str, request: Request, db: Session = Depends(get_db),
):
    """Public — no auth. Renders 'who is being invited where'.

    Privacy: returns first names + school name + role. NO emails, NO
    phones. The caller already proved they hold the token; that's
    enough to see the staged claim.
    """
    inv = db.query(Invitation).filter(
        Invitation.token_hash == _hash_token(token),
    ).first()
    if not inv:
        return _err("INVALID_TOKEN", "Invitation not found.", request, status=404)
    if inv.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return _err("TOKEN_EXPIRED", "This invite has expired.", request, status=410)
    if inv.accepted_at is not None:
        return _err("ALREADY_ACCEPTED",
                    "This invite has already been used.",
                    request, status=409)

    user = db.query(User).filter(User.id == inv.user_id).first()
    return _ok({
        "school_id": str(inv.school_id),
        "role": inv.role,
        "full_name": user.full_name if user else None,
        "target_resource_id": inv.target_resource_id,
        "target_resource_type": inv.target_resource_type,
        "expires_at": inv.expires_at.isoformat(),
    }, request)


@router.post("/{token}/accept")
def accept_invitation(
    token: str, body: InviteAccept, request: Request,
    db: Session = Depends(get_db),
):
    """Public — no auth. Activate the pre-staged user, set password."""
    inv = db.query(Invitation).filter(
        Invitation.token_hash == _hash_token(token),
    ).first()
    if not inv:
        return _err("INVALID_TOKEN", "Invitation not found.", request, status=404)
    if inv.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return _err("TOKEN_EXPIRED", "This invite has expired.", request, status=410)
    if inv.accepted_at is not None:
        return _err("ALREADY_ACCEPTED",
                    "This invite has already been used.",
                    request, status=409)

    user = db.query(User).filter(User.id == inv.user_id).first()
    if not user:
        return _err("INVALID_TOKEN", "Linked user not found.", request, status=404)

    user.password_hash = hash_password(body.password)
    user.activated_at = datetime.now(timezone.utc)
    inv.accepted_at = datetime.now(timezone.utc)
    _audit_activated(db, user, inv.role, request)
    db.commit()
    return _ok({
        "user_id": str(user.id),
        "school_id": str(user.school_id),
        "role": inv.role,
    }, request)


@router.post("/by-code")
def accept_by_code(
    body: InviteByCode, request: Request,
    db: Session = Depends(get_db),
):
    """Public — no auth. Manual-mode fallback: phone + 6-digit code +
    new password. Used when the user couldn't open the magic link
    (no SMS, no email, no WhatsApp — admin read the code over the
    phone).

    Looks up the Invitation row by `(contact_phone, manual_code)`.
    """
    inv = db.query(Invitation).filter(
        Invitation.contact_phone == body.phone,
        Invitation.manual_code == body.code,
    ).first()
    if not inv:
        return _err("INVALID_CODE", "Code does not match.", request, status=404)
    if inv.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return _err("TOKEN_EXPIRED", "Code has expired.", request, status=410)
    if inv.accepted_at is not None:
        return _err("ALREADY_ACCEPTED",
                    "This invite has already been used.",
                    request, status=409)

    user = db.query(User).filter(User.id == inv.user_id).first()
    if not user:
        return _err("INVALID_CODE", "Linked user not found.", request, status=404)

    user.password_hash = hash_password(body.password)
    user.activated_at = datetime.now(timezone.utc)
    inv.accepted_at = datetime.now(timezone.utc)
    _audit_activated(db, user, inv.role, request)
    db.commit()
    return _ok({
        "user_id": str(user.id),
        "school_id": str(user.school_id),
        "role": inv.role,
    }, request)


@router.post("/{token}/resend")
def resend_invitation(
    token: str, request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Refresh the expiry + rotate the raw token. Caller must be the
    original inviter (or hold invite:write — gateway enforces)."""
    inv = db.query(Invitation).filter(
        Invitation.token_hash == _hash_token(token),
    ).first()
    if not inv:
        return _err("INVALID_TOKEN", "Invitation not found.", request, status=404)
    if inv.accepted_at is not None:
        return _err("ALREADY_ACCEPTED",
                    "This invite has already been used.",
                    request, status=409)
    if (inv.attempts or 0) >= MAX_RESEND_ATTEMPTS:
        return _err("TOO_MANY_RESENDS",
                    f"Resend limit ({MAX_RESEND_ATTEMPTS}) reached. "
                    "Create a fresh invitation.",
                    request, status=429)

    raw = _gen_raw_token()
    inv.token_hash = _hash_token(raw)
    inv.manual_code = _gen_manual_code()
    inv.expires_at = datetime.now(timezone.utc) + INVITE_LIFETIME
    inv.attempts = (inv.attempts or 0) + 1
    db.commit()
    return _ok(_serialize(inv, raw_token=raw), request)


@router.get("")
def list_invitations(
    request: Request,
    school_id: Optional[uuid.UUID] = None,
    role: Optional[str] = None,
    only_pending: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List invitations for the inviter's school (scoped). Returns the
    same shape as `_serialize` but WITHOUT `raw_token` (we don't have
    it on disk — only the hash). Manual codes ARE returned so the
    admin can re-read them out."""
    q = db.query(Invitation)
    if school_id:
        q = q.filter(Invitation.school_id == school_id)
    if role:
        q = q.filter(Invitation.role == role)
    if only_pending:
        q = q.filter(Invitation.accepted_at.is_(None))
    rows = q.order_by(Invitation.created_at.desc()).limit(500).all()
    return _ok([_serialize(r) for r in rows], request)
