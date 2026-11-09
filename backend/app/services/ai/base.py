from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from backend.app.schemas.model import ModelInfo, ProviderHealth


class BaseAIProvider(ABC):
    """Abstract Base Class for AI Model Providers (Ollama, Cloud, etc.)."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def check_health(self) -> ProviderHealth:
        """Perform a live health check on the provider."""
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List models available on this provider."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens chunk by chunk."""
        pass

    @abstractmethod
    async def complete_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> str:
        """Generate a complete non-streamed response."""
        pass
