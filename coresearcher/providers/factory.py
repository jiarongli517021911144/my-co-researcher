from __future__ import annotations

from coresearcher.config.schema import Config
from coresearcher.providers.registry import find_by_name


def create_provider(config: Config, provider_name: str | None = None, model: str | None = None):
    name, provider_config = config.providers.resolve(provider_name)
    resolved_model = model or provider_config.model or config.providers.default_model

    if name in {"openai_codex", "codex"}:
        from coresearcher.providers.openai_codex_provider import OpenAICodexProvider

        return OpenAICodexProvider(default_model=resolved_model)

    if name == "mock":
        from coresearcher.providers.mock_provider import MockProvider

        return MockProvider(default_model=resolved_model)

    if name == "custom":
        from coresearcher.providers.custom_provider import CustomProvider

        return CustomProvider(
            api_key=provider_config.api_key or "no-key",
            api_base=provider_config.api_base or "http://localhost:8000/v1",
            default_model=resolved_model,
        )

    from coresearcher.providers.litellm_provider import LiteLLMProvider

    spec = find_by_name(name)
    return LiteLLMProvider(
        api_key=provider_config.api_key,
        api_base=provider_config.api_base or (spec.default_api_base if spec else None),
        default_model=resolved_model,
        extra_headers=provider_config.extra_headers,
        provider_name=name,
    )
