"""Pick an LLM provider from arguments or the environment."""

import os
from typing import Optional

from .base import LLMProvider

PROVIDERS = ("anthropic", "openai")


def get_provider(name: Optional[str] = None, model: Optional[str] = None) -> LLMProvider:
    """
    Return the configured provider.

    Selection order: the ``name`` argument, ``LLMDAILY_PROVIDER``, then ``openai`` if only
    ``OPENAI_API_KEY`` is set, otherwise ``anthropic``.
    """
    chosen = (name or os.environ.get("LLMDAILY_PROVIDER") or "").strip().lower()
    if not chosen:
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        chosen = "openai" if has_openai and not has_anthropic else "anthropic"

    if chosen == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model)
    if chosen == "openai":
        from .openai_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider(model=model)

    raise ValueError(f"Unknown LLM provider '{chosen}'. Choose one of: {', '.join(PROVIDERS)}")
