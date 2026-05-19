import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User, Role, Permission, RefreshToken, TokenBlacklist, LoginAudit
from app.schemas.auth import (
    LoginRequest, UserCreate, UserUpdate, PasswordReset,
    RoleCreate, RoleUpdate,
    TokenResponse, UserBrief, UserResponse, MeResponse, RoleResponse,
    PermissionResponse,
)
from app.utils.security import (
    hash_password, verify_password, hash_token,
    create_access_token, create_refresh_token, decode_token,
)
from app.config import get_settings

settings = get_settings()


class AuthService:
    """Production-grade authentication and authorization service."""

    def __init__(self, db: Session):
        self.db = db

    # ───────────────── Authentication ─────────────────

    def login(
        self,
        data: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """Authenticate user by email+password, return tokens + user brief."""
        # Find user (we try all schools — email+school_id is unique, but login is email-only)
        user = self.db.query(User).filter(User.email == data.email).first()

        if not user or not verify_password(data.password, user.password_hash):
            self._log_login(data.email, None, False, ip_address, user_agent, "invalid_credentials")
            self.db.commit()  # Persist audit log entry
            return None  # Caller handles 401

        if not user.is_active:
            self._log_login(data.email, user.school_id, False, ip_address, user_agent, "account_disabled")
            self.db.commit()  # Persist audit log entry
            return None

        roles = [r.name for r in user.roles]
        permissions = self._expand_permissions(user)

        # Create tokens
        access_token, access_jti, _ = create_access_token(str(user.id), str(user.school_id), roles, permissions)
        refresh_token, refresh_jti, refresh_exp = create_refresh_token(str(user.id), str(user.school_id), roles, permissions)

        # Store refresh token hash in DB
        rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            jti=refresh_jti,
            expires_at=refresh_exp,
        )
        self.db.add(rt)
        self._log_login(data.email, user.school_id, True, ip_address, user_agent)
        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "name": user.full_name,
                "email": user.email,
                "roles": roles,
            },
        }

    def refresh_tokens(self, refresh_token_str: str) -> Optional[dict]:
        """Validate refresh token, rotate, and return new token pair."""
        try:
            payload = decode_token(refresh_token_str)
        except Exception:
            return None

        if payload.get("type") != "refresh":
            return None

        # Find stored refresh token by hash
        token_hash = hash_token(refresh_token_str)
        stored = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        ).first()

        if not stored:
            return None

        # Check expiry
        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None

        user = self.db.query(User).filter(User.id == stored.user_id).first()
        if not user or not user.is_active:
            return None

        # Revoke old refresh token (rotation)
        stored.revoked = True

        roles = [r.name for r in user.roles]
        permissions = self._expand_permissions(user)

        # Issue new pair
        access_token, _, _ = create_access_token(str(user.id), str(user.school_id), roles, permissions)
        new_refresh, new_jti, new_exp = create_refresh_token(str(user.id), str(user.school_id), roles, permissions)

        new_rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh),
            jti=new_jti,
            expires_at=new_exp,
        )
        self.db.add(new_rt)
        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "name": user.full_name,
                "email": user.email,
                "roles": roles,
            },
        }

    def logout(self, token_payload: dict) -> None:
        """Blacklist the current access token and revoke all user refresh tokens."""
        user_id = uuid.UUID(token_payload["sub"])

        # Blacklist access token
        bl = TokenBlacklist(
            jti=token_payload["jti"],
            user_id=user_id,
            expires_at=datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc),
        )
        self.db.add(bl)

        # Revoke all refresh tokens for this user
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
        ).update({"revoked": True})

        self.db.commit()

    def get_me(self, user_id: uuid.UUID) -> dict:
        """Return current user profile with expanded permissions + preferences."""
        from app.models.user import UserPreference  # local import avoids cycles

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # Inline preference lookup. If absent, expose role-defaulted values
        # without persisting — first PATCH will materialise the row.
        pref = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user.id)
            .first()
        )
        role_names = [r.name for r in user.roles]
        if pref is None:
            # Mirror _default_theme_for_roles from app/api/preferences.py
            tier_map = {
                "parent": "joyful", "student": "joyful", "guardian": "joyful",
                "teacher": "focus", "head_teacher": "focus",
                "admin": "sovereign", "school_admin": "sovereign",
                "ministry": "sovereign", "provincial_coordinator": "sovereign",
            }
            tiers = {tier_map.get(r) for r in role_names}
            theme = "sovereign" if "sovereign" in tiers else (
                "focus" if "focus" in tiers else (
                    "joyful" if "joyful" in tiers else "focus"
                )
            )
            preferences = {
                "language": "en",
                "theme_pref": theme,
                "text_size": "lg" if theme == "joyful" else "md",
                "high_contrast": False,
                "read_aloud_enabled": theme == "joyful",
                "reduced_motion": False,
            }
        else:
            preferences = {
                "language": pref.language,
                "theme_pref": pref.theme_pref,
                "text_size": pref.text_size,
                "high_contrast": pref.high_contrast,
                "read_aloud_enabled": pref.read_aloud_enabled,
                "reduced_motion": pref.reduced_motion,
            }

        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "school_id": str(user.school_id),
            "is_active": user.is_active,
            "roles": role_names,
            "permissions": self._expand_permissions(user),
            "preferences": preferences,
        }

    # ───────────────── User CRUD ─────────────────

    def create_user(self, data: UserCreate) -> dict:
        """Create a new user. Returns serialized user dict."""
        # Check uniqueness (email + school_id)
        existing = self.db.query(User).filter(
            User.email == data.email,
            User.school_id == data.school_id,
        ).first()
        if existing:
            return {"error": "EMAIL_EXISTS", "message": "Email already registered for this school"}

        user = User(
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            school_id=data.school_id,
        )

        # Assign roles
        if data.role_ids:
            roles = self.db.query(Role).filter(Role.id.in_(data.role_ids)).all()
            user.roles = roles

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return self._serialize_user(user)

    def list_users(self, school_id: uuid.UUID, page: int, page_size: int) -> tuple[list[dict], int]:
        """List users for a school with pagination."""
        query = self.db.query(User).filter(User.school_id == school_id)
        total = query.count()
        users = query.offset((page - 1) * page_size).limit(page_size).all()
        return [self._serialize_user(u) for u in users], total

    def get_user(self, user_id: uuid.UUID, school_id: uuid.UUID) -> Optional[dict]:
        """Get single user, scoped to school."""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.school_id == school_id,
        ).first()
        if not user:
            return None
        return self._serialize_user(user)

    def update_user(self, user_id: uuid.UUID, school_id: uuid.UUID, data: UserUpdate) -> Optional[dict]:
        """Update user, scoped to school."""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.school_id == school_id,
        ).first()
        if not user:
            return None

        if data.email is not None:
            user.email = data.email
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.role_ids is not None:
            roles = self.db.query(Role).filter(Role.id.in_(data.role_ids)).all()
            user.roles = roles

        self.db.commit()
        self.db.refresh(user)
        return self._serialize_user(user)

    def reset_password(self, user_id: uuid.UUID, school_id: uuid.UUID, data: PasswordReset) -> bool:
        """Reset user password. Returns True on success."""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.school_id == school_id,
        ).first()
        if not user:
            return False
        user.password_hash = hash_password(data.new_password)
        # Revoke all refresh tokens
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked == False,
        ).update({"revoked": True})
        self.db.commit()
        return True

    # ───────────────── RBAC ─────────────────

    def create_role(self, data: RoleCreate) -> dict:
        """Create a role."""
        if self.db.query(Role).filter(Role.name == data.name).first():
            return {"error": "ROLE_EXISTS", "message": "Role already exists"}
        role = Role(name=data.name, description=data.description, school_id=data.school_id)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return self._serialize_role(role)

    def list_roles(self) -> list[dict]:
        return [self._serialize_role(r) for r in self.db.query(Role).all()]

    def update_role(self, role_id: uuid.UUID, data: RoleUpdate) -> Optional[dict]:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return None
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        self.db.commit()
        self.db.refresh(role)
        return self._serialize_role(role)

    def assign_permission_to_role(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> Optional[dict]:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return None
        perm = self.db.query(Permission).filter(Permission.id == permission_id).first()
        if not perm:
            return None
        if perm not in role.permissions:
            role.permissions.append(perm)
            self.db.commit()
            self.db.refresh(role)
        return self._serialize_role(role)

    def list_permissions(self) -> list[dict]:
        return [self._serialize_permission(p) for p in self.db.query(Permission).all()]

    # ───────────────── Token Checks ─────────────────

    def is_token_blacklisted(self, jti: str) -> bool:
        return self.db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None

    # ───────────────── Helpers ─────────────────

    def _expand_permissions(self, user: User) -> list[str]:
        perms = set()
        for role in user.roles:
            for p in role.permissions:
                perms.add(f"{p.resource}:{p.action}")
        return sorted(perms)

    def _log_login(self, email, school_id, success, ip_address, user_agent, reason=None):
        audit = LoginAudit(
            email=email,
            school_id=school_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=reason,
        )
        self.db.add(audit)

    def _serialize_user(self, user: User) -> dict:
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "school_id": str(user.school_id),
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "roles": [{"id": str(r.id), "name": r.name, "description": r.description,
                       "school_id": str(r.school_id) if r.school_id else None,
                       "created_at": r.created_at.isoformat() if r.created_at else None,
                       "permissions": [self._serialize_permission(p) for p in r.permissions]}
                      for r in user.roles],
            "permissions": self._expand_permissions(user),
        }

    def _serialize_role(self, role: Role) -> dict:
        return {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "school_id": str(role.school_id) if role.school_id else None,
            "created_at": role.created_at.isoformat() if role.created_at else None,
            "permissions": [self._serialize_permission(p) for p in role.permissions],
        }

    def _serialize_permission(self, p: Permission) -> dict:
        return {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "resource": p.resource,
            "action": p.action,
        }
