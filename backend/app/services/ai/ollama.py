import json
import logging
import httpx
from typing import AsyncGenerator, List, Dict, Any, Optional
from backend.app.services.ai.base import BaseAIProvider
from backend.app.schemas.model import ModelInfo, ModelCapability, ProviderHealth
from backend.app.core.config import settings

logger = logging.getLogger("aurevon.ai.ollama")


class OllamaProvider(BaseAIProvider):
    def __init__(self, base_url: Optional[str] = None):
        super().__init__(name="ollama")
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = httpx.Timeout(connect=1.5, read=120.0, write=5.0, pool=5.0)

    async def check_health(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return ProviderHealth(
                        provider="ollama",
                        status="healthy",
                        url=self.base_url,
                        available_models=models,
                        error_message=None,
                    )
                else:
                    return ProviderHealth(
                        provider="ollama",
                        status="unhealthy",
                        url=self.base_url,
                        available_models=[],
                        error_message=f"HTTP {res.status_code}: {res.text}",
                    )
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return ProviderHealth(
                provider="ollama",
                status="offline",
                url=self.base_url,
                available_models=[],
                error_message="Ollama daemon is not reachable at " + self.base_url,
            )

    async def list_models(self) -> List[ModelInfo]:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = []
                    raw_models = data.get("models", [])
                    for m in raw_models:
                        name = m.get("name", "")
                        details = m.get("details", {})
                        size_mb = round(m.get("size", 0) / (1024 * 1024), 1)
                        size_str = f"{size_mb} MB" if size_mb < 1024 else f"{round(size_mb/1024, 2)} GB"
                        
                        family = details.get("family", "qwen")
                        is_vision = "vision" in name.lower() or "llava" in name.lower()
                        
                        models.append(
                            ModelInfo(
                                id=name,
                                name=name,
                                provider="ollama",
                                size=size_str,
                                parameters=details.get("parameter_size", "unknown"),
                                capabilities=ModelCapability(
                                    vision=is_vision,
                                    tools=True,
                                    context_length=settings.MODEL_CONTEXT_WINDOW,
                                    family=family,
                                ),
                                is_available=True,
                                is_default=(name == settings.DEFAULT_MODEL or name.startswith("qwen")),
                            )
                        )
                    if models:
                        return models
        except Exception as e:
            logger.info(f"Ollama models query failed: {e}. Returning configured fallback metadata.")

        # Fallback catalog metadata when Ollama is offline or empty
        return [
            ModelInfo(
                id="qwen2.5:3b",
                name="Qwen 2.5 3B (Local Recommended)",
                provider="ollama",
                size="1.9 GB",
                parameters="3B",
                capabilities=ModelCapability(
                    vision=False,
                    tools=True,
                    context_length=8192,
                    family="qwen",
                ),
                is_available=False,
                is_default=True,
            ),
            ModelInfo(
                id="qwen3:4b",
                name="Qwen 3 4B (Local Target)",
                provider="ollama",
                size="2.6 GB",
                parameters="4B",
                capabilities=ModelCapability(
                    vision=False,
                    tools=True,
                    context_length=8192,
                    family="qwen",
                ),
                is_available=False,
                is_default=False,
            ),
            ModelInfo(
                id="llama3.2:3b",
                name="Llama 3.2 3B",
                provider="ollama",
                size="2.0 GB",
                parameters="3B",
                capabilities=ModelCapability(
                    vision=False,
                    tools=True,
                    context_length=8192,
                    family="llama",
                ),
                is_available=False,
                is_default=False,
            ),
            ModelInfo(
                id="llava:7b",
                name="LLaVA 7B (Vision Multimodal)",
                provider="ollama",
                size="4.5 GB",
                parameters="7B",
                capabilities=ModelCapability(
                    vision=True,
                    tools=False,
                    context_length=4096,
                    family="llava",
                ),
                is_available=False,
                is_default=False,
            ),
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model or settings.DEFAULT_MODEL,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": context_window or settings.MODEL_CONTEXT_WINDOW,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(f"Ollama stream error status {response.status_code}: {err_text.decode('utf-8', errors='ignore')}")
                        yield f"**Provider Error (HTTP {response.status_code})**: Ollama returned an error: `{err_text.decode('utf-8', errors='ignore')}`.\n\n*Make sure the model `{payload['model']}` is pulled via `ollama run {payload['model']}`.*"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk_data = json.loads(line)
                            message_obj = chunk_data.get("message", {})
                            content_piece = message_obj.get("content", "")
                            if content_piece:
                                yield content_piece
                            if chunk_data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning(f"Ollama connection refused at {self.base_url}: {e}")
            guidance = (
                f"### ⚠️ Local Ollama Runtime Notice\n\n"
                f"AUREVON AI could not connect to Ollama at `{self.base_url}`.\n\n"
                f"**To activate local AI inference:**\n"
                f"1. Download and start [Ollama](https://ollama.com) on your Windows machine, or run:\n"
                f"   ```powershell\n"
                f"   winget install Ollama.Ollama\n"
                f"   ollama run {model or settings.DEFAULT_MODEL}\n"
                f"   ```\n"
                f"2. Once Ollama is running, AUREVON will automatically detect it and stream responses directly from your local hardware.\n\n"
                f"---\n"
                f"*Echo Diagnostic: Your prompt was successfully captured and persisted in the database.*"
            )
            yield guidance
        except Exception as e:
            logger.exception("Unexpected error in Ollama stream_chat")
            yield f"\n\n**System Error**: An unexpected error occurred while communicating with the model provider: `{str(e)}`."

    async def complete_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> str:
        accumulated = []
        async for chunk in self.stream_chat(messages, model, temperature, context_window):
            accumulated.append(chunk)
        return "".join(accumulated)
