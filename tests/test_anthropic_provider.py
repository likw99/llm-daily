from types import SimpleNamespace

import pytest

from llm_daily.llm import LLMRefusal
from llm_daily.llm.anthropic_provider import AnthropicProvider


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def make_client(content, stop_reason="end_turn", stop_details=None, model="claude-sonnet-5-5"):
    response = SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        stop_details=stop_details,
        model=model,
        usage=SimpleNamespace(input_tokens=120, output_tokens=45),
    )
    messages = FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_joins_text_blocks_after_thinking():
    client, _ = make_client([
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="# BUSINESS\n"),
        SimpleNamespace(type="text", text="- item"),
    ])
    completion = AnthropicProvider(client=client).complete("sys", "user", 16000)
    assert completion.text == "# BUSINESS\n- item"
    assert completion.usage.input_tokens == 120
    assert completion.usage.output_tokens == 45


def test_request_shape():
    client, messages = make_client([SimpleNamespace(type="text", text="ok")])
    AnthropicProvider(client=client, effort="low").complete("system prompt", "hello", 900)
    kwargs = messages.kwargs
    assert kwargs["model"] == "claude-sonnet-5-5"
    assert kwargs["system"] == "system prompt"
    assert kwargs["messages"] == [{"role": "user", "content": "hello"}]
    assert kwargs["max_tokens"] == 900
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in kwargs
    assert "thinking" not in kwargs


def test_fallbacks_can_be_disabled(monkeypatch):
    monkeypatch.setenv("LLMDAILY_FALLBACKS", "off")
    client, messages = make_client([SimpleNamespace(type="text", text="ok")])
    AnthropicProvider(client=client).complete("s", "u", 100)
    assert "fallbacks" not in messages.kwargs
    assert "betas" not in messages.kwargs


def test_no_fallbacks_for_models_without_support():
    client, messages = make_client([SimpleNamespace(type="text", text="ok")])
    AnthropicProvider(model="claude-haiku-5-5", client=client).complete("s", "u", 100)
    assert "fallbacks" not in messages.kwargs


def test_refusal_raises():
    client, _ = make_client([], stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    with pytest.raises(LLMRefusal) as excinfo:
        AnthropicProvider(client=client).complete("s", "u", 100)
    assert excinfo.value.category == "cyber"


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("LLMDAILY_MODEL", "claude-opus-5-5")
    client, messages = make_client([SimpleNamespace(type="text", text="ok")])
    AnthropicProvider(client=client).complete("s", "u", 100)
    assert messages.kwargs["model"] == "claude-opus-5-5"


def test_large_requests_stream():
    final = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="streamed")],
        stop_reason="end_turn", stop_details=None, model="claude-sonnet-5-5",
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
    )

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return final

    calls = {}

    def stream(**kwargs):
        calls["kwargs"] = kwargs
        return FakeStream()

    def create(**kwargs):
        raise AssertionError("create() must not be used for large max_tokens")

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream, create=create)))
    completion = AnthropicProvider(client=client).complete("s", "u", 32000)
    assert completion.text == "streamed"
    assert calls["kwargs"]["max_tokens"] == 32000
