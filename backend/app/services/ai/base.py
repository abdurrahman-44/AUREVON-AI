from abc import ABC, abstractmethod
import inspect
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

    async def stream_chat_with_metrics(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream structured token/telemetry/error events from the provider."""
        async for token in self.stream_chat(messages, model, temperature, context_window):
            yield {"type": "token", "text": token}
        yield {
            "type": "done",
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

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


async def invoke_provider_stream(
    provider: BaseAIProvider,
    messages: List[Dict[str, Any]],
    model: str,
    temperature: float = 0.7,
    context_window: int = 8192,
    max_tokens: Optional[int] = None,
    keep_alive: Optional[str] = None,
    request_timeout: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Call stream_chat_with_metrics while staying backwards-compatible with custom/mock subclasses."""
    sig = inspect.signature(provider.stream_chat_with_metrics)
    kwargs: Dict[str, Any] = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
        "context_window": context_window,
    }
    if "max_tokens" in sig.parameters and max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if "keep_alive" in sig.parameters and keep_alive is not None:
        kwargs["keep_alive"] = keep_alive
    if "request_timeout" in sig.parameters and request_timeout is not None:
        kwargs["request_timeout"] = request_timeout

    async for event in provider.stream_chat_with_metrics(**kwargs):
        yield event
