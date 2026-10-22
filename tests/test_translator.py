from llm_daily.generators.translator import translate_to_chinese
from llm_daily.llm import Completion, Usage

ISSUE = (
    "# 🔍 LLM DAILY\n\n# BUSINESS\n\n"
    "- **[Big round](https://example.com/a)** (2026-10-21) – raised money\n"
    "- **[Deal](https://example.com/b)** (2026-10-21) – merged\n"
)


class Translator:
    name, model = "fake", "fake-model"

    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, system, user, max_tokens):
        self.calls.append((system, user, max_tokens))
        return Completion(text=self.text, model=self.model, usage=Usage(100, 80))


def test_translation_keeps_links():
    zh = ISSUE.replace("BUSINESS", "商业").replace("raised money", "完成融资").replace("merged", "合并")
    provider = Translator(zh)
    result = translate_to_chinese(ISSUE, provider)

    assert "商业" in result.text
    assert result.links_in == result.links_out == 2
    assert result.links_match
    assert result.usage.output_tokens == 80
    system, user, _ = provider.calls[0]
    assert "Simplified Chinese" in system and user == ISSUE


def test_lost_link_is_flagged(caplog):
    result = translate_to_chinese(ISSUE, Translator("# 商业\n\n- 只有一个 https://example.com/a\n"))
    assert not result.links_match
    assert "check the translation" in caplog.text
