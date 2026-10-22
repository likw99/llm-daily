"""Provider-neutral types for LLM calls."""

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Completion:
    text: str
    model: str
    stop_reason: Optional[str] = None
    usage: Usage = field(default_factory=Usage)


class LLMRefusal(Exception):
    """Raised when the model declines to answer (for example a safety refusal)."""

    def __init__(self, provider: str, category: Optional[str] = None):
        self.provider = provider
        self.category = category
        detail = f" (category: {category})" if category else ""
        super().__init__(f"{provider} model declined the request{detail}")


class LLMProvider(Protocol):
    """Anything that can turn a system prompt and a user message into text."""

    name: str
    model: str

    def complete(self, system: str, user: str, max_tokens: int) -> Completion: ...
