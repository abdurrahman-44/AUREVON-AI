from typing import Dict, Type
from backend.app.services.ai.base import BaseAIProvider
from backend.app.services.ai.ollama import OllamaProvider


class ProviderFactory:
    _providers: Dict[str, BaseAIProvider] = {}

    @classmethod
    def get_provider(cls, name: str = "ollama") -> BaseAIProvider:
        normalized = (name or "ollama").lower()
        if normalized not in cls._providers:
            if normalized == "ollama":
                cls._providers["ollama"] = OllamaProvider()
            else:
                raise ValueError(f"Provider '{name}' is not currently configured or supported.")
        return cls._providers[normalized]


def get_ai_provider(provider_name: str = "ollama") -> BaseAIProvider:
    return ProviderFactory.get_provider(provider_name)
