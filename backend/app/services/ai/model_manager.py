import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import app_cache
from backend.app.core.config import settings
from backend.app.models.entities import ProviderUsageLog, SystemAIConfig
from backend.app.services.ai.factory import ProviderFactory

logger = logging.getLogger("aurevon.ai.model_manager")

_CLOUD_PROVIDERS: Set[str] = {"openai", "gemini", "groq", "deepseek", "production"}

# Approximate USD per 1M tokens for optional cloud cost awareness (0.0 for local Ollama)
_COST_PER_1M_USD: Dict[str, Tuple[float, float]] = {
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}


class ModelManager:
    """Centralized local-first model discovery, load-serialization, warm keep-alive, and cloud governance."""

    _model_load_lock = asyncio.Lock()
    _last_loaded_key: Optional[str] = None
    _last_loaded_at: float = 0.0

    @classmethod
    def is_cloud_provider(cls, provider_name: str) -> bool:
        return (provider_name or "ollama").strip().lower() in _CLOUD_PROVIDERS

    @classmethod
    def estimate_cost_usd(cls, provider: str, model: str, prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> float:
        if not cls.is_cloud_provider(provider):
            return 0.0
        pt = prompt_tokens or 0
        ct = completion_tokens or 0
        m_low = (model or "").lower()
        in_rate, out_rate = (0.50, 1.50)
        for prefix, rates in _COST_PER_1M_USD.items():
            if prefix in m_low:
                in_rate, out_rate = rates
                break
        return round(((pt / 1_000_000) * in_rate) + ((ct / 1_000_000) * out_rate), 6)

    @classmethod
    async def fetch_ollama_runtime_state(cls, force_refresh: bool = False) -> Dict[str, Any]:
        """Discover installed Ollama models (/api/tags) and active loaded models in RAM (/api/ps)."""
        if not force_refresh:
            cached = app_cache.get("ollama_runtime_state")
            if isinstance(cached, dict):
                return cached

        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        state: Dict[str, Any] = {
            "reachable": False,
            "base_url": base_url,
            "installed_models": [],
            "loaded_models": [],
            "installed_names": set(),
            "loaded_names": set(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                tags_res, ps_res = await asyncio.gather(
                    client.get(f"{base_url}/api/tags"),
                    client.get(f"{base_url}/api/ps"),
                    return_exceptions=True,
                )

            if not isinstance(tags_res, Exception) and tags_res.status_code == 200:
                state["reachable"] = True
                raw_models = tags_res.json().get("models", []) or []
                installed = []
                names = set()
                for m in raw_models:
                    name = m.get("name", "")
                    if not name:
                        continue
                    names.add(name)
                    details = m.get("details", {}) or {}
                    size_bytes = int(m.get("size", 0) or 0)
                    installed.append(
                        {
                            "id": name,
                            "name": name,
                            "provider": "ollama",
                            "size_bytes": size_bytes,
                            "size_gb": round(size_bytes / (1024 ** 3), 2),
                            "parameter_size": details.get("parameter_size", "unknown"),
                            "quantization": details.get("quantization_level", "unknown"),
                            "family": details.get("family", "unknown"),
                            "modified_at": m.get("modified_at"),
                            "is_coding_specialist": "coder" in name.lower() or "code" in name.lower(),
                        }
                    )
                state["installed_models"] = installed
                state["installed_names"] = names

            if not isinstance(ps_res, Exception) and ps_res.status_code == 200:
                raw_loaded = ps_res.json().get("models", []) or []
                loaded = []
                loaded_names = set()
                for m in raw_loaded:
                    name = m.get("name", "")
                    if name:
                        loaded_names.add(name)
                    size_vram = int(m.get("size_vram", 0) or 0)
                    size_total = int(m.get("size", 0) or 0)
                    loaded.append(
                        {
                            "name": name,
                            "size_mb": round(size_total / (1024 * 1024), 1),
                            "vram_mb": round(size_vram / (1024 * 1024), 1),
                            "expires_at": m.get("expires_at"),
                            "context_length": m.get("context_length"),
                        }
                    )
                state["loaded_models"] = loaded
                state["loaded_names"] = loaded_names
                if loaded_names:
                    cls._last_loaded_key = f"ollama:{next(iter(loaded_names))}"
        except Exception as exc:
            state["error"] = str(exc)

        app_cache.set("ollama_runtime_state", state, ttl_seconds=6)
        return state

    @classmethod
    async def list_discovered_models(cls, config: SystemAIConfig) -> Dict[str, Any]:
        """Return rich model catalog with status (loaded/ready/offline), active roles, and cloud availability."""
        ollama_state = await cls.fetch_ollama_runtime_state(force_refresh=True)
        loaded_set: Set[str] = ollama_state.get("loaded_names", set())
        installed_list: List[Dict[str, Any]] = []

        for m in ollama_state.get("installed_models", []):
            name = m["id"]
            installed_list.append(
                {
                    **m,
                    "status": "loaded" if name in loaded_set else "ready",
                    "is_default": (config.active_provider == "ollama" and config.active_model == name),
                    "is_coding_default": (config.coding_model == name),
                    "is_fallback": (config.fallback_provider == "ollama" and config.fallback_model == name),
                    "available": True,
                }
            )

        cloud_catalog: List[Dict[str, Any]] = []
        key_flags = ProviderFactory.get_configured_key_flags()
        for p_name in ("openai", "gemini", "groq", "deepseek", "production"):
            if p_name not in key_flags:
                continue
            cloud_catalog.append(
                {
                    "provider": p_name,
                    "key_configured": bool(key_flags.get(p_name)),
                    "cloud_enabled": bool(config.cloud_inference_enabled),
                    "require_consent": bool(config.require_cloud_consent),
                    "daily_limit": int(config.cloud_daily_limit or 100),
                }
            )

        return {
            "ollama_reachable": bool(ollama_state.get("reachable")),
            "ollama_url": ollama_state.get("base_url"),
            "active_provider": config.active_provider,
            "active_model": config.active_model,
            "coding_provider": config.coding_provider,
            "coding_model": config.coding_model,
            "fallback_provider": config.fallback_provider,
            "fallback_model": config.fallback_model,
            "context_window": config.context_window,
            "max_output_tokens": config.max_output_tokens,
            "keep_alive_seconds": config.keep_alive_seconds,
            "request_timeout_seconds": config.request_timeout_seconds,
            "streaming_enabled": config.streaming_enabled,
            "installed_local_models": installed_list,
            "loaded_models": ollama_state.get("loaded_models", []),
            "cloud_providers": cloud_catalog,
            "checked_at": ollama_state.get("checked_at"),
        }

    @classmethod
    async def check_model_available(cls, provider: str, model: str) -> Tuple[bool, str]:
        p = (provider or "ollama").strip().lower()
        if p == "ollama":
            state = await cls.fetch_ollama_runtime_state()
            if not state["reachable"]:
                return False, f"Ollama daemon at {state['base_url']} is unreachable"
            installed: Set[str] = state.get("installed_names", set())
            if installed and model not in installed:
                return False, f"Model '{model}' is not installed in Ollama (installed: {', '.join(sorted(installed))})"
            return True, "ready"

        key_flags = ProviderFactory.get_configured_key_flags()
        if not key_flags.get(p):
            return False, f"Cloud provider '{p}' does not have an API key configured"
        return True, "configured"

    @classmethod
    async def warm_model_if_needed(
        cls,
        provider: str,
        model: str,
        context_window: int,
        keep_alive_seconds: int,
    ) -> None:
        """
        Serialize cold-model loads in Ollama so concurrent requests do not trigger RAM thrashing.
        Skips locking entirely if the target (provider, model, context_window) is already warm.
        """
        p = (provider or "ollama").lower()
        if p != "ollama":
            return

        target_key = f"{p}:{model}:{context_window}"
        now_mono = time.monotonic()
        # Fast path: same warm target recently used
        if cls._last_loaded_key == target_key and (now_mono - cls._last_loaded_at) < max(30, keep_alive_seconds - 10):
            return

        async with cls._model_load_lock:
            now_mono = time.monotonic()
            if cls._last_loaded_key == target_key and (now_mono - cls._last_loaded_at) < max(30, keep_alive_seconds - 10):
                return
            state = await cls.fetch_ollama_runtime_state()
            if not state["reachable"]:
                return
            loaded_names: Set[str] = state.get("loaded_names", set())
            if model in loaded_names and cls._last_loaded_key == target_key:
                cls._last_loaded_at = now_mono
                return

            # Mark transition; Ollama /api/chat will load cleanly under this lock window when needed
            cls._last_loaded_key = target_key
            cls._last_loaded_at = now_mono
            app_cache.delete("ollama_runtime_state")

    @classmethod
    async def test_model_connectivity(
        cls,
        provider: str,
        model: str,
        context_window: int = 8192,
        keep_alive_seconds: int = 900,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        p_name = (provider or "ollama").lower()
        if p_name == "ollama":
            ok, msg = await cls.check_model_available("ollama", model)
            if not ok:
                return {
                    "provider": p_name,
                    "model": model,
                    "success": False,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "error": msg,
                }
        provider_inst = ProviderFactory.get_provider(p_name)
        preview = ""
        err = None
        usage: Dict[str, Any] = {}
        try:
            async for ev in provider_inst.stream_chat_with_metrics(
                messages=[{"role": "user", "content": "Reply with OK."}],
                model=model,
                temperature=0.1,
                context_window=context_window,
            ):
                if ev["type"] == "token":
                    preview += ev["text"]
                elif ev["type"] == "done":
                    usage = ev
                elif ev["type"] == "error":
                    err = ev.get("error_message")
            latency = int((time.perf_counter() - started) * 1000)
            if not err and preview.strip():
                cls._last_loaded_key = f"{p_name}:{model}:{context_window}"
                cls._last_loaded_at = time.monotonic()
                app_cache.delete("ollama_runtime_state")
            return {
                "provider": p_name,
                "model": model,
                "success": err is None and bool(preview.strip()),
                "latency_ms": latency,
                "response_preview": preview.strip()[:120] or None,
                "error": err,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
        except Exception as exc:
            return {
                "provider": p_name,
                "model": model,
                "success": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": str(exc)[:200],
            }

    @classmethod
    async def select_route_model(
        cls,
        config: SystemAIConfig,
        resolved_provider: str,
        resolved_model: str,
        intent: str,
        allow_cloud: bool,
        db: AsyncSession,
        user_id: Optional[str] = None,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Choose appropriate provider/model based on intent, installed availability, and cloud consent policy.
        Returns (provider, model, note).
        """
        provider = (resolved_provider or "ollama").lower()
        model = resolved_model or settings.DEFAULT_MODEL
        note: Optional[str] = None

        # Optional programming specialist model only if explicitly configured AND verified installed
        if intent == "programming" and config.coding_model:
            c_provider = (config.coding_provider or provider).lower()
            if c_provider == "ollama":
                state = await cls.fetch_ollama_runtime_state()
                if state["reachable"] and config.coding_model in state.get("installed_names", set()):
                    provider, model = c_provider, config.coding_model
                    note = f"specialist:coding:{model}"

        # Cloud consent & daily limit guard
        if cls.is_cloud_provider(provider):
            if not config.cloud_inference_enabled:
                provider = "ollama"
                model = config.fallback_model if (config.fallback_provider == "ollama" and config.fallback_model) else settings.DEFAULT_MODEL
                note = "cloud_disabled_using_local"
            elif config.require_cloud_consent and not allow_cloud:
                provider = "ollama"
                model = config.fallback_model if (config.fallback_provider == "ollama" and config.fallback_model) else settings.DEFAULT_MODEL
                note = "cloud_consent_required_using_local"
            else:
                since = datetime.now(timezone.utc) - timedelta(hours=24)
                today_cloud_count = int(
                    (
                        await db.execute(
                            select(func.count(ProviderUsageLog.id)).where(
                                ProviderUsageLog.is_cloud == True,
                                ProviderUsageLog.created_at >= since,
                            )
                        )
                    ).scalar()
                    or 0
                )
                if today_cloud_count >= int(config.cloud_daily_limit or 100):
                    provider = "ollama"
                    model = config.fallback_model if (config.fallback_provider == "ollama" and config.fallback_model) else settings.DEFAULT_MODEL
                    note = "cloud_daily_limit_exceeded_using_local"

        return provider, model, note

    @classmethod
    async def record_provider_usage(
        cls,
        db: AsyncSession,
        provider: str,
        model: str,
        user_id: Optional[str],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
        consent_granted: bool,
        success: bool,
        latency_ms: int,
    ) -> None:
        is_cloud = cls.is_cloud_provider(provider)
        cost = cls.estimate_cost_usd(provider, model, prompt_tokens, completion_tokens)
        entry = ProviderUsageLog(
            provider=provider,
            model=model,
            user_id=user_id,
            is_cloud=is_cloud,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            consent_granted=consent_granted,
            success=success,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.commit()
