import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from .collectors.reddit_collector import RedditCollector
from .collectors.arxiv_collector import ArXivCollector
from .collectors.github_collector import GitHubCollector
from .collectors.huggingface_collector import HuggingFaceCollector
from .collectors.producthunt_collector import ProductHuntCollector
from .collectors.venturebeat_collector import VentureBeatCollector
from .collectors.techcrunch_collector import TechCrunchCollector
from .collectors.sequoia_collector import SequoiaCollector
from .generators.newsletter_generator import NewsletterGenerator
from .generators.translator import translate_to_chinese
from .llm import get_provider
from .llm.stub import StubProvider
from .utils.common import get_project_root, save_output
from .publishers.archive import ArchivePublisher
from .publishers.base import Issue
from .publishers.registry import publish_all, selected_names
from .site import build_site

logger = logging.getLogger("llm_daily")

def _save(content: str, filename: str, output_dir: Optional[Path]) -> str:
    """Save to data/output, or to a dry-run folder."""
    if output_dir is None:
        return save_output(content, filename=filename)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def _issue_meta(generator: NewsletterGenerator, translation, args) -> dict:
    """Facts about this run, stored next to the issue in the archive."""
    report = generator.report
    meta = {
        "provider": generator.provider.name,
        "model": generator.provider.model,
        "llm_calls": generator.usage["calls"],
        "input_tokens": generator.usage["input_tokens"],
        "output_tokens": generator.usage["output_tokens"],
        "sections": report.get("sections", []),
        "sections_omitted": report.get("omitted", {}),
        "sources_unavailable": report.get("failed_sources", []),
        "unsourced_lines_removed": report.get("dropped_items", 0),
        "languages": ["en"] + (["zh"] if translation else []),
        "dry_run": bool(args.dry_run),
    }
    if translation:
        meta["translation_tokens"] = {
            "input": translation.usage.input_tokens,
            "output": translation.usage.output_tokens,
        }
        meta["translation_links_match"] = translation.links_match
    return meta


