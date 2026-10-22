"""Checks that keep unsourced claims out of a newsletter section."""

import re
from dataclasses import dataclass
from typing import List

_BULLET = re.compile(r"^(?:[-*•+]|\d+[.)])\s+")
_HEADING = re.compile(r"^(#{1,6})\s")
_RULE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,}|(?:\* ){2,}\*)\s*$")
_LINK = re.compile(r"https?://")
NOTHING_NOTABLE = "Nothing notable today."


@dataclass
class ValidationResult:
    text: str
    kept_items: int
    dropped_items: int
    dropped_paragraphs: int


def _has_link(lines: List[str]) -> bool:
    return any(_LINK.search(line) for line in lines)


def drop_unlinked_items(section_md: str) -> ValidationResult:
    """
    Remove content that has no source link.

    - A top-level list item without an http(s) link is removed together with its indented
      children and continuation lines.
    - A plain paragraph without a link is removed, except the "Nothing notable today." line.
    - Headings and horizontal rules are kept; subheadings left with no content are removed.
    """
    lines = section_md.splitlines()
    blocks: List[tuple] = []  # (kind, [lines]) with kind in heading|rule|item|para|blank
    current_kind = None
    current: List[str] = []

    def flush():
        nonlocal current_kind, current
        if current_kind is not None:
            blocks.append((current_kind, current))
        current_kind, current = None, []

    for line in lines:
        stripped = line.strip()
        indented = line[:1] in (" ", "\t")

        if not stripped:
            if current_kind == "para":
                flush()
            elif current_kind == "item":
                current.append(line)  # an indented child may follow the blank line
            continue

        if not indented and _HEADING.match(stripped):
            flush()
            blocks.append(("heading", [line]))
            continue
        if not indented and _RULE.match(stripped):
            flush()
            blocks.append(("rule", [line]))
            continue
        if not indented and _BULLET.match(stripped):
            flush()
            current_kind, current = "item", [line]
            continue
        if current_kind == "item" and (indented or (current and current[-1].strip())):
            # indented child, or a lazy continuation line directly under the item
            current.append(line)
            continue
        if current_kind == "para":
            current.append(line)
            continue
        flush()
        current_kind, current = "para", [line]
    flush()

    kept: List[tuple] = []
    kept_items = dropped_items = dropped_paragraphs = 0
    for kind, block in blocks:
        if kind == "item":
            if _has_link(block):
                kept_items += 1
                while block and not block[-1].strip():
                    block = block[:-1]
                kept.append((kind, block))
            else:
                dropped_items += 1
        elif kind == "para":
            text = " ".join(line.strip() for line in block)
            if _has_link(block) or NOTHING_NOTABLE.lower() in text.lower():
                kept.append((kind, block))
            else:
                dropped_paragraphs += 1
        else:
            kept.append((kind, block))

    # Remove subheadings (level >= 2) that no longer introduce any content.
    pruned: List[tuple] = []
    for i, (kind, block) in enumerate(kept):
        if kind == "heading":
            level = len(_HEADING.match(block[0].strip()).group(1))
            if level >= 2:
                has_content = False
                for next_kind, next_block in kept[i + 1:]:
                    if next_kind == "heading":
                        next_level = len(_HEADING.match(next_block[0].strip()).group(1))
                        if next_level <= level:
                            break
                        continue
                    if next_kind in ("item", "para"):
                        has_content = True
                        break
                if not has_content:
                    continue
        pruned.append((kind, block))

    # Blank line between blocks; consecutive list items stay a tight list.
    out: List[str] = []
    previous_kind = None
    for kind, block in pruned:
        if out and not (kind == "item" and previous_kind == "item"):
            out.append("")
        out.extend(block)
        previous_kind = kind
    text = "\n".join(out).strip() + "\n"
    return ValidationResult(text=text, kept_items=kept_items, dropped_items=dropped_items,
                            dropped_paragraphs=dropped_paragraphs)
