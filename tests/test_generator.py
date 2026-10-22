from llm_daily.generators.newsletter_generator import NewsletterGenerator
from llm_daily.llm import Completion, Usage

FULL_DATA = dict(
    venturebeat_data="# VentureBeat\n\n## Story one\nhttps://example.com/1",
    producthunt_data="# Product Hunt\n\n## Tool\nhttps://example.com/tool",
    github_data="# GitHub\n\n## repo\nhttps://github.com/example/repo",
    arxiv_data="# arXiv\n\n## Paper\nhttps://arxiv.org/abs/2610.00001",
)


def test_full_issue_has_sections_highlights_and_footer(fake_provider):
    generator = NewsletterGenerator(provider=fake_provider)
    content = generator.generate_content(**FULL_DATA)

    for header in ("# HIGHLIGHTS", "# BUSINESS", "# PRODUCTS", "# TECHNOLOGY", "# RESEARCH", "## Sources & method"):
        assert header in content
    assert "LOOKING AHEAD" not in content
    assert "fake-model" in content
    # 4 sections + highlights, no conclusion call
    assert generator.usage == {"calls": 5, "input_tokens": 50, "output_tokens": 25}


def test_no_data_means_no_calls_and_empty_issue(fake_provider):
    generator = NewsletterGenerator(provider=fake_provider)
    assert generator.generate_content() == ""
    assert fake_provider.calls == []
    assert set(generator.report["omitted"]) == {"business", "products", "technology", "research"}


def test_section_without_data_is_skipped(fake_provider):
    generator = NewsletterGenerator(provider=fake_provider)
    content = generator.generate_content(arxiv_data=FULL_DATA["arxiv_data"])

    assert "# RESEARCH" in content
    assert "# BUSINESS" not in content
    assert "Business (no data)" in content
    prompts = " ".join(call["user"] for call in fake_provider.calls)
    assert "your knowledge" not in prompts


def test_prompts_carry_grounding_rules(fake_provider):
    NewsletterGenerator(provider=fake_provider).generate_content(**FULL_DATA)
    section_systems = [c["system"] for c in fake_provider.calls[:4]]
    assert all("Use ONLY the data provided" in s for s in section_systems)


def test_failed_section_is_left_out_not_invented(fake_provider):
    class FlakyProvider(type(fake_provider)):
        def complete(self, system, user, max_tokens):
            if "# PRODUCTS" in system:
                raise RuntimeError("upstream 500")
            return super().complete(system, user, max_tokens)

    generator = NewsletterGenerator(provider=FlakyProvider())
    content = generator.generate_content(**FULL_DATA)
    assert "# PRODUCTS" not in content
    assert "technical limitations" not in content
    assert "Products (generation failed)" in content


def test_unlinked_items_are_removed_and_counted():
    class UnlinkedProvider:
        name, model = "fake", "fake-model"

        def complete(self, system, user, max_tokens):
            if "HIGHLIGHTS" in system:
                text = "# HIGHLIGHTS\n\n• one"
            else:
                text = ("# BUSINESS\n\n## Funding\n"
                        "- **[Real round](https://example.com/a)** (2026-10-21) – sourced\n"
                        "- Rumoured round with no source\n\n"
                        "Some commentary paragraph without a link.\n")
            return Completion(text=text, model=self.model, usage=Usage(1, 1))

    generator = NewsletterGenerator(provider=UnlinkedProvider())
    content = generator.generate_content(venturebeat_data=FULL_DATA["venturebeat_data"])
    assert "Real round" in content
    assert "Rumoured round" not in content
    assert "commentary paragraph" not in content
    assert "2 unsourced lines were removed" in content


def test_section_with_nothing_notable_is_left_out():
    class NothingProvider:
        name, model = "fake", "fake-model"

        def complete(self, system, user, max_tokens):
            return Completion(text="# RESEARCH\n\nNothing notable today.", model=self.model, usage=Usage(1, 1))

    generator = NewsletterGenerator(provider=NothingProvider())
    assert generator.generate_content(arxiv_data=FULL_DATA["arxiv_data"]) == ""
    assert generator.report["omitted"] == {
        "business": "no data", "products": "no data", "technology": "no data", "research": "nothing notable",
    }


def test_highlights_failure_omits_highlights(fake_provider):
    class NoHighlights(type(fake_provider)):
        def complete(self, system, user, max_tokens):
            if "HIGHLIGHTS" in system:
                raise RuntimeError("boom")
            return super().complete(system, user, max_tokens)

    content = NewsletterGenerator(provider=NoHighlights()).generate_content(**FULL_DATA)
    assert "# HIGHLIGHTS" not in content
    assert "# BUSINESS" in content


def test_footer_lists_failed_sources(fake_provider):
    content = NewsletterGenerator(provider=fake_provider).generate_content(
        **FULL_DATA, failed_sources=["Reddit", "Product Hunt"]
    )
    assert "Unavailable today: Reddit, Product Hunt." in content


def test_section_calls_leave_room_for_thinking(fake_provider):
    NewsletterGenerator(provider=fake_provider).generate_content(**FULL_DATA)
    assert all(call["max_tokens"] >= 16000 for call in fake_provider.calls[:4])
