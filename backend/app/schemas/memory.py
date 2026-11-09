from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=2, max_length=1000)
    category: Optional[str] = Field("general", max_length=64)
    source: Optional[str] = Field("user", max_length=255)


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=2, max_length=1000)
    category: Optional[str] = None
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    content: str
    category: str
    source: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
