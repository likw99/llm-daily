"""Any OpenAI-compatible chat completions API (OpenRouter, DeepSeek, Qwen, Ollama, GitHub Models, ...)."""

import logging
import os
from typing import Any, Optional

from .base import Completion, LLMRefusal, Usage

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """
    Calls an OpenAI-compatible `/chat/completions` endpoint.

    Configuration (environment):
        OPENAI_API_KEY   API key for the host
        OPENAI_BASE_URL  base URL, e.g. https://openrouter.ai/api/v1 or http://localhost:11434/v1
                         (omit for api.openai.com)
        LLMDAILY_MODEL   model name on that host (required)
    """

    name = "openai"

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self.model = model or os.environ.get("LLMDAILY_MODEL")
        if not self.model:
            raise ValueError(
                "The openai provider needs a model name. Set LLMDAILY_MODEL "
                "(for example deepseek-chat, qwen-plus or llama3.1) or pass --model."
            )

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "The openai provider needs the openai package. Run `uv sync --extra openai` "
                    "or `pip install 'llm-daily[openai]'`."
                ) from e
            client = OpenAI(
                base_url=base_url or os.environ.get("OPENAI_BASE_URL") or None,
                api_key=api_key or os.environ.get("OPENAI_API_KEY"),
                max_retries=4,
            )
        self.client = client

    def complete(self, system: str, user: str, max_tokens: int) -> Completion:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        if choice.finish_reason == "content_filter":
            raise LLMRefusal(self.name, "content_filter")
        if choice.finish_reason == "length":
            logger.warning("Response from %s hit max_tokens=%s and may be truncated", self.model, max_tokens)

        usage = Usage()
        if getattr(response, "usage", None):
            usage = Usage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
            )
        return Completion(
            text=choice.message.content or "",
            model=getattr(response, "model", None) or self.model,
            stop_reason=choice.finish_reason,
            usage=usage,
        )
