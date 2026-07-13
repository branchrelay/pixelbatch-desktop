from __future__ import annotations

from threading import Event
from typing import Any

from .alibaba_provider import AlibabaProvider
from .base import ImageProvider, ProviderError
from .google_provider import GoogleProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider


class ProviderFactory:
    PROVIDERS: dict[str, type[ImageProvider]] = {
        "openrouter": OpenRouterProvider,
        "openai": OpenAIProvider,
        "google": GoogleProvider,
        "alibaba": AlibabaProvider,
    }

    @classmethod
    def create(
        cls,
        provider_id: str,
        settings: Any,
        cancel: Event | None = None,
        session: Any = None,
    ) -> ImageProvider:
        adapter = cls.PROVIDERS.get(provider_id)
        if adapter is None:
            raise ProviderError(f"Unsupported provider: {provider_id}", "invalid_request")
        config = settings.provider_config(provider_id) if hasattr(settings, "provider_config") else settings["providers"][provider_id]
        api_key = settings.api_key(provider_id) if hasattr(settings, "api_key") else settings.get("api_key", "")
        return adapter(config, api_key, cancel=cancel, session=session)

