from types import SimpleNamespace

import pytest

from llm_daily.llm import LLMRefusal
from llm_daily.llm.openai_provider import OpenAICompatibleProvider


class FakeCompletions:
    def __init__(self, finish_reason="stop", content="# RESEARCH\n- paper"):
        self.finish_reason = finish_reason
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[SimpleNamespace(
                finish_reason=self.finish_reason,
                message=SimpleNamespace(content=self.content),
            )],
            usage=SimpleNamespace(prompt_tokens=30, completion_tokens=12),
        )


def make_client(**kwargs):
    completions = FakeCompletions(**kwargs)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_requires_model():
    with pytest.raises(ValueError, match="LLMDAILY_MODEL"):
        OpenAICompatibleProvider(client=object())


def test_complete_maps_response():
    client, completions = make_client()
    provider = OpenAICompatibleProvider(model="deepseek-chat", client=client)
    completion = provider.complete("system prompt", "hello", 2000)

    assert completion.text == "# RESEARCH\n- paper"
    assert completion.usage.input_tokens == 30
    assert completion.usage.output_tokens == 12
    assert completions.kwargs["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]
    assert completions.kwargs["max_tokens"] == 2000


def test_content_filter_raises():
    client, _ = make_client(finish_reason="content_filter", content="")
    with pytest.raises(LLMRefusal):
        OpenAICompatibleProvider(model="m", client=client).complete("s", "u", 10)


def test_real_client_honours_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    provider = OpenAICompatibleProvider(model="llama3.1")
    assert str(provider.client.base_url).startswith("http://localhost:11434/v1")
