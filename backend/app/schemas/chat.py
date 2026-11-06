from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequestMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="Existing conversation UUID or None to create a new one")
    message: str = Field(..., min_length=1, description="User prompt message")
    model: Optional[str] = Field(None, description="Model to use (defaults to configured system model)")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    stream: bool = Field(True, description="Whether to stream response chunks via SSE")


class ChatChunk(BaseModel):
    conversation_id: str
    message_id: str
    delta: str
    done: bool = False
    model: Optional[str] = None
    finish_reason: Optional[str] = None
