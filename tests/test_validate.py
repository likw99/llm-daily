from llm_daily.generators.validate import drop_unlinked_items


def test_keeps_linked_items_with_children():
    md = (
        "# RESEARCH\n\n## Paper of the Day\n"
        "- **[Great paper](https://arxiv.org/abs/2610.1)** (2026-10-21)\n"
        "  - Authors: A. Person\n"
        "  - Why it matters: it is good\n"
    )
    result = drop_unlinked_items(md)
    assert result.kept_items == 1 and result.dropped_items == 0
    assert "Authors: A. Person" in result.text
    assert "Why it matters" in result.text


def test_drops_unlinked_item_and_its_children():
    md = (
        "# PRODUCTS\n\n## New Releases\n"
        "- **[Tool](https://example.com/tool)** – ok\n"
        "- Mystery product\n"
        "  - with a detail\n"
        "- **[Other](https://example.com/other)** – ok\n"
    )
    result = drop_unlinked_items(md)
    assert result.dropped_items == 1
    assert "Mystery" not in result.text and "with a detail" not in result.text
    assert "Tool" in result.text and "Other" in result.text


def test_drops_unlinked_paragraph_keeps_nothing_notable():
    md = "# BUSINESS\n\nThe market keeps evolving.\n\nNothing notable today.\n"
    result = drop_unlinked_items(md)
    assert "market keeps evolving" not in result.text
    assert "Nothing notable today." in result.text
    assert result.dropped_paragraphs == 1 and result.kept_items == 0


def test_removes_empty_subheadings():
    md = (
        "# BUSINESS\n\n## Funding\n- No source here\n\n"
        "## M&A\n- **[Deal](https://example.com/deal)** – ok\n"
    )
    text = drop_unlinked_items(md).text
    assert "## Funding" not in text
    assert "## M&A" in text and text.startswith("# BUSINESS")


def test_numbered_and_star_bullets():
    md = "# TECHNOLOGY\n\n1. [repo](https://github.com/a/b)\n2. unlinked\n* also unlinked\n"
    result = drop_unlinked_items(md)
    assert result.kept_items == 1 and result.dropped_items == 2


def test_lazy_continuation_belongs_to_item():
    md = "# BUSINESS\n\n- **[Round](https://example.com/r)** (2026-10-21)\nraised $10M from investors\n"
    result = drop_unlinked_items(md)
    assert "raised $10M" in result.text and result.dropped_paragraphs == 0
