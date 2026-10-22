from pathlib import Path

import pytest

from llm_daily.utils.common import get_project_root, load_sources


def test_project_root_contains_package():
    assert (get_project_root() / "llm_daily").is_dir()


def test_default_sources_file():
    sources = load_sources()
    names = [s["name"] for s in sources["reddit"]["subreddits"]]
    assert "LocalLLaMA" in names
    assert sources["x"]["list_id"] == ""


def test_sources_env_override(tmp_path: Path, monkeypatch):
    custom = tmp_path / "sources.yaml"
    custom.write_text("reddit:\n  subreddits:\n    - {name: singularity, active: true}\n", encoding="utf-8")
    monkeypatch.setenv("LLMDAILY_SOURCES", str(custom))
    assert load_sources()["reddit"]["subreddits"][0]["name"] == "singularity"


def test_reddit_collector_reads_active_subreddits(tmp_path: Path, monkeypatch):
    from llm_daily.collectors.reddit_collector import RedditCollector

    custom = tmp_path / "sources.yaml"
    custom.write_text(
        "reddit:\n  subreddits:\n    - {name: a, active: true}\n    - {name: b, active: false}\n",
        encoding="utf-8",
    )
    collector = RedditCollector.__new__(RedditCollector)
    assert collector._load_subreddits(str(custom)) == ["a"]


def test_x_collector_requires_list_id(monkeypatch):
    from llm_daily.collectors.x_collector import XCollector

    with pytest.raises(ValueError, match="X_LIST_ID"):
        XCollector(bearer_token="test-token")


def test_x_collector_uses_env_list_id(monkeypatch):
    from llm_daily.collectors.x_collector import XCollector

    monkeypatch.setenv("X_LIST_ID", "12345")
    assert XCollector(bearer_token="test-token").list_id == "12345"


def test_collector_error_returns_no_data():
    from llm_daily.collectors.base_collector import BaseCollector

    class Broken(BaseCollector):
        def collect_data(self, **kwargs):
            raise RuntimeError("network down")

        def format_for_llm(self, data):
            return "unused"

    assert Broken().run() == ("", {})
