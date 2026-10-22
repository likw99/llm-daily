from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from llm_daily.publishers.base import Issue
from llm_daily.publishers.kit import API_URL, KitPublisher
from llm_daily.publishers.telegram import TelegramPublisher
from llm_daily.publishers.webhook import WebhookPublisher, detect_format

MD = (
    "# 🔍 LLM DAILY\n\n# HIGHLIGHTS\n\n• Big model released <today>\n• Funding round\n\n---\n\n"
    "# BUSINESS\n\n- **[Round](https://example.com/r)** – raised\n"
)


def issue(site=True):
    return Issue(day=date(2026, 10, 21), markdown=MD, markdown_en=MD,
                 site_url="https://example.github.io/llm-daily/" if site else None)


class Session:
    def __init__(self, status=200, body=None):
        self.status, self.body, self.calls = status, body or {}, []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return SimpleNamespace(status_code=self.status, content=b"x", text=str(self.body), json=lambda: self.body)


# --- Kit ---------------------------------------------------------------------------

def test_kit_requires_key():
    with pytest.raises(ValueError, match="KIT_API_KEY"):
        KitPublisher()


def test_kit_draft_payload(monkeypatch):
    now = datetime(2026, 10, 21, 2, 20, tzinfo=timezone.utc)
    payload = KitPublisher(api_key="k", session=Session()).build_payload(issue(), now=now)
    assert payload["subject"] == "LLM Daily: October 21, 2026"
    assert payload["send_at"] is None  # draft by default
    assert payload["public"] is False
    assert "<li>" in payload["content"] and "Read this issue on the web" in payload["content"]
    assert payload["preview_text"] == "Big model released <today>"
    assert "subscriber_filter" not in payload  # all subscribers


def test_kit_send_mode_schedules_and_targets_segment(monkeypatch):
    monkeypatch.setenv("KIT_STATUS", "send")
    monkeypatch.setenv("KIT_SEGMENT_ID", "42")
    now = datetime(2026, 10, 21, 2, 20, tzinfo=timezone.utc)
    payload = KitPublisher(api_key="k", session=Session()).build_payload(issue(), now=now)
    assert payload["send_at"] == "2026-10-21T02:22:00+00:00"
    assert payload["subscriber_filter"] == [{"all": [{"type": "segment", "ids": [42]}]}]


def test_kit_publish_posts_with_key_header():
    session = Session(status=201, body={"broadcast": {"id": 7, "status": "draft", "send_at": None}})
    result = KitPublisher(api_key="secret", session=session).publish(issue())
    assert result == {"id": 7, "status": "draft", "send_at": None}
    assert session.calls[0]["url"] == API_URL
    assert session.calls[0]["headers"]["X-Kit-Api-Key"] == "secret"


def test_kit_error_raises():
    with pytest.raises(RuntimeError, match="422"):
        KitPublisher(api_key="k", session=Session(status=422, body={"errors": ["bad"]})).publish(issue())


# --- Telegram ----------------------------------------------------------------------

def test_telegram_text_escapes_and_links():
    text = TelegramPublisher("t", "@chan", session=Session()).build_text(issue())
    assert text.startswith("<b>LLM Daily: October 21, 2026</b>")
    assert "&lt;today&gt;" in text
    assert 'href="https://example.github.io/llm-daily/issues/2026-10-21.html"' in text


def test_telegram_error_hides_token():
    session = Session(status=400, body={"ok": False, "description": "chat not found"})
    with pytest.raises(RuntimeError) as excinfo:
        TelegramPublisher("123:SECRET", "@chan", session=session).publish(issue())
    assert "SECRET" not in str(excinfo.value) and "chat not found" in str(excinfo.value)


def test_telegram_publish():
    session = Session(body={"ok": True, "result": {"message_id": 99}})
    assert TelegramPublisher("t", "@chan", session=session).publish(issue()) == {"message_id": 99}
    assert session.calls[0]["json"]["chat_id"] == "@chan"


# --- Webhook -----------------------------------------------------------------------

@pytest.mark.parametrize("url,fmt", [
    ("https://discord.com/api/webhooks/1/abc", "discord"),
    ("https://hooks.slack.com/services/T/B/x", "slack"),
    ("https://open.feishu.cn/open-apis/bot/v2/hook/abc", "feishu"),
    ("https://example.com/hook", "json"),
])
def test_detect_format(url, fmt):
    assert detect_format(url) == fmt


def test_webhook_payload_shapes():
    i = issue()
    assert "content" in WebhookPublisher("https://discord.com/api/webhooks/1/a", session=Session()).build_payload(i)
    assert "text" in WebhookPublisher("https://hooks.slack.com/services/x", session=Session()).build_payload(i)
    feishu = WebhookPublisher("https://open.feishu.cn/open-apis/bot/v2/hook/a", session=Session()).build_payload(i)
    assert feishu["msg_type"] == "text" and "LLM Daily" in feishu["content"]["text"]
    generic = WebhookPublisher("https://example.com/hook", session=Session()).build_payload(i)
    assert generic["date"] == "2026-10-21" and generic["markdown"] == MD


def test_feishu_error_code_raises():
    session = Session(body={"code": 19021, "msg": "sign match fail"})
    with pytest.raises(RuntimeError, match="19021"):
        WebhookPublisher("https://open.feishu.cn/open-apis/bot/v2/hook/a", session=session).publish(issue())
