import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: "UserBrief"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    school_id: str
    roles: list[str] = []
    jti: str
    exp: int


# --- Users ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    school_id: uuid.UUID
    role_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    role_ids: Optional[list[uuid.UUID]] = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserBrief(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    roles: list[str]

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    school_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list["RoleResponse"] = []
    permissions: list[str] = []

    class Config:
        from_attributes = True


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    school_id: uuid.UUID
    is_active: bool
    roles: list[str]
    permissions: list[str]

    class Config:
        from_attributes = True


# --- Roles ---

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    school_id: Optional[uuid.UUID] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    school_id: Optional[uuid.UUID]
    created_at: datetime
    permissions: list["PermissionResponse"] = []

    class Config:
        from_attributes = True


class RoleAssignment(BaseModel):
    role_id: uuid.UUID


class PermissionAssignment(BaseModel):
    permission_id: uuid.UUID


# --- Permissions ---

class PermissionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    resource: str
    action: str

    class Config:
        from_attributes = True


# --- User Preferences ---
from typing import Literal

Language = Literal["en", "sn", "nd"]
ThemePref = Literal["joyful", "focus", "sovereign"]
TextSize = Literal["sm", "md", "lg", "xl"]


class UserPreferencesResponse(BaseModel):
    """Per-user accessibility, locale and theme preferences."""
    language: Language = "en"
    theme_pref: ThemePref = "focus"
    text_size: TextSize = "md"
    high_contrast: bool = False
    read_aloud_enabled: bool = False
    reduced_motion: bool = False

    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    """Patch payload — all fields optional."""
    language: Optional[Language] = None
    theme_pref: Optional[ThemePref] = None
    text_size: Optional[TextSize] = None
    high_contrast: Optional[bool] = None
    read_aloud_enabled: Optional[bool] = None
    reduced_motion: Optional[bool] = None
