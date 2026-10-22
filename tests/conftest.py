import pytest

from llm_daily.llm import Completion, Usage

PROVIDER_ENV = [
    "LLMDAILY_PROVIDER", "LLMDAILY_MODEL", "LLMDAILY_EFFORT", "LLMDAILY_FALLBACKS",
    "LLMDAILY_SOURCES", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "X_LIST_ID",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Keep the developer's real keys and settings out of every test."""
    for var in PROVIDER_ENV:
        monkeypatch.delenv(var, raising=False)


class FakeProvider:
    """Records calls and answers with the section header the prompt asks for."""

    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def complete(self, system, user, max_tokens):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        for header in ("BUSINESS", "PRODUCTS", "TECHNOLOGY", "RESEARCH", "HIGHLIGHTS", "LOOKING AHEAD"):
            if f'"# {header}"' in system or f"# {header}" in system:
                if header == "HIGHLIGHTS":
                    text = "# HIGHLIGHTS\n\n• A highlight"
                else:
                    slug = header.lower().replace(" ", "-")
                    text = f"# {header}\n\n- **[Item for {slug}](https://example.com/{slug})** (2026-10-21) – summary"
                break
        else:
            text = "# UNKNOWN"
        return Completion(text=text, model=self.model, stop_reason="end_turn", usage=Usage(10, 5))


@pytest.fixture
def fake_provider():
    return FakeProvider()
