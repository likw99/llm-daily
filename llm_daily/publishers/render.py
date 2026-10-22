"""Markdown to HTML for the web archive and for email bodies."""

import re

import markdown as _markdown

# The Highlights prompt asks for "•" bullets, which Markdown does not treat as a list.
_BULLET_DOT = re.compile(r"^(\s*)•\s+", re.MULTILINE)


def to_html(md: str) -> str:
    """Render newsletter Markdown to an HTML fragment."""
    md = _BULLET_DOT.sub(r"\1- ", md)
    # A list needs a blank line before it to be recognised after a paragraph or heading.
    md = re.sub(r"(?m)^(?!\s*$)(?![-*+]\s|\d+\.\s|\s)(.+)\n(- )", r"\1\n\n\2", md)
    return _markdown.markdown(md, extensions=["extra", "sane_lists"], output_format="html")
