"""Claude via the official Anthropic SDK."""

import logging
import os
from typing import Any, Optional

import anthropic

from .base import Completion, LLMRefusal, Usage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
STREAM_ABOVE_TOKENS = 16000

# Models that accept the server-side `fallbacks: "default"` parameter on the Claude API.
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class AnthropicProvider:
    """
    Calls Claude through the Messages API.

    Configuration (environment, all optional except the key):
        ANTHROPIC_API_KEY   API key (read by the SDK)
        LLMDAILY_MODEL      model ID, default claude-sonnet-5-5
        LLMDAILY_EFFORT     low | medium | high | xhigh | max, default medium
        LLMDAILY_FALLBACKS  set to "off" to disable server-side refusal fallbacks
    """

    name = "anthropic"

    def __init__(
        self,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        client: Optional[Any] = None,
        fallbacks: Optional[bool] = None,
    ):
        self.model = model or os.environ.get("LLMDAILY_MODEL") or DEFAULT_MODEL
        self.effort = effort or os.environ.get("LLMDAILY_EFFORT") or DEFAULT_EFFORT
        if fallbacks is None:
            fallbacks = os.environ.get("LLMDAILY_FALLBACKS", "").lower() != "off"
        self.use_fallbacks = fallbacks and self.model in FALLBACK_MODELS
        # The SDK retries 408/409/429/5xx and connection errors with exponential backoff.
        self.client = client or anthropic.Anthropic(max_retries=4)

    def complete(self, system: str, user: str, max_tokens: int) -> Completion:
        kwargs: dict = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "output_config": {"effort": self.effort},
        }
        if self.use_fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"

        if max_tokens > STREAM_ABOVE_TOKENS:
            # The SDK rejects long non-streaming requests; stream and collect the final message.
            with self.client.beta.messages.stream(**kwargs) as stream:
                response = stream.get_final_message()
        else:
            response = self.client.beta.messages.create(**kwargs)

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusal(self.name, getattr(details, "category", None))

        # Thinking and fallback blocks can precede the answer, so join every text block.
        text = "".join(block.text for block in response.content if block.type == "text")

        if response.stop_reason == "max_tokens":
            logger.warning("Response from %s hit max_tokens=%s and may be truncated", self.model, max_tokens)

        usage = Usage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )
        return Completion(text=text, model=response.model, stop_reason=response.stop_reason, usage=usage)
