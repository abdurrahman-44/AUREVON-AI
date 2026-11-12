from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import app_cache
from backend.app.core.config import settings
from backend.app.models.entities import PlatformConfig

_PLATFORM_CACHE_KEY = "platform_config_snapshot"


class PlatformSettingsService:
    """Manages runtime platform configuration (maintenance mode, signup policy, rate limits, retention)."""

    @classmethod
    async def ensure_initialized(cls, db: AsyncSession) -> PlatformConfig:
        res = await db.execute(select(PlatformConfig).where(PlatformConfig.config_key == "default"))
        cfg = res.scalar_one_or_none()
        if not cfg:
            cfg = PlatformConfig(
                config_key="default",
                app_display_name=settings.APP_NAME,
                maintenance_mode=False,
                maintenance_message="AUREVON AI is currently undergoing scheduled maintenance. Please check back shortly.",
                allow_public_registration=True,
                log_retention_days=settings.LOG_RETENTION_DAYS_DEFAULT,
                auth_rate_limit_per_min=settings.RATE_LIMIT_AUTH_PER_MINUTE,
                chat_rate_limit_per_min=settings.RATE_LIMIT_CHAT_PER_MINUTE,
                upload_rate_limit_per_min=settings.RATE_LIMIT_UPLOAD_PER_MINUTE,
                enable_api_request_logging=True,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(cfg)
            await db.commit()
            await db.refresh(cfg)
        return cfg

    @classmethod
    def to_dict(cls, cfg: PlatformConfig) -> Dict:
        return {
            "app_display_name": cfg.app_display_name,
            "maintenance_mode": cfg.maintenance_mode,
            "maintenance_message": cfg.maintenance_message,
            "allow_public_registration": cfg.allow_public_registration,
            "log_retention_days": cfg.log_retention_days,
            "auth_rate_limit_per_min": cfg.auth_rate_limit_per_min,
            "chat_rate_limit_per_min": cfg.chat_rate_limit_per_min,
            "upload_rate_limit_per_min": cfg.upload_rate_limit_per_min,
            "enable_api_request_logging": cfg.enable_api_request_logging,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }

    @classmethod
    async def get_snapshot(cls, db: AsyncSession) -> Dict:
        cached = app_cache.get(_PLATFORM_CACHE_KEY)
        if isinstance(cached, dict):
            return cached
        cfg = await cls.ensure_initialized(db)
        snap = cls.to_dict(cfg)
        app_cache.set(_PLATFORM_CACHE_KEY, snap, ttl_seconds=15)
        return snap

    @classmethod
    def invalidate_cache(cls) -> None:
        app_cache.delete(_PLATFORM_CACHE_KEY)

    @classmethod
    async def update_settings(
        cls,
        db: AsyncSession,
        *,
        actor_user_id: str,
        app_display_name: Optional[str] = None,
        maintenance_mode: Optional[bool] = None,
        maintenance_message: Optional[str] = None,
        allow_public_registration: Optional[bool] = None,
        log_retention_days: Optional[int] = None,
        auth_rate_limit_per_min: Optional[int] = None,
        chat_rate_limit_per_min: Optional[int] = None,
        upload_rate_limit_per_min: Optional[int] = None,
        enable_api_request_logging: Optional[bool] = None,
    ) -> PlatformConfig:
        cfg = await cls.ensure_initialized(db)

        if app_display_name is not None and app_display_name.strip():
            cfg.app_display_name = app_display_name.strip()[:128]
        if maintenance_mode is not None:
            cfg.maintenance_mode = bool(maintenance_mode)
        if maintenance_message is not None and maintenance_message.strip():
            cfg.maintenance_message = maintenance_message.strip()[:255]
        if allow_public_registration is not None:
            cfg.allow_public_registration = bool(allow_public_registration)
        if log_retention_days is not None:
            cfg.log_retention_days = max(1, min(365, int(log_retention_days)))
        if auth_rate_limit_per_min is not None:
            cfg.auth_rate_limit_per_min = max(1, min(600, int(auth_rate_limit_per_min)))
            settings.RATE_LIMIT_AUTH_PER_MINUTE = cfg.auth_rate_limit_per_min
        if chat_rate_limit_per_min is not None:
            cfg.chat_rate_limit_per_min = max(1, min(600, int(chat_rate_limit_per_min)))
            settings.RATE_LIMIT_CHAT_PER_MINUTE = cfg.chat_rate_limit_per_min
        if upload_rate_limit_per_min is not None:
            cfg.upload_rate_limit_per_min = max(1, min(300, int(upload_rate_limit_per_min)))
            settings.RATE_LIMIT_UPLOAD_PER_MINUTE = cfg.upload_rate_limit_per_min
        if enable_api_request_logging is not None:
            cfg.enable_api_request_logging = bool(enable_api_request_logging)

        cfg.updated_by_user_id = actor_user_id
        cfg.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(cfg)
        cls.invalidate_cache()
        return cfg
