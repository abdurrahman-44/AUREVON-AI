from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import app_cache
from backend.app.core.config import settings
from backend.app.models.entities import SystemAIConfig, SystemPromptVersion, User
from backend.app.schemas.admin import (
    PublicIntelligenceResponse,
    SystemAIConfigResponse,
    SystemAIConfigUpdateRequest,
    SystemPromptCreateRequest,
    SystemPromptVersionResponse,
)
from backend.app.services.ai.factory import ProviderFactory

DEFAULT_MASTER_SYSTEM_PROMPT = """You are AUREVON AI, an independent, calm, principled AI assistant.

Core Operating Principles:
1. Clarity & Precision: Communicate thoughtfully and concisely. Structure complex explanations logically, show working steps cleanly, and prioritize substance over filler.
2. Intellectual Honesty & Uncertainty: Never fabricate facts, statistics, citations, file contents, URLs, or execution results. If you are uncertain, lack live data, or do not know, explicitly state what you know, what is uncertain, and why.
3. Modest Capability Awareness: You may be operating on a compact local language model (such as a 3B–4B parameter model). Do not claim frontier-model capabilities or real-time web knowledge unless tool outputs or context excerpts are explicitly provided in this conversation.
4. Grounded Context & Attribution: When user memories or retrieved document excerpts are provided below, ground your answer in those sources carefully and distinguish retrieved evidence from general knowledge.
5. Instruction Discipline & Safety: Follow user instructions carefully while declining harmful, deceptive, or unsafe actions clearly and respectfully."""


