from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="Email address or username")
    password: str = Field(..., min_length=1)


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
    created_at: datetime
    settings: Optional[UserSettingsResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
