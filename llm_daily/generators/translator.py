"""Chinese edition: translate a finished issue while keeping every link intact."""

import logging
import re
from dataclasses import dataclass, field

from ..llm import LLMProvider, Usage

logger = logging.getLogger(__name__)

_URL = re.compile(r"https?://[^\s)\]>\"']+")

TRANSLATE_PROMPT = """
You translate the LLM Daily newsletter from English into Simplified Chinese for Chinese-speaking
AI practitioners.

Rules:
- Keep the Markdown structure exactly: the same headings, bullets, indentation, bold and
  horizontal rules, in the same order.
- Keep every URL exactly as written. Translate link text, never the URL.
- Keep dates, numbers, code, model names, product names, company names, paper titles and
  GitHub repository names in their original form.
- Use the terms Chinese AI media commonly use, for example 大模型, 智能体, 开源, 推理, 微调,
  多模态, 基准测试.
- Translate headings as: HIGHLIGHTS → 今日要点, BUSINESS → 商业, PRODUCTS → 产品,
  TECHNOLOGY → 技术, RESEARCH → 研究, Sources & method → 来源与方法,
  "Your Daily Briefing on Large Language Models" → 大模型每日简报.
- Do not add, remove or summarise anything. Output only the translated newsletter.
"""


@dataclass
class Translation:
    text: str
    links_in: int
    links_out: int
    usage: Usage = field(default_factory=Usage)

    @property
    def links_match(self) -> bool:
        return self.links_in == self.links_out


def translate_to_chinese(markdown: str, provider: LLMProvider, max_tokens: int = 32000) -> Translation:
    """
    Translate a finished newsletter into Simplified Chinese.

    The number of URLs before and after is compared; a mismatch is logged so a broken
    translation can be spotted, but the text is still returned.
    """
    completion = provider.complete(system=TRANSLATE_PROMPT, user=markdown, max_tokens=max_tokens)
    text = completion.text.strip() + "\n"
    result = Translation(
        text=text,
        links_in=len(_URL.findall(markdown)),
        links_out=len(_URL.findall(text)),
        usage=completion.usage,
    )
    if not result.links_match:
        logger.warning(
            "Chinese edition has %s links but the English issue has %s; check the translation",
            result.links_out, result.links_in,
        )
    return result
