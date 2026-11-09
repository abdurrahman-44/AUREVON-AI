from typing import Dict, List, Optional
from backend.app.services.ai.base import BaseAIProvider
from backend.app.services.ai.ollama import OllamaProvider
from backend.app.services.ai.openai_compatible import OpenAICompatibleProvider
from backend.app.schemas.model import ModelInfo, ProviderHealth


class ProviderFactory:
    _providers: Dict[str, BaseAIProvider] = {}
    _api_keys: Dict[str, str] = {}

    @classmethod
    def register_provider(cls, name: str, provider: BaseAIProvider) -> None:
        cls._providers[name.lower()] = provider

    @classmethod
    def set_api_key(cls, provider_name: str, api_key: str) -> None:
        p_name = provider_name.lower()
        cls._api_keys[p_name] = api_key
        # Refresh instance if cloud provider
        if p_name in cls._providers and isinstance(cls._providers[p_name], OpenAICompatibleProvider):
            cls._providers[p_name].api_key = api_key

    @classmethod
    def get_provider(cls, name: str = "ollama") -> BaseAIProvider:
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
            else:
                # Default to Ollama fallback
                return cls.get_provider("ollama")
        return cls._providers[normalized]

    @classmethod
    def list_all_providers(cls) -> List[BaseAIProvider]:
        names = ["ollama", "groq", "openai", "deepseek"]
        return [cls.get_provider(n) for n in names]


def get_ai_provider(provider_name: str = "ollama") -> BaseAIProvider:
    return ProviderFactory.get_provider(provider_name)
