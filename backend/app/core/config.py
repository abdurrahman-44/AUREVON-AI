import json
import os
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator


class Settings(BaseSettings):
    APP_NAME: str = "AUREVON AI"
    APP_VERSION: str = "2.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    ENABLE_DOCS: bool = True

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in stripped.split(",") if i.strip()]
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./aurevon.db"

    # AI Provider & Intelligence Core defaults
    DEFAULT_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    DEFAULT_MODEL: str = "qwen2.5:3b"
    MODEL_CONTEXT_WINDOW: int = 8192
    GENERATION_TEMPERATURE: float = 0.7
    PIN_DEFAULT_MODEL: bool = True
    ALLOW_USER_MODEL_SWITCHING: bool = False

    # Optional Cloud / Hosted Inference Provider (used when configured for production or admin override)
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    PRODUCTION_INFERENCE_PROVIDER: Optional[str] = None
    PRODUCTION_INFERENCE_URL: Optional[str] = None
    PRODUCTION_INFERENCE_API_KEY: Optional[str] = None
    PRODUCTION_DEFAULT_MODEL: Optional[str] = None

    # Security & Owner Bootstrap
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production-12345",
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"),
    )
    ADMIN_BOOTSTRAP_TOKEN: Optional[str] = None
    OWNER_USERNAME: Optional[str] = None
    OWNER_EMAIL: Optional[str] = None
    OWNER_PASSWORD: Optional[str] = None
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25

    # Rate Limiting (requests per minute) & Session/Log Policies
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30
    RATE_LIMIT_AUTH_PER_MINUTE: int = 15
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
    RATE_LIMIT_ADMIN_TERMINAL_PER_MINUTE: int = 30
    ADMIN_SESSION_EXPIRE_MINUTES: int = 720
    LOG_RETENTION_DAYS_DEFAULT: int = 30

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
