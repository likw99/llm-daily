import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..llm import LLMProvider, get_provider
from ..utils.common import format_stats_text
from .validate import NOTHING_NOTABLE, drop_unlinked_items

REPO_URL = "https://github.com/likw99/llm-daily"

# Appended to every data-section prompt. The newsletter must only report what the
# collected data contains; validate.drop_unlinked_items enforces the link rule afterwards.
GROUNDING_RULES = f"""
Rules that override everything above:
- Use ONLY the data provided in the user message. Do not add news, products, papers, numbers
  or quotes from your own knowledge.
- Format every item as ONE top-level bullet that starts with the linked title, for example:
  - **[Title of the item](https://example.com/link)** (YYYY-MM-DD) – one or two sentences.
  Put any extra detail (authors, features, stars) on indented sub-bullets under that item.
  Never use a top-level bullet for anything that is not a linked item.
- Use the exact URL from the data. If an item has no URL in the data, leave it out.
- Take dates from the data. If the data gives no date for an item, omit the date rather than guess.
- Do not write commentary paragraphs, introductions or conclusions; only headers and items.
- If nothing in the data is relevant, return only the section header followed by the line:
  {NOTHING_NOTABLE}
"""

SECTION_ORDER = ["business", "products", "technology", "research"]


class NewsletterGenerator:
    """Generator for the LLM newsletter content, one LLM call per section"""

    # Thinking tokens count against max_tokens on current models, so leave headroom.
    SECTION_MAX_TOKENS = 16000
    SHORT_MAX_TOKENS = 4000

    def __init__(self, provider: Optional[LLMProvider] = None):
        """
        Initialize the newsletter generator

        Args:
            provider: LLM provider to use (defaults to get_provider(), configured from the environment)
        """
        self.provider = provider or get_provider()
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.report: Dict[str, Any] = {}

    def generate_content(self,
                        reddit_data: Optional[str] = None,
                        reddit_stats: Optional[Dict[str, Any]] = None,
                        x_data: Optional[str] = None,
                        x_stats: Optional[Dict[str, Any]] = None,
                        arxiv_data: Optional[str] = None,
                        arxiv_stats: Optional[Dict[str, Any]] = None,
                        github_data: Optional[str] = None,
                        github_stats: Optional[Dict[str, Any]] = None,
                        huggingface_data: Optional[str] = None,
                        huggingface_stats: Optional[Dict[str, Any]] = None,
                        producthunt_data: Optional[str] = None,
                        producthunt_stats: Optional[Dict[str, Any]] = None,
                        venturebeat_data: Optional[str] = None,
                        venturebeat_stats: Optional[Dict[str, Any]] = None,
                        techcrunch_data: Optional[str] = None,
                        techcrunch_stats: Optional[Dict[str, Any]] = None,
                        sequoia_data: Optional[str] = None,
                        sequoia_stats: Optional[Dict[str, Any]] = None,
                        failed_sources: Optional[List[str]] = None) -> str:
        """
        Generate the newsletter from collected data.

        A section is only written when it has data, and any item without a source link is
        removed. If no section has content, an empty string is returned so nothing is published.

        Args:
            [Various data sources and their stats]
            failed_sources: names of collectors that errored or returned nothing

        Returns:
            str: Generated newsletter content, or "" when there is nothing to publish
        """
        stats_text = self._create_stats_text(
            reddit_stats=reddit_stats,
            x_stats=x_stats,
            arxiv_stats=arxiv_stats,
            github_stats=github_stats,
            huggingface_stats=huggingface_stats,
            producthunt_stats=producthunt_stats,
            venturebeat_stats=venturebeat_stats,
            techcrunch_stats=techcrunch_stats,
            sequoia_stats=sequoia_stats
        )

        sections: Dict[str, str] = {}
        omitted: Dict[str, str] = {}
        dropped_total = 0

        for section_name, generator_method, params in [
            ("business", self._generate_business_section, {
                "venturebeat_data": self._preprocess_data(venturebeat_data, max_items=3),
                "techcrunch_data": self._preprocess_data(techcrunch_data, max_items=3),
                "x_data": self._preprocess_data(x_data, max_items=3, max_chars=1000),
                "sequoia_data": self._preprocess_data(sequoia_data, max_items=3)
            }),
            ("products", self._generate_products_section, {
                "producthunt_data": self._preprocess_data(producthunt_data, max_items=3),
                "reddit_data": self._preprocess_data(reddit_data, max_items=3, max_chars=1000)
            }),
            ("technology", self._generate_technology_section, {
                "github_data": self._preprocess_data(github_data, max_items=3),
                "huggingface_data": self._preprocess_data(huggingface_data, max_items=3)
            }),
            ("research", self._generate_research_section, {
                "arxiv_data": self._preprocess_data(arxiv_data, max_items=8, max_chars=1500)
            })
        ]:
            if not any(params.values()):
                print(f"- {section_name.upper()} skipped: no data from its sources")
                omitted[section_name] = "no data"
                continue

            print(f"Generating {section_name.upper()} section...")
            start_time = time.time()
            try:
                raw = generator_method(**params)
            except Exception as e:
                print(f"✗ {section_name.upper()} failed, leaving it out: {e}")
                omitted[section_name] = "generation failed"
                continue

            result = drop_unlinked_items(raw)
            dropped_total += result.dropped_items + result.dropped_paragraphs
            if result.kept_items == 0:
                print(f"- {section_name.upper()} left out: no linked items")
                omitted[section_name] = "nothing notable"
                continue

            sections[section_name] = result.text
            print(f"✓ {section_name.upper()} section completed in {time.time() - start_time:.1f} seconds "
                  f"({result.kept_items} items, {result.dropped_items} unlinked items removed)")

        self.report = {
            "sections": list(sections),
            "omitted": omitted,
            "dropped_items": dropped_total,
            "failed_sources": list(failed_sources or []),
            "stats_text": stats_text.strip(),
        }

        if not sections:
            print("No section has content; nothing to publish.")
            return ""

        print("Assembling final newsletter...")
        return self._assemble_newsletter(sections)

    def _create_stats_text(self, **stats_sources) -> str:
        """Create statistics text for the introduction"""
        stats_text = ""
        
        # Add Reddit stats if available
        if stats_sources.get('reddit_stats'):
            reddit_stats_text = format_stats_text(stats_sources['reddit_stats'])
            if reddit_stats_text:
                stats_text += reddit_stats_text + " "
        
        # Add X stats if available
        if stats_sources.get('x_stats'):
            tweets_count = stats_sources['x_stats'].get('total_tweets', 0)
            list_name = stats_sources['x_stats'].get('list_name', 'AI experts')
            if tweets_count > 0:
                stats_text += f"We analyzed {tweets_count} tweets from the {list_name}. "
        
        # Add arXiv stats if available
        if stats_sources.get('arxiv_stats'):
            papers_count = stats_sources['arxiv_stats'].get('total_papers', 0)
            recent_count = stats_sources['arxiv_stats'].get('last_week_count', 0)
            if papers_count > 0:
                stats_text += f"We analyzed {papers_count} research papers from arXiv ({recent_count} from last week). "
        
        # Add GitHub stats if available
        if stats_sources.get('github_stats'):
            repos_count = stats_sources['github_stats'].get('total_repos', 0)
            if repos_count > 0:
                stats_text += f"We analyzed {repos_count} trending AI repositories on GitHub. "
        
        # Add Hugging Face stats if available
        if stats_sources.get('huggingface_stats'):
            models_count = stats_sources['huggingface_stats'].get('total_models', 0)
            datasets_count = stats_sources['huggingface_stats'].get('total_datasets', 0)
            spaces_count = stats_sources['huggingface_stats'].get('total_spaces', 0)
            sort_option = stats_sources['huggingface_stats'].get('sort_option', 'trendingScore')
            
            if models_count > 0 or datasets_count > 0 or spaces_count > 0:
                stats_text += f"We analyzed {models_count} trending models, {datasets_count} datasets, and {spaces_count} spaces from Hugging Face Hub (sorted by {sort_option}). "

        # Add Product Hunt stats if available
        if stats_sources.get('producthunt_stats'):
            products_count = stats_sources['producthunt_stats'].get('total_products', 0)
            if products_count > 0:
                stats_text += f"We analyzed {products_count} AI products from Product Hunt. "

        # Add VentureBeat stats if available
        if stats_sources.get('venturebeat_stats'):
            articles_count = stats_sources['venturebeat_stats'].get('total_articles', 0)
            if articles_count > 0:
                stats_text += f"We analyzed {articles_count} AI articles from VentureBeat. "
        
        # Add TechCrunch stats if available
        if stats_sources.get('techcrunch_stats'):
            articles_count = stats_sources['techcrunch_stats'].get('total_articles', 0)
            if articles_count > 0:
                stats_text += f"We analyzed {articles_count} AI articles from TechCrunch. "

        # Add Sequoia stats if available
        if stats_sources.get('sequoia_stats'):
            articles_count = stats_sources['sequoia_stats'].get('total_articles', 0)
            if articles_count > 0:
                stats_text += f"We analyzed {articles_count} insights from Sequoia Capital. "
                
        return stats_text
    
    def _preprocess_data(self, data: Optional[str], max_items: int = 5, max_chars: int = 2000) -> Optional[str]:
        """
        Preprocess data to reduce volume
        
        Args:
            data: Raw data from collector
            max_items: Maximum number of items to include
            max_chars: Maximum characters per item
            
        Returns:
            str or None: Preprocessed data
        """
        if not data:
            return None
            
        # Split data into sections based on markdown headers
        sections = []
        current_section = ""
        
        for line in data.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections.append(current_section)
                current_section = line + '\n'
            else:
                current_section += line + '\n'
                
        if current_section:
            sections.append(current_section)
        
        # Always keep the first section (usually an introduction)
        processed_sections = sections[:1] if sections else []
        
        # Add a limited number of other sections
        if len(sections) > 1:
            subsection_count = 0
            for section in sections[1:]:
                # Skip if we've reached the max
                if subsection_count >= max_items:
                    break
                    
                # Truncate section if too long
                if len(section) > max_chars:
                    # Find the last paragraph break before max_chars
                    last_break = section[:max_chars].rfind('\n\n')
                    if last_break == -1 or last_break < max_chars // 2:
                        last_break = max_chars
                        
                    truncated = section[:last_break] + "\n\n...[truncated]...\n"
                    processed_sections.append(truncated)
                else:
                    processed_sections.append(section)
                    
                subsection_count += 1
        
        # Recombine sections
        return ''.join(processed_sections)
    
    def _make_api_call(self, prompt: str, user_message: str, max_tokens: int = SECTION_MAX_TOKENS) -> str:
        """
        Call the configured LLM provider and record token usage.

        Retries for rate limits and transient errors are handled by the provider's SDK.

        Args:
            prompt: System prompt
            user_message: User message
            max_tokens: Maximum tokens to generate (includes thinking on models that think)

        Returns:
            str: The model's text response
        """
        completion = self.provider.complete(system=prompt, user=user_message, max_tokens=max_tokens)
        self.usage["calls"] += 1
        self.usage["input_tokens"] += completion.usage.input_tokens
        self.usage["output_tokens"] += completion.usage.output_tokens
        return completion.text

    def _generate_business_section(self, venturebeat_data: Optional[str] = None, 
                                  techcrunch_data: Optional[str] = None,
                                  x_data: Optional[str] = None,
                                  sequoia_data: Optional[str] = None) -> Optional[str]:
        """Generate the Business section of the newsletter"""
        
        prompt = """
        Generate the BUSINESS section of the LLM Daily newsletter. This section should cover:
        
        - Funding & Investment: VC activity, funding rounds, and investment trends
        - M&A: Mergers, acquisitions, and partnerships
        - Company Updates: Major announcements from AI companies and tech giants
        - Market Analysis: Emerging trends and shifts in the AI market
        
        Use the provided data to extract the most significant business developments in the AI industry
        from ONLY the past 24 hours. Strictly exclude any news older than 24 hours.
        
        For each piece of news:
        1. Include a DIRECT LINK to the original source article
        2. Include the publication date in (YYYY-MM-DD) format
        3. Attribute all information to specific sources
        4. Include only the most recent and relevant developments
        
        Return only the BUSINESS section formatted in Markdown, starting with the "# BUSINESS" header.
        """
        
        # Build user message with available data
        user_message = "Generate the BUSINESS section for today's LLM Daily newsletter.\n\n"
        
        sources = []
        if venturebeat_data:
            sources.append("VentureBeat AI news:\n\n" + venturebeat_data)
        if techcrunch_data:
            sources.append("TechCrunch AI news:\n\n" + techcrunch_data)
        if x_data:
            sources.append("X/Twitter discussions:\n\n" + x_data)
        if sequoia_data:
            sources.append("Sequoia Capital insights:\n\n" + sequoia_data)
            
        if not sources:
            return None
        user_message += "Here is the data to use for this section:\n\n"
        user_message += "\n\n---\n\n".join(sources)
        
        return self._make_api_call(prompt + GROUNDING_RULES, user_message)
    
    def _generate_products_section(self, producthunt_data: Optional[str] = None,
                                  reddit_data: Optional[str] = None) -> Optional[str]:
        """Generate the Products section of the newsletter"""
        
        prompt = """
        Generate the PRODUCTS section of the LLM Daily newsletter. This section should cover:

        - New Releases: Notable new AI products and services from both startups and established players (OpenAI, Anthropic, Google, Microsoft, Meta, etc.)
        - Product Updates: Significant updates to existing AI products and models
        - Applications & Use Cases: How AI is being applied in different domains
        - Community Reception: User feedback and reaction to new products

        For EACH product mentioned:
        1. Include a DIRECT LINK to the original source announcement or article
        2. Specify the company behind the product (and note if it's a startup or established player)
        3. Include the release/announcement date in (YYYY-MM-DD) format
        4. Provide a concise summary focusing on key features, capabilities, and differentiators

        Use the provided data to extract the most significant product developments in the AI industry
        from the past 24 hours. Focus on factual information with specific attributions to sources.
        Return only the PRODUCTS section formatted in Markdown, starting with the "# PRODUCTS" header.
        """
        
        # Build user message with available data
        user_message = "Generate the PRODUCTS section for today's LLM Daily newsletter.\n\n"
        
        sources = []
        if producthunt_data:
            sources.append("Product Hunt launches:\n\n" + producthunt_data)
        if reddit_data:
            sources.append("Reddit discussions:\n\n" + reddit_data)
            
        if not sources:
            return None
        user_message += "Here is the data to use for this section:\n\n"
        user_message += "\n\n---\n\n".join(sources)
        
        return self._make_api_call(prompt + GROUNDING_RULES, user_message)
    
    def _generate_technology_section(self, github_data: Optional[str] = None,
                                    huggingface_data: Optional[str] = None) -> Optional[str]:
        """Generate the Technology section of the newsletter"""
        
        prompt = """
        Generate the TECHNOLOGY section of the LLM Daily newsletter. This section should cover:
        
        - Open Source Projects: Interesting GitHub repositories and contributions
        - Models & Datasets: New or updated models on Hugging Face and elsewhere
        - Developer Tools: Tools that improve AI development workflow
        - Infrastructure: Advances in training, deployment, and scaling technology

        Focus on factual information about each project, including:
        1. DIRECT LINKS to each project (GitHub repos, Hugging Face models & Datasets)
        2. The PRIMARY PURPOSE of each project in 1-2 concise sentences
        3. DISTINCTIVE FEATURES that set it apart from existing alternatives
        4. TECHNICAL DETAILS like frameworks, approaches, or architecture when relevant
        5. Current MOMENTUM indicators (stars, recent updates, community adoption)

        For Hugging Face content, focus on the most significant models, datasets, and spaces based on trending score.
        Highlight what makes them interesting, unique, or valuable to the AI community.

        Use the provided data to extract the most significant technology developments in the AI industry
        from the past 24 hours.
        Return only the TECHNOLOGY section formatted in Markdown, starting with the "# TECHNOLOGY" header.
        """
        
        # Build user message with available data
        user_message = "Generate the TECHNOLOGY section for today's LLM Daily newsletter.\n\n"
        
        sources = []
        if github_data:
            sources.append("GitHub trending repositories:\n\n" + github_data)
        if huggingface_data:
            sources.append("Hugging Face models and datasets:\n\n" + huggingface_data)
            
        if not sources:
            return None
        user_message += "Here is the data to use for this section:\n\n"
        user_message += "\n\n---\n\n".join(sources)
        
        return self._make_api_call(prompt + GROUNDING_RULES, user_message)
    
    def _generate_research_section(self, arxiv_data: Optional[str] = None) -> Optional[str]:
        """Generate the Research section of the newsletter"""
        
        prompt = """
        Generate the RESEARCH section of the LLM Daily newsletter. This section should focus exclusively on academic and scientific research papers related to LLMs and AI, published within the last 24 hours.

        Structure the RESEARCH section as follows:
        
        1. "# RESEARCH" as the main header
        
        2. "## Paper of the Day" - the single most significant paper from the provided data, as one
        top-level bullet: the linked title (arXiv URL, https://arxiv.org/abs/XXXX.XXXXX) and date, then
        indented sub-bullets for the authors, institutions if the data names them, why it matters
        (2-3 sentences) and the key findings.

        3. "## Notable Research" - 3-5 other significant papers, one top-level bullet each: the linked
        title and date, then an indented sub-bullet with the primary author and a 1-2 sentence
        summary of the key contribution.
        
        For EACH paper mentioned:
        1. ALWAYS include a direct link to the original paper (arXiv link preferred)
        2. Include the publication date in (YYYY-MM-DD) format
        3. Focus on papers that advance the state of LLMs through novel architectures, training methods, evaluation techniques, or applications
        4. Prioritize papers with potential for significant impact on the field
        
        Use the provided arXiv data to extract ONLY the most significant research papers published in the last 24 hours.
        Return only the RESEARCH section formatted in Markdown.
        """
        
        # Build user message with available data
        user_message = "Generate the RESEARCH section for today's LLM Daily newsletter.\n\n"
        
        if not arxiv_data:
            return None
        user_message += "Here are the recent arXiv research papers to use for this section:\n\n" + arxiv_data
        
        user_message += "\n\nRemember to ALWAYS include direct links to each paper mentioned, prioritize papers published within the last 24 hours, and follow the structured format specified in the instructions."
        
        return self._make_api_call(prompt + GROUNDING_RULES, user_message)
    
    def _assemble_newsletter(self, sections: Dict[str, str]) -> str:
        """Join the header, Highlights, the sections that have content, and the footer."""
        newsletter = (
            "# 🔍 LLM DAILY\n## Your Daily Briefing on Large Language Models\n"
            f"**{datetime.now().strftime('%B %d, %Y')}**\n\n"
        )

        highlights = self._generate_introduction(**{f"{k}_section": v for k, v in sections.items()})
        if highlights.strip():
            newsletter += highlights.strip() + "\n\n---\n\n"

        for name in SECTION_ORDER:
            if name in sections:
                newsletter += sections[name].strip() + "\n\n---\n\n"

        newsletter += self._build_footer()
        return newsletter

    def _generate_introduction(self, **sections) -> str:
        """Generate a Highlights section for the newsletter that outlines key insights"""
        
        prompt = """
        You are an expert on large language models and AI technology. Your task is to write a brief, engaging 
        "HIGHLIGHTS" section for an AI/LLM newsletter that outlines the key insights and important developments
        in today's edition. 
        
        The section should start with "# HIGHLIGHTS" and include 3-5 bullet points of the most 
        significant AI developments and insights covered in today's newsletter sections.
        Each bullet point should be concise (1-2 sentences) but specific enough to convey real value.
        
        Make the highlights substantive, insightful and focused on concrete developments rather than
        vague statements. Where appropriate, include specific companies, technologies, or research 
        advancements.
        
        Format each bullet point with a "•" symbol. DO NOT include the sources or statistics information
        in the bullet points themselves.
        
        Base your highlights on the content in the provided newsletter sections, selecting the most 
        important and interesting developments from each section.
        """
        
        user_message = f"""
        Write a "HIGHLIGHTS" section for today's LLM Daily newsletter dated {datetime.now().strftime('%B %d, %Y')}.
        
        Here are the sections from today's newsletter to extract highlights from:
        """
        
        # Add content from each section to the user message
        for section_name, section_key in [
            ("Business", "business_section"),
            ("Products", "products_section"),
            ("Technology", "technology_section"),
            ("Research", "research_section")
        ]:
            if section_key in sections and sections[section_key]:
                # Add a truncated version to avoid overwhelming the context
                section_content = sections[section_key]
                if len(section_content) > 1000:
                    # Truncate but preserve the structure
                    truncated = section_content[:1000] + "...[content truncated]..."
                    user_message += f"\n\n---\n\n{section_name} SECTION:\n{truncated}"
                else:
                    user_message += f"\n\n---\n\n{section_name} SECTION:\n{section_content}"
        
        try:
            highlights = self._make_api_call(prompt, user_message, max_tokens=self.SHORT_MAX_TOKENS)
            return highlights
        except Exception as e:
            print(f"Error generating highlights section, leaving it out: {e}")
            return ""

    def _build_footer(self) -> str:
        """
        Describe how this issue was made: sources, omissions, model and token use.

        Built from recorded facts only; no LLM call.
        """
        report = self.report
        lines = ["## Sources & method", ""]
        if report.get("stats_text"):
            lines.append(report["stats_text"])
            lines.append("")
        if report.get("failed_sources"):
            lines.append(f"Unavailable today: {', '.join(report['failed_sources'])}.")
        omitted = report.get("omitted") or {}
        if omitted:
            parts = [f"{name.capitalize()} ({reason})" for name, reason in omitted.items()]
            lines.append(f"Sections left out: {', '.join(parts)}.")
        if report.get("dropped_items"):
            lines.append(f"{report['dropped_items']} unsourced lines were removed before sending.")
        usage = self.usage
        lines.append(
            f"Written by {self.provider.model} ({self.provider.name}) in {usage['calls']} calls, "
            f"{usage['input_tokens']:,} input and {usage['output_tokens']:,} output tokens."
        )
        lines.append(f"Every item links to its source. Code: {REPO_URL}")
        return "\n".join(lines) + "\n"
