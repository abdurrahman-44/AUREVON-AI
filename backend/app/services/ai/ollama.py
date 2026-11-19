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
                                is_default=(name == settings.DEFAULT_MODEL),
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
        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": context_window or settings.MODEL_CONTEXT_WINDOW,
        }
        if max_tokens and max_tokens > 0:
            options["num_predict"] = int(max_tokens)

        payload: Dict[str, Any] = {
            "model": model or settings.DEFAULT_MODEL,
            "messages": messages,
            "stream": True,
            "keep_alive": keep_alive or settings.MODEL_KEEP_ALIVE,
            "options": options,
        }

        timeout_cfg = (
            httpx.Timeout(connect=1.5, read=float(request_timeout), write=5.0, pool=5.0)
            if request_timeout and request_timeout > 0
            else self.timeout
        )

        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None

        try:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        err_raw = await response.aread()
                        err_decoded = err_raw.decode("utf-8", errors="ignore")
                        logger.error(f"Ollama stream error status {response.status_code}: {err_decoded}")
                        user_msg = (
                            f"**Provider Error (HTTP {response.status_code})**: Ollama returned an error: "
                            f"`{err_decoded}`.\n\n*Make sure the model `{payload['model']}` is available in Ollama.*"
                        )
                        yield {
                            "type": "error",
                            "error_category": f"http_{response.status_code}",
                            "error_message": f"Ollama HTTP {response.status_code}: {err_decoded[:180]}",
                            "user_message": user_msg,
                        }
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk_data = json.loads(line)
                            if chunk_data.get("error"):
                                err_str = str(chunk_data["error"])
                                yield {
                                    "type": "error",
                                    "error_category": "provider_stream_error",
                                    "error_message": err_str[:200],
                                    "user_message": f"**Provider Error**: {err_str}",
                                }
                                return

                            message_obj = chunk_data.get("message", {})
                            content_piece = message_obj.get("content", "")
                            if content_piece:
                                yield {"type": "token", "text": content_piece}

                            if chunk_data.get("done", False):
                                raw_prompt = chunk_data.get("prompt_eval_count")
                                raw_eval = chunk_data.get("eval_count")
                                prompt_tokens = int(raw_prompt) if isinstance(raw_prompt, int) else None
                                completion_tokens = int(raw_eval) if isinstance(raw_eval, int) else None
                                break
                        except json.JSONDecodeError:
                            continue

            total_tokens = (
                (prompt_tokens + completion_tokens)
                if (prompt_tokens is not None and completion_tokens is not None)
                else None
            )
            yield {
                "type": "done",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning(f"Ollama connection refused at {self.base_url}: {e}")
            guidance = (
                f"### Local Ollama Runtime Unavailable\n\n"
                f"AUREVON AI could not connect to Ollama at `{self.base_url}`.\n\n"
                f"Start Ollama locally (for example `ollama run {payload['model']}`) or configure a reachable provider in `/admin`."
            )
            yield {
                "type": "error",
                "error_category": "connection_unavailable",
                "error_message": f"Ollama unreachable at {self.base_url}",
                "user_message": guidance,
            }
        except httpx.TimeoutException as e:
            logger.error(f"Ollama request timed out: {e}")
            yield {
                "type": "error",
                "error_category": "timeout",
                "error_message": "Ollama request timed out",
                "user_message": "\n\n**Provider Timeout**: The local AI runtime took too long to respond.",
            }
        except Exception as e:
            logger.exception("Unexpected error in Ollama stream_chat")
            yield {
                "type": "error",
                "error_category": "unexpected_provider_error",
                "error_message": str(e)[:200],
                "user_message": f"\n\n**System Error**: Unable to complete generation (`{str(e)}`).",
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
        accumulated = []
        async for chunk in self.stream_chat(messages, model, temperature, context_window):
            accumulated.append(chunk)
        return "".join(accumulated)
