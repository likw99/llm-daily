"""Post the Highlights and a link to a Discord, Slack or Feishu/Lark webhook, or any JSON endpoint."""

import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from .base import Issue

FORMATS = ("discord", "slack", "feishu", "json")


def detect_format(url: str) -> str:
    host = urlparse(url).hostname or ""
    if host.endswith("discord.com") or host.endswith("discordapp.com"):
        return "discord"
    if host.endswith("hooks.slack.com"):
        return "slack"
    if host.endswith("feishu.cn") or host.endswith("larksuite.com"):
        return "feishu"
    return "json"


class WebhookPublisher:
    """
    Configuration (environment):
        LLMDAILY_WEBHOOK_URL     the incoming-webhook URL
        LLMDAILY_WEBHOOK_FORMAT  discord | slack | feishu | json (default: detected from the URL)
    """

    name = "webhook"

    def __init__(self, url: Optional[str] = None, fmt: Optional[str] = None, session: Optional[Any] = None):
        self.url = url or os.environ.get("LLMDAILY_WEBHOOK_URL")
        if not self.url:
            raise ValueError("LLMDAILY_WEBHOOK_URL is not set")
        self.format = (fmt or os.environ.get("LLMDAILY_WEBHOOK_FORMAT") or detect_format(self.url)).lower()
        if self.format not in FORMATS:
            raise ValueError(f"LLMDAILY_WEBHOOK_FORMAT must be one of: {', '.join(FORMATS)}")
        self.session = session or requests.Session()

    def _text(self, issue: Issue, limit: int) -> str:
        parts = [issue.subject, issue.highlights()]
        if issue.web_url:
            parts.append(f"Read the full issue: {issue.web_url}")
        text = "\n\n".join(p for p in parts if p)
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def build_payload(self, issue: Issue) -> Dict[str, Any]:
        if self.format == "discord":
            return {"content": self._text(issue, 2000)}
        if self.format == "slack":
            return {"text": self._text(issue, 3000)}
        if self.format == "feishu":
            return {"msg_type": "text", "content": {"text": self._text(issue, 4000)}}
        return {"subject": issue.subject, "date": issue.slug, "url": issue.web_url,
                "highlights": issue.highlights(), "markdown": issue.markdown}

    def publish(self, issue: Issue) -> Dict[str, Any]:
        response = self.session.post(self.url, json=self.build_payload(issue), timeout=30)
        if response.status_code >= 300:
            raise RuntimeError(f"Webhook returned {response.status_code}: {response.text[:200]}")
        if self.format == "feishu":
            body = response.json() if response.content else {}
            if body.get("code", 0) != 0:
                raise RuntimeError(f"Feishu webhook error {body.get('code')}: {body.get('msg')}")
        return {"format": self.format, "status": response.status_code}
