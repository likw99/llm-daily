import pytest

from llm_daily.llm import get_provider
from llm_daily.llm.anthropic_provider import AnthropicProvider
from llm_daily.llm.openai_provider import OpenAICompatibleProvider


def test_defaults_to_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    provider = get_provider()
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5-5"


def test_explicit_name_and_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = get_provider("openai", "deepseek-chat")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "deepseek-chat"


def test_env_selects_provider(monkeypatch):
    monkeypatch.setenv("LLMDAILY_PROVIDER", "openai")
    monkeypatch.setenv("LLMDAILY_MODEL", "qwen-plus")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert isinstance(get_provider(), OpenAICompatibleProvider)


def test_auto_selects_openai_when_only_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LLMDAILY_MODEL", "llama3.1")
    assert isinstance(get_provider(), OpenAICompatibleProvider)


def test_unknown_provider():
    with pytest.raises(ValueError, match="anthropic, openai"):
        get_provider("bard")
