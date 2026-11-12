from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class OwnerBootstrapRequest(UserRegisterRequest):
    bootstrap_token: Optional[str] = Field(None, description="Required when ADMIN_BOOTSTRAP_TOKEN is configured")


class BootstrapStatusResponse(BaseModel):
    owner_exists: bool
    requires_bootstrap_token: bool
    web_bootstrap_allowed: bool


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Email address or username")
    password: str = Field(..., min_length=1)
    totp_code: Optional[str] = Field(None, description="6-digit 2FA authenticator code when enabled")


class UserSettingsResponse(BaseModel):
    theme: str = "dark"
    default_model: str = "qwen2.5:3b"
    memory_enabled: bool = True
    other_preferences: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdate(BaseModel):
    theme: Optional[str] = Field(None, pattern="^(dark|light|system)$")
    default_model: Optional[str] = None
    memory_enabled: Optional[bool] = None
    other_preferences: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str = "user"
    is_active: bool = True
    totp_enabled: bool = False
    last_active_at: Optional[datetime] = None
    created_at: datetime
    settings: Optional[UserSettingsResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
