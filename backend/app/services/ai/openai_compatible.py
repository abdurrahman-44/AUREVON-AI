import json
import logging
import httpx
from typing import AsyncGenerator, List, Dict, Any, Optional
from backend.app.services.ai.base import BaseAIProvider
from backend.app.schemas.model import ModelInfo, ModelCapability, ProviderHealth

logger = logging.getLogger("aurevon.ai.openai_compatible")


class OpenAICompatibleProvider(BaseAIProvider):
    """
    Standardized provider for OpenAI-compatible APIs (OpenAI, Groq, DeepSeek, OpenRouter, vLLM).
    """

    def __init__(
        self,
        name: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
    ):
        super().__init__(name=name)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=10.0)

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def check_health(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth(
                provider=self.name,
                status="unhealthy",
                url=self.base_url,
                available_models=[],
                error_message=f"API key not configured for {self.name}.",
            )
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    models = [m["id"] for m in data.get("data", [])]
                    return ProviderHealth(
                        provider=self.name,
                        status="healthy",
                        url=self.base_url,
                        available_models=models[:10],
                        error_message=None,
                    )
                else:
                    return ProviderHealth(
                        provider=self.name,
                        status="unhealthy",
                        url=self.base_url,
                        available_models=[],
                        error_message=f"HTTP {res.status_code}: {res.text[:100]}",
                    )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                status="offline",
                url=self.base_url,
                available_models=[],
                error_message=str(e),
            )

    async def list_models(self) -> List[ModelInfo]:
        if not self.api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("data", []):
                        mid = item.get("id", "")
                        results.append(
                            ModelInfo(
                                id=mid,
                                name=f"{mid} ({self.name.capitalize()})",
                                provider=self.name,
                                capabilities=ModelCapability(
                                    vision="vision" in mid or "4o" in mid,
                                    tools=True,
                                    context_length=128000 if "gpt-4" in mid else 32768,
                                    family=self.name,
                                ),
                                is_available=True,
                                is_default=False,
                            )
                        )
                    return results
        except Exception as e:
            logger.warning(f"Could not fetch models for {self.name}: {e}")
        return []

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            yield f"**Provider Error**: `{self.name}` requires an API key. Please configure your API key in Model Settings."
            return

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        err = await response.aread()
                        yield f"**API Error ({response.status_code})**: {err.decode('utf-8', errors='ignore')}"
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_part = line[6:]
                        if data_part == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data_part)
                            choices = parsed.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield delta
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.exception("Error in OpenAI-compatible stream_chat")
            yield f"\n\n**Provider Connection Error**: `{str(e)}`"

    async def complete_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> str:
        chunks = []
        async for c in self.stream_chat(messages, model, temperature, context_window):
            chunks.append(c)
        return "".join(chunks)
