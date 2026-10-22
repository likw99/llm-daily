"""Write each issue into archive/YYYY/MM/ so the repo keeps a dated history."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.common import get_project_root
from .base import Issue


class ArchivePublisher:
    name = "archive"

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else get_project_root() / "archive"

    def paths(self, issue: Issue) -> Dict[str, Path]:
        folder = self.root / f"{issue.day:%Y}" / f"{issue.day:%m}"
        return {
            "en": folder / f"{issue.slug}.md",
            "zh": folder / f"{issue.slug}.zh.md",
            "meta": folder / f"{issue.slug}.json",
        }

    def publish(self, issue: Issue) -> Dict[str, Any]:
        paths = self.paths(issue)
        paths["en"].parent.mkdir(parents=True, exist_ok=True)

        paths["en"].write_text(issue.markdown_en, encoding="utf-8")
        written = [str(paths["en"])]
        if issue.markdown_zh:
            paths["zh"].write_text(issue.markdown_zh, encoding="utf-8")
            written.append(str(paths["zh"]))

        meta = {"date": issue.slug, "subject": issue.subject, **issue.meta}
        paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(str(paths["meta"]))
        return {"files": written}
