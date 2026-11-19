from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class MessageBase(BaseModel):
    role: str = Field(..., description="Role of the sender: user, assistant, system")
    content: str = Field(..., description="Text content of the message")
    model: Optional[str] = Field(None, description="Model identifier used to produce response")


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    token_usage: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