def _setup_logging():
    """Log to stdout and to a dated file in the current directory."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f"llm_daily_{datetime.now().strftime('%Y-%m-%d')}.log", encoding="utf-8"),
        ],
    )


def parse_args(argv=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(prog="llm-daily", description="LLM Daily - open-source AI newsletter agent")
    parser.add_argument("--skip-reddit", action="store_true", help="Skip Reddit data collection")
    parser.add_argument("--skip-x", action="store_true", help="Skip X/Twitter data collection")
    parser.add_argument("--skip-arxiv", action="store_true", help="Skip arXiv data collection")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub data collection")
    parser.add_argument("--skip-huggingface", action="store_true", help="Skip Hugging Face data collection")
    parser.add_argument("--no-publish", action="store_true", help="Skip publishing to Buttondown")
    parser.add_argument("--output-dir", type=str, help="Custom output directory for newsletter files")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh of data caches")
    parser.add_argument("--arxiv-days", type=int, default=7, help="Number of days to look back for arXiv papers (default: 7)")
    parser.add_argument("--arxiv-results", type=int, default=50, help="Maximum number of arXiv results to retrieve (default: 50)")
    parser.add_argument("--github-days", type=int, default=30, help="Number of days to look back for GitHub repos")
    parser.add_argument("--huggingface-days", type=int, default=14, help="Number of days to look back for Hugging Face content")
    parser.add_argument("--huggingface-limit", type=int, default=30, help="Maximum number of Hugging Face items per category")
    parser.add_argument("--huggingface-sort", type=str, default="trendingScore", help="Sort option for Hugging Face content (trendingScore, likes, downloads, lastModified)")
    parser.add_argument("--skip-producthunt", action="store_true", help="Skip Product Hunt data collection")
    parser.add_argument("--producthunt-days", type=int, default=7, help="Number of days to look back for Product Hunt products")
    parser.add_argument("--producthunt-limit", type=int, default=50, help="Maximum number of Product Hunt products to retrieve")
    parser.add_argument("--skip-venturebeat", action="store_true", help="Skip VentureBeat data collection")
    parser.add_argument("--skip-techcrunch", action="store_true", help="Skip TechCrunch data collection")
    parser.add_argument("--news-days", type=int, default=7, help="Number of days to look back for tech news")
    parser.add_argument("--skip-sequoia", action="store_true", help="Skip Sequoia Capital data collection")
    parser.add_argument("--sequoia-days", type=int, default=7, help="Number of days to look back for Sequoia content")
    parser.add_argument("--sequoia-articles", type=int, default=15, help="Maximum number of Sequoia articles to retrieve")
    parser.add_argument("--debug", action="store_true", help="Print debug info about data sizes")
    parser.add_argument("--provider", type=str, help="LLM provider: anthropic (default) or openai (any OpenAI-compatible API). Overrides LLMDAILY_PROVIDER")
    parser.add_argument("--model", type=str, help="Model name. Overrides LLMDAILY_MODEL")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run offline with example data and a stub model; writes to data/dry-run/ and builds a site there")
    parser.add_argument("--publishers", type=str,
                        help="Comma-separated publishers (archive, buttondown, kit, telegram, webhook). Overrides LLMDAILY_PUBLISHERS")
    parser.add_argument("--lang", choices=["en", "zh", "both"], default=os.environ.get("LLMDAILY_LANG", "en"),
                        help="Editions to write: en (default), zh (Simplified Chinese) or both. Overrides LLMDAILY_LANG")
    return parser.parse_args(argv)


def main(argv=None):
    """Main function to run the newsletter pipeline"""
    start_time = datetime.now()
    # Parse command line arguments first so --help works without any setup
    args = parse_args(argv)
    _setup_logging()
    logger.info(f"Starting LLM Daily generation at {start_time}")

    # Load environment variables from .env in the project root (if present)
    load_dotenv(dotenv_path=get_project_root() / '.env')

    if args.dry_run:
        logger.info("Dry run: using example data from llm_daily/fixtures and the offline stub model")
        for flag in ("reddit", "x", "arxiv", "github", "huggingface", "producthunt",
                     "venturebeat", "techcrunch", "sequoia"):
            setattr(args, f"skip_{flag}", True)
    
    # Initialize data variables
    reddit_data = None
    reddit_stats = None
    x_data = None
    x_stats = None
    arxiv_data = None
    arxiv_stats = None
    github_data = None
    github_stats = None
    huggingface_data = None
    huggingface_stats = None
    producthunt_data = None
    producthunt_stats = None
    venturebeat_data = None
    venturebeat_stats = None
    techcrunch_data = None
    techcrunch_stats = None
    sequoia_data = None
    sequoia_stats = None
    
    # Collect Reddit data
    if not args.skip_reddit:
        logger.info("Collecting Reddit data...")
        try:
            collector = RedditCollector()
            reddit_formatted_data, reddit_raw_data = collector.run(time_period=48, limit=7)
            reddit_data = reddit_formatted_data
            reddit_stats = collector.get_statistics(reddit_raw_data)
            
            # Save raw Reddit data for reference
            reddit_data_file = save_output(
                reddit_formatted_data, 
                filename=f"reddit_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="reddit"
            )
            logger.info(f"Reddit data saved to {reddit_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting Reddit data: {str(e)}", exc_info=True)
            logger.warning("Continuing without Reddit data...")
    
    # Collect X/Twitter data
    if not args.skip_x:
        logger.info("Collecting X/Twitter data...")
        try:
            # Check for required X Bearer Token
            if not os.environ.get("X_BEARER_TOKEN"):
                logger.error("X_BEARER_TOKEN environment variable not set. Skipping X/Twitter data collection.")
            else:
                from .collectors.x_collector import XCollector

                collector = XCollector()
                x_formatted_data, x_raw_data = collector.run(
                    hours_back=48, 
                    max_results=100,
                    force_refresh=args.force_refresh
                )
                x_data = x_formatted_data
                x_stats = collector.get_statistics(x_raw_data)
                
                # Check if we hit rate limits and are using cache
                if x_stats.get("rate_limited", False):
                    logger.warning("X/Twitter API rate limit reached. Using cached data.")
                elif x_stats.get("from_cache", False):
                    logger.info("Using cached X/Twitter data.")
                
                # Save raw X/Twitter data for reference
                x_data_file = save_output(
                    x_formatted_data, 
                    filename=f"x_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                    subfolder="x"
                )
                logger.info(f"X/Twitter data saved to {x_data_file}")
        except Exception as e:
            logger.error(f"Error collecting X/Twitter data: {str(e)}", exc_info=True)
            logger.warning("Continuing without X/Twitter data...")
    
    # Collect arXiv data
    if not args.skip_arxiv:
        logger.info(f"Collecting arXiv data (looking back {args.arxiv_days} days)...")
        try:
            collector = ArXivCollector()
            arxiv_formatted_data, arxiv_raw_data = collector.run(
                days_back=args.arxiv_days, 
                max_results=args.arxiv_results,
                force_refresh=args.force_refresh
            )
            arxiv_data = arxiv_formatted_data
            arxiv_stats = collector.get_statistics(arxiv_raw_data)
            
            # Log information about the recency of papers
            today_count = arxiv_stats.get('today_count', 0)
            yesterday_count = arxiv_stats.get('yesterday_count', 0)
            last_3days_count = arxiv_stats.get('last_3days_count', 0)
            last_week_count = arxiv_stats.get('last_week_count', 0)
            
            logger.info("arXiv paper counts by recency:")
            logger.info(f"- Today: {today_count}")
            logger.info(f"- Yesterday: {yesterday_count}")
            logger.info(f"- Last 3 days: {last_3days_count}")
            logger.info(f"- Last week: {last_week_count}")
            logger.info(f"- Total papers: {arxiv_stats.get('total_papers', 0)}")
            
            # Save raw arXiv data for reference
            arxiv_data_file = save_output(
                arxiv_formatted_data, 
                filename=f"arxiv_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="arxiv"
            )
            logger.info(f"arXiv data saved to {arxiv_data_file}")
                
        except Exception as e:
            logger.error(f"Error collecting arXiv data: {str(e)}", exc_info=True)
            logger.warning("Continuing without arXiv data...")
    
    # Collect GitHub data
    if not args.skip_github:
        logger.info("Collecting GitHub trending data...")
        try:
            collector = GitHubCollector()
            github_formatted_data, github_raw_data = collector.run(
                days_back=args.github_days,
                per_page=50,
                force_refresh=args.force_refresh
            )
            github_data = github_formatted_data
            github_stats = collector.get_statistics(github_raw_data)

            # Log GitHub collection statistics
            repo_count = github_stats.get('total_repos', 0)
            trending_count = github_stats.get('trending_count', 0)
            api_count = github_stats.get('api_count', 0)
            
            logger.info(f"Collected {repo_count} GitHub repositories:")
            logger.info(f"- From trending pages: {trending_count}")
            logger.info(f"- From API fallback: {api_count}")

            # Save raw GitHub data for reference
            github_data_file = save_output(
                github_formatted_data, 
                filename=f"github_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="github"
            )
            logger.info(f"GitHub data saved to {github_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting GitHub data: {str(e)}", exc_info=True)
            logger.warning("Continuing without GitHub data...")
    
    # Collect Hugging Face data
    if not args.skip_huggingface:
        logger.info("Collecting Hugging Face trending data...")
        try:
            collector = HuggingFaceCollector()
            huggingface_formatted_data, huggingface_raw_data = collector.run(
                days_back=args.huggingface_days,
                model_limit=args.huggingface_limit,
                dataset_limit=args.huggingface_limit // 2,  # Half as many datasets as models
                space_limit=args.huggingface_limit // 2,     # Half as many spaces as models
                force_refresh=args.force_refresh,
                sort_option=args.huggingface_sort  # Use specified sort option
            )
            huggingface_data = huggingface_formatted_data
            huggingface_stats = collector.get_statistics(huggingface_raw_data)
            
            # Log information about what was collected
            logger.info("Hugging Face collection statistics:")
            logger.info(f"- Models: {huggingface_stats.get('total_models', 0)}")
            logger.info(f"- Datasets: {huggingface_stats.get('total_datasets', 0)}")
            logger.info(f"- Spaces: {huggingface_stats.get('total_spaces', 0)}")
            logger.info(f"- Sort option: {huggingface_stats.get('sort_option', 'trendingScore')}")
            
            # Save raw Hugging Face data for reference
            huggingface_data_file = save_output(
                huggingface_formatted_data, 
                filename=f"huggingface_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="huggingface"
            )
            logger.info(f"Hugging Face data saved to {huggingface_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting Hugging Face data: {str(e)}", exc_info=True)
            logger.warning("Continuing without Hugging Face data...")
            
    # Collect Product Hunt data
    if not args.skip_producthunt:
        logger.info("Collecting Product Hunt data...")
        try:
            collector = ProductHuntCollector()
            producthunt_formatted_data, producthunt_raw_data = collector.run(
                days_back=args.producthunt_days,
                posts_limit=args.producthunt_limit,
                force_refresh=args.force_refresh
            )
            producthunt_data = producthunt_formatted_data
            producthunt_stats = collector.get_statistics(producthunt_raw_data)
            
            # Save raw Product Hunt data for reference
            producthunt_data_file = save_output(
                producthunt_formatted_data, 
                filename=f"producthunt_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="producthunt"
            )
            logger.info(f"Product Hunt data saved to {producthunt_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting Product Hunt data: {str(e)}", exc_info=True)
            logger.warning("Continuing without Product Hunt data...")

    if not args.skip_venturebeat:
        logger.info("Collecting VentureBeat AI news...")
        try:
            collector = VentureBeatCollector()
            venturebeat_formatted_data, venturebeat_raw_data = collector.run(
                days_back=args.news_days,
                force_refresh=args.force_refresh
            )
            venturebeat_data = venturebeat_formatted_data
            venturebeat_stats = collector.get_statistics(venturebeat_raw_data)
            
            # Save raw VentureBeat data for reference
            venturebeat_data_file = save_output(
                venturebeat_formatted_data, 
                filename=f"venturebeat_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="venturebeat"
            )
            logger.info(f"VentureBeat data saved to {venturebeat_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting VentureBeat data: {str(e)}", exc_info=True)
            logger.warning("Continuing without VentureBeat data...")

    if not args.skip_techcrunch:
        logger.info("Collecting TechCrunch AI news...")
        try:
            collector = TechCrunchCollector()
            techcrunch_formatted_data, techcrunch_raw_data = collector.run(
                days_back=args.news_days,
                force_refresh=args.force_refresh
            )
            techcrunch_data = techcrunch_formatted_data
            techcrunch_stats = collector.get_statistics(techcrunch_raw_data)
            
            # Save raw TechCrunch data for reference
            techcrunch_data_file = save_output(
                techcrunch_formatted_data, 
                filename=f"techcrunch_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="techcrunch"
            )
            logger.info(f"TechCrunch data saved to {techcrunch_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting TechCrunch data: {str(e)}", exc_info=True)
            logger.warning("Continuing without TechCrunch data...")

    # Collect Sequoia Capital data
    if not args.skip_sequoia:
        logger.info("Collecting Sequoia Capital insights...")
        try:
            collector = SequoiaCollector()
            sequoia_formatted_data, sequoia_raw_data = collector.run(
                days_back=args.sequoia_days,
                max_articles=args.sequoia_articles,
                force_refresh=args.force_refresh
            )
            sequoia_data = sequoia_formatted_data
            sequoia_stats = collector.get_statistics(sequoia_raw_data)
            
            # Save raw Sequoia data for reference
            sequoia_data_file = save_output(
                sequoia_formatted_data, 
                filename=f"sequoia_data_{datetime.now().strftime('%Y-%m-%d')}.md",
                subfolder="sequoia"
            )
            logger.info(f"Sequoia data saved to {sequoia_data_file}")
            
        except Exception as e:
            logger.error(f"Error collecting Sequoia data: {str(e)}", exc_info=True)
            logger.warning("Continuing without Sequoia data...")

    # Debug data sizes if requested
    if args.debug:
        data_sizes = {
            "Reddit": len(reddit_data) if reddit_data else 0,
            "X/Twitter": len(x_data) if x_data else 0,
            "arXiv": len(arxiv_data) if arxiv_data else 0,
            "GitHub": len(github_data) if github_data else 0,
            "Hugging Face": len(huggingface_data) if huggingface_data else 0,
            "Product Hunt": len(producthunt_data) if producthunt_data else 0,
            "VentureBeat": len(venturebeat_data) if venturebeat_data else 0,
            "TechCrunch": len(techcrunch_data) if techcrunch_data else 0,
            "Sequoia": len(sequoia_data) if sequoia_data else 0
        }
        
        logger.info("Data sizes (characters):")
        for source, size in data_sizes.items():
            kb_size = size / 1024
            logger.info(f"{source}: {size:,} chars ({kb_size:.1f} KB)")
        
        total_size = sum(data_sizes.values())
        logger.info(f"TOTAL: {total_size:,} chars ({total_size/1024:.1f} KB)")

    if args.dry_run:
        fixtures = Path(__file__).parent / "fixtures"
        venturebeat_data = (fixtures / "venturebeat.md").read_text(encoding="utf-8")
        producthunt_data = (fixtures / "producthunt.md").read_text(encoding="utf-8")
        github_data = (fixtures / "github.md").read_text(encoding="utf-8")
        arxiv_data = (fixtures / "arxiv.md").read_text(encoding="utf-8")

    # Sources that were enabled but produced nothing are reported in the issue footer
    failed_sources = [
        name for name, skipped, data in [
            ("Reddit", args.skip_reddit, reddit_data),
            ("X", args.skip_x, x_data),
            ("arXiv", args.skip_arxiv, arxiv_data),
            ("GitHub", args.skip_github, github_data),
            ("Hugging Face", args.skip_huggingface, huggingface_data),
            ("Product Hunt", args.skip_producthunt, producthunt_data),
            ("VentureBeat", args.skip_venturebeat, venturebeat_data),
            ("TechCrunch", args.skip_techcrunch, techcrunch_data),
            ("Sequoia", args.skip_sequoia, sequoia_data),
        ]
        if not skipped and not data
    ]
    if failed_sources:
        logger.warning(f"No data today from: {', '.join(failed_sources)}")

    # Generate newsletter content using the multi-stage approach
    logger.info("Generating newsletter content with multi-stage approach...")
    try:
        provider = StubProvider() if args.dry_run else get_provider(args.provider, args.model)
        generator = NewsletterGenerator(provider=provider)
        logger.info(f"Using LLM provider '{generator.provider.name}' with model '{generator.provider.model}'")
        content = generator.generate_content(
            reddit_data=reddit_data, 
            reddit_stats=reddit_stats,
            x_data=x_data,
            x_stats=x_stats,
            arxiv_data=arxiv_data,
            arxiv_stats=arxiv_stats,
            github_data=github_data,
            github_stats=github_stats,
            huggingface_data=huggingface_data,
            huggingface_stats=huggingface_stats,
            producthunt_data=producthunt_data,
            producthunt_stats=producthunt_stats,
            venturebeat_data=venturebeat_data,
            venturebeat_stats=venturebeat_stats,
            techcrunch_data=techcrunch_data,
            techcrunch_stats=techcrunch_stats,
            sequoia_data=sequoia_data,
            sequoia_stats=sequoia_stats,
            failed_sources=failed_sources,
        )
        
        usage = generator.usage
        logger.info(
            f"LLM usage: {usage['calls']} calls, {usage['input_tokens']:,} input tokens, "
            f"{usage['output_tokens']:,} output tokens"
        )

        if not content:
            logger.error("No section had content today; nothing will be saved or published")
            return 1
            
    except Exception as e:
        logger.error(f"Error generating newsletter: {str(e)}", exc_info=True)
        return 1
    
    # Validate and clean content
    try:
        # Ensure content has a title
        if not content.strip().startswith("#"):
            logger.warning("Newsletter content doesn't start with a title. Adding one.")
            today = datetime.now().strftime('%B %d, %Y')
            content = f"# 🔍 LLM DAILY\n## Your Daily Briefing on Large Language Models\n**{today}**\n\n{content}"
        
        # Ensure content has a date
        if datetime.now().strftime('%Y') not in content:
            logger.warning("Newsletter content doesn't include current year. Adding date.")
            today = datetime.now().strftime('%B %d, %Y')
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith("# "):
                    lines.insert(i+1, f"**{today}**\n")
                    break
            content = '\n'.join(lines)
    except Exception as e:
        logger.warning(f"Error during content validation: {str(e)}")
        # Continue anyway since this isn't critical
    
    root = get_project_root()
    output_dir = root / "data" / "dry-run" if args.dry_run else None
    today = datetime.now()

    # Save newsletter content locally
    try:
        output_file = _save(content, f"llm_newsletter_{today:%Y-%m-%d}.md", output_dir)
        logger.info(f"Newsletter saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving newsletter: {str(e)}", exc_info=True)
        return 1

    # Chinese edition
    content_zh = None
    translation = None
    if args.lang in ("zh", "both"):
        logger.info("Translating the issue into Simplified Chinese...")
        try:
            translation = translate_to_chinese(content, generator.provider)
            content_zh = translation.text
            zh_file = _save(content_zh, f"llm_newsletter_{today:%Y-%m-%d}.zh.md", output_dir)
            logger.info(
                f"Chinese edition saved to {zh_file} ({translation.usage.input_tokens:,} input / "
                f"{translation.usage.output_tokens:,} output tokens, {translation.links_out}/{translation.links_in} links)"
            )
        except Exception as e:
            logger.error(f"Chinese translation failed, continuing with English only: {e}", exc_info=True)

    issue = Issue(
        day=today.date(),
        markdown=content_zh if (args.lang == "zh" and content_zh) else content,
        markdown_en=content,
        markdown_zh=content_zh,
        meta=_issue_meta(generator, translation, args),
        site_url=os.environ.get("LLMDAILY_SITE_URL") or None,
    )

    # Publish
    try:
        if args.dry_run:
            names = ["archive"]
        else:
            names = selected_names(args.publishers, no_publish=args.no_publish)
    except ValueError as e:
        logger.error(str(e))
        return 1
    overrides = {"archive": ArchivePublisher(output_dir / "archive")} if args.dry_run else None
    logger.info(f"Publishers: {', '.join(names) or 'none'}")
    results = publish_all(issue, names, overrides=overrides)

    if args.dry_run:
        count = build_site(output_dir / "archive", output_dir / "site")
        logger.info(f"Dry run complete: archive and a {count}-issue site are in {output_dir}")

    failed = [name for name, result in results.items() if not result["ok"]]
    if failed:
        logger.error(f"Publishing failed for: {', '.join(failed)}")
        return 2

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    logger.info(f"LLM Daily generation completed in {runtime:.2f} seconds")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
