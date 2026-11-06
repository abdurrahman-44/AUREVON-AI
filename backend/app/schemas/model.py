from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ModelCapability(BaseModel):
    vision: bool = False
    tools: bool = False
    context_length: int = 8192
    family: str = "qwen"


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    size: Optional[str] = None
    parameters: Optional[str] = None
    capabilities: ModelCapability = ModelCapability()
    is_available: bool = True
    is_default: bool = False


class ProviderHealth(BaseModel):
    provider: str
    status: str  # "healthy", "unhealthy", "offline"
    url: str
    available_models: List[str] = []
    error_message: Optional[str] = None


class SystemStatusResponse(BaseModel):
    app_name: str
    version: str
    database: str
    providers: List[ProviderHealth]
