"""Offline provider for --dry-run: builds plausible output from the input, with no network."""

import re

from .base import Completion, Usage

_SECTION = re.compile(r'"# ([A-Z ]+)"')
_URL = re.compile(r"https?://\S+")


class StubProvider:
    """
    Turns each '## Title' + URL pair in the input data into a linked item.

    Lets the whole pipeline (validation, archive, site, feeds) run without an API key.
    """

    name = "stub"
    model = "dry-run-stub"

    def complete(self, system: str, user: str, max_tokens: int) -> Completion:
        if "Simplified Chinese" in system:
            text = (user.replace("# HIGHLIGHTS", "# 今日要点").replace("# BUSINESS", "# 商业")
                    .replace("# PRODUCTS", "# 产品").replace("# TECHNOLOGY", "# 技术")
                    .replace("# RESEARCH", "# 研究").replace("## Sources & method", "## 来源与方法"))
        elif "HIGHLIGHTS" in system:
            titles = re.findall(r"\*\*\[([^\]]+)\]", user)[:4]
            text = "# HIGHLIGHTS\n\n" + "\n".join(f"• {t} (dry-run highlight)" for t in titles)
        else:
            match = _SECTION.search(system)
            header = match.group(1).strip() if match else "SECTION"
            items, title = [], None
            for line in user.splitlines():
                if line.startswith("## "):
                    title = line[3:].strip()
                url = _URL.search(line)
                if url and title:
                    items.append(f"- **[{title}]({url.group(0).rstrip(').,')})** – Example summary written by the dry-run stub.")
                    title = None
                if len(items) == 3:
                    break
            text = f"# {header}\n\n" + ("\n".join(items) if items else "Nothing notable today.")
        return Completion(text=text, model=self.model, stop_reason="end_turn",
                          usage=Usage(len(system + user) // 4, len(text) // 4))