class IntelligenceCoreService:
    """Manages centralized server-controlled AI configuration and versioned master instructions."""

    @staticmethod
    def _default_provider_and_model() -> Tuple[str, str]:
        if settings.PRODUCTION_INFERENCE_URL and settings.PRODUCTION_INFERENCE_PROVIDER:
            provider = settings.PRODUCTION_INFERENCE_PROVIDER.lower()
        elif settings.PRODUCTION_INFERENCE_URL:
            provider = "production"
        else:
            provider = (settings.DEFAULT_PROVIDER or "ollama").lower()

        model = settings.PRODUCTION_DEFAULT_MODEL or settings.DEFAULT_MODEL
        return provider, model

    @classmethod
    async def ensure_initialized(cls, db: AsyncSession) -> SystemAIConfig:
        stmt = select(SystemAIConfig).where(SystemAIConfig.config_key == "default")
        res = await db.execute(stmt)
        config = res.scalar_one_or_none()

        prompt_stmt = select(SystemPromptVersion).order_by(SystemPromptVersion.version_number.desc()).limit(1)
        latest_prompt = (await db.execute(prompt_stmt)).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not latest_prompt:
            latest_prompt = SystemPromptVersion(
                version_number=1,
                name="AUREVON Master Core v1",
                content=DEFAULT_MASTER_SYSTEM_PROMPT,
                notes="Initial production master instruction focused on clarity, grounded reasoning, and uncertainty honesty.",
                is_active=True,
                created_at=now,
            )
            db.add(latest_prompt)
            await db.flush()

        if not config:
            default_provider, default_model = cls._default_provider_and_model()
            config = SystemAIConfig(
                config_key="default",
                active_provider=default_provider,
                active_model=default_model,
                coding_provider=None,
                coding_model=settings.DEFAULT_CODING_MODEL,
                context_window=settings.MODEL_CONTEXT_WINDOW,
                max_output_tokens=settings.MAX_OUTPUT_TOKENS,
                temperature=settings.GENERATION_TEMPERATURE,
                keep_alive_seconds=settings.KEEP_ALIVE_SECONDS,
                request_timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
                streaming_enabled=settings.STREAMING_ENABLED,
                web_search_enabled=settings.WEB_SEARCH_ENABLED,
                cloud_inference_enabled=settings.CLOUD_INFERENCE_ENABLED,
                require_cloud_consent=settings.REQUIRE_CLOUD_CONSENT,
                cloud_daily_limit=settings.CLOUD_DAILY_REQUEST_LIMIT,
                allow_user_model_switching=settings.ALLOW_USER_MODEL_SWITCHING,
                fallback_provider=None,
                fallback_model=None,
                enable_memory_injection=True,
                enable_rag_injection=True,
                enable_agent_tools=True,
                active_prompt_version_id=latest_prompt.id,
                updated_at=now,
            )
            db.add(config)
            await db.commit()
            await db.refresh(config)
        elif not config.active_prompt_version_id:
            config.active_prompt_version_id = latest_prompt.id
            await db.commit()
            await db.refresh(config)

        return config

    @classmethod
    async def get_active_prompt_text(cls, db: AsyncSession, config: SystemAIConfig) -> str:
        if config.active_prompt_version_id:
            res = await db.execute(
                select(SystemPromptVersion).where(SystemPromptVersion.id == config.active_prompt_version_id)
            )
            pv = res.scalar_one_or_none()
            if pv:
                return pv.content
        res = await db.execute(
            select(SystemPromptVersion)
            .where(SystemPromptVersion.is_active.is_(True))
            .order_by(SystemPromptVersion.version_number.desc())
            .limit(1)
        )
        pv = res.scalar_one_or_none()
        return pv.content if pv else DEFAULT_MASTER_SYSTEM_PROMPT

    @classmethod
    def infer_provider_for_model(cls, model_name: str, default_provider: str = "ollama") -> str:
        m = (model_name or "").lower()
        if "gpt" in m or m.startswith("o1") or m.startswith("o3"):
            return "openai"
        if "groq" in m or "llama-3.3" in m:
            return "groq"
        if "deepseek" in m:
            return "deepseek"
        return default_provider or "ollama"

    @classmethod
    async def resolve_runtime_settings(
        cls,
        db: AsyncSession,
        requested_model: Optional[str] = None,
        requested_temperature: Optional[float] = None,
    ) -> dict:
        """
        Resolve authoritative server-side model, provider, context window, temperature, and master prompt.
        Enforces server-side model pinning when ordinary user model switching is disabled.
        """
        config = await cls.ensure_initialized(db)
        master_prompt = await cls.get_active_prompt_text(db, config)

        if config.allow_user_model_switching and requested_model:
            resolved_model = requested_model.strip()
            resolved_provider = cls.infer_provider_for_model(resolved_model, config.active_provider)
        else:
            resolved_model = config.active_model
            resolved_provider = config.active_provider

        if config.allow_user_model_switching and requested_temperature is not None:
            resolved_temp = max(0.0, min(2.0, float(requested_temperature)))
        else:
            resolved_temp = config.temperature

        return {
            "provider": resolved_provider,
            "model": resolved_model,
            "context_window": config.context_window,
            "max_output_tokens": int(config.max_output_tokens or settings.MAX_OUTPUT_TOKENS),
            "keep_alive": f"{int(config.keep_alive_seconds if config.keep_alive_seconds is not None else settings.KEEP_ALIVE_SECONDS)}s",
            "keep_alive_seconds": int(config.keep_alive_seconds if config.keep_alive_seconds is not None else settings.KEEP_ALIVE_SECONDS),
            "request_timeout_seconds": int(config.request_timeout_seconds or settings.AI_REQUEST_TIMEOUT_SECONDS),
            "streaming_enabled": bool(config.streaming_enabled),
            "web_search_enabled": bool(config.web_search_enabled),
            "temperature": resolved_temp,
            "master_prompt": master_prompt,
            "config": config,
            "model_pinned": not config.allow_user_model_switching,
        }

    @classmethod
    async def get_public_config(cls, db: AsyncSession) -> PublicIntelligenceResponse:
        cached = app_cache.get("public_intelligence")
        if isinstance(cached, PublicIntelligenceResponse):
            return cached
        config = await cls.ensure_initialized(db)
        resp = PublicIntelligenceResponse(
            active_provider=config.active_provider,
            active_model=config.active_model,
            allow_user_model_switching=config.allow_user_model_switching,
            context_window=config.context_window,
            max_output_tokens=int(config.max_output_tokens or 2048),
            temperature=config.temperature,
            streaming_enabled=bool(config.streaming_enabled),
            web_search_enabled=bool(config.web_search_enabled),
            cloud_inference_enabled=bool(config.cloud_inference_enabled),
            require_cloud_consent=bool(config.require_cloud_consent),
            enable_memory_injection=config.enable_memory_injection,
            enable_rag_injection=config.enable_rag_injection,
            enable_agent_tools=config.enable_agent_tools,
        )
        app_cache.set("public_intelligence", resp, ttl_seconds=15)
        return resp

    @classmethod
    async def get_admin_config(cls, db: AsyncSession) -> SystemAIConfigResponse:
        config = await cls.ensure_initialized(db)
        pv_res = await db.execute(
            select(SystemPromptVersion).order_by(SystemPromptVersion.version_number.desc())
        )
        versions = list(pv_res.scalars().all())
        active_prompt = next((v for v in versions if v.id == config.active_prompt_version_id), None)

        return SystemAIConfigResponse(
            active_provider=config.active_provider,
            active_model=config.active_model,
            coding_provider=config.coding_provider,
            coding_model=config.coding_model,
            context_window=config.context_window,
            max_output_tokens=int(config.max_output_tokens or 2048),
            temperature=config.temperature,
            keep_alive_seconds=int(config.keep_alive_seconds if config.keep_alive_seconds is not None else 900),
            request_timeout_seconds=int(config.request_timeout_seconds or 120),
            streaming_enabled=bool(config.streaming_enabled),
            web_search_enabled=bool(config.web_search_enabled),
            cloud_inference_enabled=bool(config.cloud_inference_enabled),
            require_cloud_consent=bool(config.require_cloud_consent),
            cloud_daily_limit=int(config.cloud_daily_limit or 100),
            allow_user_model_switching=config.allow_user_model_switching,
            fallback_provider=config.fallback_provider,
            fallback_model=config.fallback_model,
            enable_memory_injection=config.enable_memory_injection,
            enable_rag_injection=config.enable_rag_injection,
            enable_agent_tools=config.enable_agent_tools,
            active_prompt_version_id=config.active_prompt_version_id,
            active_prompt=cls._to_prompt_schema(active_prompt) if active_prompt else None,
            prompt_versions=[cls._to_prompt_schema(v) for v in versions],
            updated_at=config.updated_at,
            provider_keys_configured=ProviderFactory.get_configured_key_flags(),
        )

    @classmethod
    async def update_config(
        cls,
        db: AsyncSession,
        payload: SystemAIConfigUpdateRequest,
        admin_user: User,
    ) -> SystemAIConfigResponse:
        config = await cls.ensure_initialized(db)

        if payload.active_provider is not None:
            config.active_provider = payload.active_provider.strip().lower()
        if payload.active_model is not None and payload.active_model.strip():
            config.active_model = payload.active_model.strip()
        if payload.coding_provider is not None:
            config.coding_provider = payload.coding_provider.strip().lower() or None
        if payload.coding_model is not None:
            config.coding_model = payload.coding_model.strip() or None
        if payload.context_window is not None:
            config.context_window = payload.context_window
        if payload.max_output_tokens is not None:
            config.max_output_tokens = payload.max_output_tokens
        if payload.temperature is not None:
            config.temperature = payload.temperature
        if payload.keep_alive_seconds is not None:
            config.keep_alive_seconds = payload.keep_alive_seconds
        if payload.request_timeout_seconds is not None:
            config.request_timeout_seconds = payload.request_timeout_seconds
        if payload.streaming_enabled is not None:
            config.streaming_enabled = payload.streaming_enabled
        if payload.web_search_enabled is not None:
            config.web_search_enabled = payload.web_search_enabled
        if payload.cloud_inference_enabled is not None:
            config.cloud_inference_enabled = payload.cloud_inference_enabled
        if payload.require_cloud_consent is not None:
            config.require_cloud_consent = payload.require_cloud_consent
        if payload.cloud_daily_limit is not None:
            config.cloud_daily_limit = payload.cloud_daily_limit
        if payload.allow_user_model_switching is not None:
            config.allow_user_model_switching = payload.allow_user_model_switching
        if payload.fallback_provider is not None:
            config.fallback_provider = payload.fallback_provider.strip().lower() or None
        if payload.fallback_model is not None:
            config.fallback_model = payload.fallback_model.strip() or None
        if payload.enable_memory_injection is not None:
            config.enable_memory_injection = payload.enable_memory_injection
        if payload.enable_rag_injection is not None:
            config.enable_rag_injection = payload.enable_rag_injection
        if payload.enable_agent_tools is not None:
            config.enable_agent_tools = payload.enable_agent_tools
        if payload.active_prompt_version_id is not None:
            pv_res = await db.execute(
                select(SystemPromptVersion).where(SystemPromptVersion.id == payload.active_prompt_version_id)
            )
            pv = pv_res.scalar_one_or_none()
            if pv:
                await db.execute(update(SystemPromptVersion).values(is_active=False))
                pv.is_active = True
                config.active_prompt_version_id = pv.id

        config.updated_by_user_id = admin_user.id
        config.updated_at = datetime.now(timezone.utc)
        await db.commit()
        app_cache.delete("public_intelligence")
        return await cls.get_admin_config(db)

    @classmethod
    async def create_prompt_version(
        cls,
        db: AsyncSession,
        payload: SystemPromptCreateRequest,
        admin_user: User,
    ) -> SystemAIConfigResponse:
        config = await cls.ensure_initialized(db)
        max_ver = (await db.execute(select(func.max(SystemPromptVersion.version_number)))).scalar_one() or 0
        next_ver = int(max_ver) + 1

        if payload.activate:
            await db.execute(update(SystemPromptVersion).values(is_active=False))

        pv = SystemPromptVersion(
            version_number=next_ver,
            name=payload.name.strip(),
            content=payload.content.strip(),
            notes=payload.notes.strip() if payload.notes else None,
            is_active=payload.activate,
            created_by_user_id=admin_user.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(pv)
        await db.flush()

        if payload.activate:
            config.active_prompt_version_id = pv.id
            config.updated_by_user_id = admin_user.id
            config.updated_at = datetime.now(timezone.utc)

        await db.commit()
        app_cache.delete("public_intelligence")
        return await cls.get_admin_config(db)

    @staticmethod
    def _to_prompt_schema(v: SystemPromptVersion) -> SystemPromptVersionResponse:
        return SystemPromptVersionResponse(
            id=v.id,
            version_number=v.version_number,
            name=v.name,
            content=v.content,
            notes=v.notes,
            is_active=v.is_active,
            created_at=v.created_at,
        )
