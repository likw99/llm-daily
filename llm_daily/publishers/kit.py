"""Kit (ConvertKit) broadcasts via the V4 API: https://developers.kit.com/api-reference/broadcasts/create-a-broadcast"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import requests

from .base import Issue
from .render import to_html

API_URL = "https://api.kit.com/v4/broadcasts"


class KitPublisher:
    """
    Creates a Kit broadcast for the issue.

    Configuration (environment):
        KIT_API_KEY        V4 API key (Settings > Developer)
        KIT_STATUS         "draft" (default) saves a draft to review in Kit;
                           "send" schedules it to go out two minutes from now
        KIT_PUBLIC         "true" also publishes it on your Kit creator profile (default false)
        KIT_SEGMENT_ID     optional: send only to this segment (default: all subscribers)
        KIT_TEMPLATE_ID    optional: email template ID (default: the account's default template)

    The Classic template wraps the content and adds the required unsubscribe link and address.
    """

    name = "kit"

    def __init__(self, api_key: Optional[str] = None, session: Optional[Any] = None):
        self.api_key = api_key or os.environ.get("KIT_API_KEY")
        if not self.api_key:
            raise ValueError("KIT_API_KEY is not set")
        self.status = os.environ.get("KIT_STATUS", "draft").strip().lower()
        if self.status not in ("draft", "send"):
            raise ValueError("KIT_STATUS must be 'draft' or 'send'")
        self.public = os.environ.get("KIT_PUBLIC", "false").strip().lower() == "true"
        self.segment_id = os.environ.get("KIT_SEGMENT_ID") or None
        self.template_id = os.environ.get("KIT_TEMPLATE_ID") or None
        self.session = session or requests.Session()

    def build_payload(self, issue: Issue, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        content = to_html(issue.markdown)
        if issue.web_url:
            content += f'<p><a href="{issue.web_url}">Read this issue on the web</a></p>'
        highlights = issue.highlights().replace("•", "").split("\n")
        payload: Dict[str, Any] = {
            "subject": issue.subject,
            "description": f"LLM Daily {issue.slug}",
            "content": content,
            "preview_text": (highlights[0].strip() if highlights and highlights[0].strip() else issue.subject)[:140],
            "public": self.public,
            "published_at": now.isoformat(),
            "send_at": (now + timedelta(minutes=2)).isoformat() if self.status == "send" else None,
            "email_address": None,
        }
        if self.template_id:
            payload["email_template_id"] = int(self.template_id)
        if self.segment_id:
            payload["subscriber_filter"] = [{"all": [{"type": "segment", "ids": [int(self.segment_id)]}]}]
        return payload

    def publish(self, issue: Issue) -> Dict[str, Any]:
        response = self.session.post(
            API_URL,
            json=self.build_payload(issue),
            headers={"X-Kit-Api-Key": self.api_key, "Accept": "application/json"},
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Kit API returned {response.status_code}: {response.text[:300]}")
        broadcast = response.json().get("broadcast", {})
        return {"id": broadcast.get("id"), "status": broadcast.get("status"), "send_at": broadcast.get("send_at")}
