import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def get_project_root() -> Path:
    """Return the repository root (the directory that contains ``llm_daily/``)."""
    return Path(__file__).resolve().parents[2]


def load_sources(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the data sources config.

    The path is resolved in order: the ``path`` argument, the ``LLMDAILY_SOURCES``
    environment variable, then ``config/sources.yaml`` in the project root.

    Raises:
        FileNotFoundError: if the resolved file does not exist.
    """
    resolved = path or os.environ.get("LLMDAILY_SOURCES")
    file_path = Path(resolved) if resolved else get_project_root() / "config" / "sources.yaml"

    if not file_path.exists():
        raise FileNotFoundError(f"Sources config not found at {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_output(content: str, filename: Optional[str] = None, subfolder: Optional[str] = None) -> str:
    """
    Save output content to a file under ``data/output``.

    Args:
        content: Content to save
        filename: Optional filename (default: auto-generated based on date)
        subfolder: Optional subfolder within data/output

    Returns:
        str: Path to the saved file
    """
    output_dir = get_project_root() / "data" / "output"
    if subfolder:
        output_dir = output_dir / subfolder
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = f"llm_newsletter_{datetime.now().strftime('%Y-%m-%d')}.md"

    file_path = output_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)


def format_stats_text(stats: dict) -> str:
    """
    Format a statistics dictionary into a human-readable string

    Args:
        stats: Dictionary of statistics

    Returns:
        str: Formatted statistics text
    """
    if not stats:
        return ""

    lines = []

    if 'subreddit_count' in stats and 'total_posts' in stats and 'total_comments' in stats:
        lines.append(f"We analyzed {stats['total_posts']} posts and {stats['total_comments']} comments from {stats['subreddit_count']} subreddits for you.")

    return " ".join(lines)
