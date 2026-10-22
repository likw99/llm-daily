import json
from datetime import date
from pathlib import Path

import feedparser
import pytest

from llm_daily.cli import main
from llm_daily.publishers.archive import ArchivePublisher
from llm_daily.publishers.base import Issue
from llm_daily.publishers.registry import publish_all, selected_names
from llm_daily.publishers.render import to_html
from llm_daily.site import build_site

EN = (
    "# 🔍 LLM DAILY\n## Your Daily Briefing on Large Language Models\n**October 21, 2026**\n\n"
    "# HIGHLIGHTS\n\n• First highlight\n• Second highlight\n\n---\n\n"
    "# BUSINESS\n\n- **[Round](https://example.com/r)** (2026-10-21) – raised\n\n---\n\n"
    "## Sources & method\n\nWritten by test.\n"
)


def make_issue(day=date(2026, 10, 21), zh=None):
    return Issue(day=day, markdown=EN, markdown_en=EN, markdown_zh=zh, meta={"model": "m"},
                 site_url="https://example.github.io/llm-daily/")


def test_issue_subject_url_and_highlights():
    issue = make_issue()
    assert issue.subject == "LLM Daily: October 21, 2026"
    assert issue.web_url == "https://example.github.io/llm-daily/issues/2026-10-21.html"
    assert issue.highlights() == "• First highlight\n• Second highlight"


def test_archive_writes_dated_files(tmp_path):
    result = ArchivePublisher(tmp_path).publish(make_issue(zh="# 商业\n"))
    folder = tmp_path / "2026" / "10"
    assert (folder / "2026-10-21.md").read_text(encoding="utf-8") == EN
    assert (folder / "2026-10-21.zh.md").exists()
    meta = json.loads((folder / "2026-10-21.json").read_text(encoding="utf-8"))
    assert meta["model"] == "m" and meta["subject"] == "LLM Daily: October 21, 2026"
    assert len(result["files"]) == 3


def test_render_turns_dot_bullets_into_a_list():
    html = to_html("# HIGHLIGHTS\n\n• one\n• two\n")
    assert html.count("<li>") == 2


def test_site_and_feed(tmp_path):
    archive = tmp_path / "archive"
    ArchivePublisher(archive).publish(make_issue(date(2026, 10, 20)))
    ArchivePublisher(archive).publish(make_issue(date(2026, 10, 21), zh="# 今日要点\n\n• 一\n"))
    out = tmp_path / "site"
    assert build_site(archive, out, "https://example.github.io/llm-daily") == 2

    index = (out / "index.html").read_text(encoding="utf-8")
    assert index.index("2026-10-21") < index.index("2026-10-20")  # newest first
    page = (out / "issues" / "2026-10-21.html").read_text(encoding="utf-8")
    assert "LLM DAILY" not in page  # masthead stripped, site header used instead
    assert page.count("October 21, 2026") == 2  # <title> and the date line, not the masthead
    assert (out / "issues" / "2026-10-21.zh.html").exists()

    feed = feedparser.parse(str(out / "feed.xml"))
    assert not feed.bozo
    assert [e.title for e in feed.entries] == ["LLM Daily: October 21, 2026", "LLM Daily: October 20, 2026"]
    assert feed.entries[0].link == "https://example.github.io/llm-daily/issues/2026-10-21.html"
    zh_feed = feedparser.parse(str(out / "feed-zh.xml"))
    assert not zh_feed.bozo and len(zh_feed.entries) == 1


def test_selected_names(monkeypatch):
    assert selected_names() == ["archive"]
    monkeypatch.setenv("LLMDAILY_PUBLISHERS", "archive, kit,kit")
    assert selected_names() == ["archive", "kit"]
    assert selected_names(no_publish=True) == ["archive"]
    with pytest.raises(ValueError, match="Unknown publisher"):
        selected_names("archive,substack")


def test_one_failing_publisher_does_not_stop_others():
    class Ok:
        name = "ok"

        def publish(self, issue):
            return {"id": 1}

    class Broken:
        name = "broken"

        def publish(self, issue):
            raise RuntimeError("down")

    results = publish_all(make_issue(), ["kit", "archive"], overrides={"kit": Broken(), "archive": Ok()})
    assert results["kit"] == {"ok": False, "error": "down"}
    assert results["archive"] == {"ok": True, "id": 1}


def test_dry_run_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr("llm_daily.cli.get_project_root", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["--dry-run", "--lang", "both"]) == 0

    out = tmp_path / "data" / "dry-run"
    archived = list((out / "archive").rglob("*.md"))
    assert {p.name.endswith(".zh.md") for p in archived} == {True, False}
    meta = json.loads(next((out / "archive").rglob("*.json")).read_text(encoding="utf-8"))
    assert meta["dry_run"] is True and meta["provider"] == "stub"
    assert set(meta["sections"]) == {"business", "products", "technology", "research"}
    assert not feedparser.parse(str(out / "site" / "feed.xml")).bozo
    assert (Path(tmp_path) / "data" / "output").exists() is False
