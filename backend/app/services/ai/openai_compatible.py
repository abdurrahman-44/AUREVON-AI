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

    async def stream_chat_with_metrics(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
        max_tokens: Optional[int] = None,
        keep_alive: Optional[str] = None,
        request_timeout: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.api_key:
            yield {
                "type": "error",
                "error_category": "missing_api_key",
                "error_message": f"{self.name} API key is not configured",
                "user_message": f"**Provider Error**: `{self.name}` is not configured on the server. Contact the platform administrator.",
            }
            return

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens and max_tokens > 0:
            payload["max_tokens"] = int(max_tokens)
        if self.name in ("openai", "groq"):
            payload["stream_options"] = {"include_usage": True}

        timeout_cfg = (
            httpx.Timeout(connect=5.0, read=float(request_timeout), write=10.0, pool=10.0)
            if request_timeout and request_timeout > 0
            else self.timeout
        )

        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None

        try:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        err = (await response.aread()).decode("utf-8", errors="ignore")
                        yield {
                            "type": "error",
                            "error_category": f"http_{response.status_code}",
                            "error_message": f"{self.name} HTTP {response.status_code}: {err[:180]}",
                            "user_message": f"**Provider Error ({response.status_code})**: Unable to generate response from `{self.name}`.",
                        }
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
                            usage = parsed.get("usage") or parsed.get("x_groq", {}).get("usage")
                            if isinstance(usage, dict):
                                if isinstance(usage.get("prompt_tokens"), int):
                                    prompt_tokens = usage["prompt_tokens"]
                                if isinstance(usage.get("completion_tokens"), int):
                                    completion_tokens = usage["completion_tokens"]
                                if isinstance(usage.get("total_tokens"), int):
                                    total_tokens = usage["total_tokens"]

                            choices = parsed.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield {"type": "token", "text": delta}
                        except json.JSONDecodeError:
                            continue

            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens

            yield {
                "type": "done",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        except httpx.TimeoutException:
            yield {
                "type": "error",
                "error_category": "timeout",
                "error_message": f"{self.name} request timed out",
                "user_message": f"\n\n**Provider Timeout**: `{self.name}` timed out while generating a response.",
            }
        except Exception as e:
            logger.exception("Error in OpenAI-compatible stream_chat")
            yield {
                "type": "error",
                "error_category": "connection_error",
                "error_message": f"{self.name}: {str(e)[:180]}",
                "user_message": f"\n\n**Provider Connection Error**: Unable to reach `{self.name}`.",
            }

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        async for event in self.stream_chat_with_metrics(messages, model, temperature, context_window):
            if event["type"] == "token":
                yield event["text"]
            elif event["type"] == "error":
                yield event["user_message"]

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
