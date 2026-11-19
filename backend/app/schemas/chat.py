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
    images: Optional[List[str]] = Field(None, description="Optional base64-encoded images for multimodal vision models")
    document_ids: Optional[List[str]] = Field(None, description="Optional uploaded document IDs scoped to this turn")
    web_search: bool = Field(False, description="Optional user request to enable live web lookup for this turn")
    allow_cloud: bool = Field(False, description="Explicit user consent for cloud inference when enabled on server")
    regenerate: bool = Field(False, description="Replace the trailing assistant turn cleanly when regenerating")


class ChatChunk(BaseModel):
    conversation_id: str
    message_id: str
    delta: str
    done: bool = False
    model: Optional[str] = None
    finish_reason: Optional[str] = None
