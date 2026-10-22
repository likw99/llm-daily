"""Post the Highlights and a link to a Telegram channel or chat."""

import html
import os
from typing import Any, Dict, Optional

import requests

from .base import Issue

LIMIT = 4096


class TelegramPublisher:
    """
    Configuration (environment):
        TELEGRAM_BOT_TOKEN  token from @BotFather
        TELEGRAM_CHAT_ID    channel username (e.g. @llm_daily) or numeric chat ID;
                            the bot must be an admin of the channel
    """

    name = "telegram"

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None, session: Optional[Any] = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        self.session = session or requests.Session()

    def build_text(self, issue: Issue) -> str:
        parts = [f"<b>{html.escape(issue.subject)}</b>"]
        highlights = issue.highlights()
        if highlights:
            parts.append(html.escape(highlights))
        if issue.web_url:
            parts.append(f'<a href="{html.escape(issue.web_url)}">Read the full issue</a>')
        text = "\n\n".join(parts)
        if len(text) > LIMIT:
            text = text[: LIMIT - 1] + "…"
        return text

    def publish(self, issue: Issue) -> Dict[str, Any]:
        response = self.session.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": self.chat_id, "text": self.build_text(issue), "parse_mode": "HTML",
                  "link_preview_options": {"is_disabled": not issue.web_url}},
            timeout=30,
        )
        data = response.json() if response.content else {}
        if response.status_code != 200 or not data.get("ok"):
            # Never echo the URL: it contains the bot token.
            raise RuntimeError(f"Telegram API returned {response.status_code}: {data.get('description', '')}")
        return {"message_id": data.get("result", {}).get("message_id")}
