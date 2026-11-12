from typing import Dict, List
from backend.app.core.config import settings
from backend.app.services.ai.base import BaseAIProvider
from backend.app.services.ai.ollama import OllamaProvider
from backend.app.services.ai.openai_compatible import OpenAICompatibleProvider


class ProviderFactory:
    _providers: Dict[str, BaseAIProvider] = {}
    _api_keys: Dict[str, str] = {}
    _initialized_from_env: bool = False

    @classmethod
    def _ensure_env_keys_loaded(cls) -> None:
        if cls._initialized_from_env:
            return
        if settings.OPENAI_API_KEY and "openai" not in cls._api_keys:
            cls._api_keys["openai"] = settings.OPENAI_API_KEY
        if settings.GROQ_API_KEY and "groq" not in cls._api_keys:
            cls._api_keys["groq"] = settings.GROQ_API_KEY
        if settings.DEEPSEEK_API_KEY and "deepseek" not in cls._api_keys:
            cls._api_keys["deepseek"] = settings.DEEPSEEK_API_KEY
        if settings.PRODUCTION_INFERENCE_API_KEY and "production" not in cls._api_keys:
            cls._api_keys["production"] = settings.PRODUCTION_INFERENCE_API_KEY
        if (
            settings.PRODUCTION_INFERENCE_PROVIDER
            and settings.PRODUCTION_INFERENCE_API_KEY
            and settings.PRODUCTION_INFERENCE_PROVIDER.lower() not in cls._api_keys
        ):
            cls._api_keys[settings.PRODUCTION_INFERENCE_PROVIDER.lower()] = settings.PRODUCTION_INFERENCE_API_KEY
        cls._initialized_from_env = True

    @classmethod
    def get_configured_key_flags(cls) -> Dict[str, bool]:
        cls._ensure_env_keys_loaded()
        flags = {
            "ollama": True,
            "openai": bool(cls._api_keys.get("openai")),
            "groq": bool(cls._api_keys.get("groq")),
            "deepseek": bool(cls._api_keys.get("deepseek")),
        }
        if settings.PRODUCTION_INFERENCE_URL:
            flags["production"] = bool(cls._api_keys.get("production"))
        return flags

    @classmethod
    def register_provider(cls, name: str, provider: BaseAIProvider) -> None:
        cls._providers[name.lower()] = provider

    @classmethod
    def set_api_key(cls, provider_name: str, api_key: str) -> None:
        cls._ensure_env_keys_loaded()
        p_name = provider_name.lower()
        cls._api_keys[p_name] = api_key
        if p_name in cls._providers and isinstance(cls._providers[p_name], OpenAICompatibleProvider):
            cls._providers[p_name].api_key = api_key

    @classmethod
    def get_provider(cls, name: str = "ollama") -> BaseAIProvider:
        cls._ensure_env_keys_loaded()
        normalized = (name or "ollama").lower()
        if normalized not in cls._providers:
            if normalized == "ollama":
                cls._providers["ollama"] = OllamaProvider()
            elif normalized == "openai":
                cls._providers["openai"] = OpenAICompatibleProvider(
                    name="openai",
                    base_url="https://api.openai.com/v1",
                    api_key=cls._api_keys.get("openai", ""),
                )
            elif normalized == "groq":
                cls._providers["groq"] = OpenAICompatibleProvider(
                    name="groq",
                    base_url="https://api.groq.com/openai/v1",
                    api_key=cls._api_keys.get("groq", ""),
                )
            elif normalized == "deepseek":
                cls._providers["deepseek"] = OpenAICompatibleProvider(
                    name="deepseek",
                    base_url="https://api.deepseek.com/v1",
                    api_key=cls._api_keys.get("deepseek", ""),
                )
            elif normalized == "production" and settings.PRODUCTION_INFERENCE_URL:
                cls._providers["production"] = OpenAICompatibleProvider(
                    name="production",
                    base_url=settings.PRODUCTION_INFERENCE_URL.rstrip("/"),
                    api_key=cls._api_keys.get("production", ""),
                )
            else:
                return cls.get_provider("ollama")
        return cls._providers[normalized]

    @classmethod
    def list_all_providers(cls) -> List[BaseAIProvider]:
        cls._ensure_env_keys_loaded()
        names = ["ollama", "groq", "openai", "deepseek"]
        if settings.PRODUCTION_INFERENCE_URL:
            names.append("production")
        return [cls.get_provider(n) for n in names]


def get_ai_provider(provider_name: str = "ollama") -> BaseAIProvider:
    return ProviderFactory.get_provider(provider_name)
