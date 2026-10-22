"""The finished issue handed to every publisher."""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Optional, Protocol

_HIGHLIGHTS = re.compile(r"^#\s+(?:HIGHLIGHTS|今日要点)\s*$(.*?)(?=^#\s|\Z)", re.MULTILINE | re.DOTALL)


@dataclass
class Issue:
    day: date
    markdown: str                       # the edition that gets sent (EN, or ZH with --lang zh)
    markdown_en: str
    markdown_zh: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    site_url: Optional[str] = None      # base URL of the web archive, if any

    @property
    def subject(self) -> str:
        return f"LLM Daily: {self.day.strftime('%B %d, %Y')}"

    @property
    def slug(self) -> str:
        return self.day.isoformat()

    @property
    def web_url(self) -> Optional[str]:
        if not self.site_url:
            return None
        return f"{self.site_url.rstrip('/')}/issues/{self.slug}.html"

    def highlights(self) -> str:
        """The Highlights bullets of the sent edition, or an empty string."""
        match = _HIGHLIGHTS.search(self.markdown)
        if not match:
            return ""
        body = match.group(1)
        return "\n".join(line.rstrip() for line in body.strip().splitlines() if line.strip() and line.strip() != "---")


class Publisher(Protocol):
    name: str

    def publish(self, issue: Issue) -> Dict[str, Any]: ...
