#!/usr/bin/env python3
"""
Test script for the updated NewsletterGenerator with rate limit handling

This script demonstrates the improved content generation process using
a staged approach with delays between API calls to avoid rate limits.

Run with:
python scripts/test_generator.py
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path so we can import modules
sys.path.append(str(Path(__file__).parent.parent))

# Import the updated collector
from llm_daily.generators.newsletter_generator import NewsletterGenerator

def load_cached_data(path, default_name=None):
    """Load cached data file or find most recent one"""
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Try to find most recent file if no specific path
    if default_name:
        data_dir = Path("data/output") / default_name
        if data_dir.exists() and data_dir.is_dir():
            files = list(data_dir.glob("*.md"))
            if files:
                most_recent = max(files, key=os.path.getmtime)
                with open(most_recent, "r", encoding="utf-8") as f:
                    return f.read()
    
    return None

def main():
    """Run the newsletter generator test with staged approach and rate limit handling"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test the updated NewsletterGenerator with rate limit handling")
    parser.add_argument("--reddit-file", help="Path to Reddit data file")
    parser.add_argument("--x-file", help="Path to X/Twitter data file")
    parser.add_argument("--arxiv-file", help="Path to arXiv data file")
    parser.add_argument("--github-file", help="Path to GitHub data file")
    parser.add_argument("--huggingface-file", help="Path to Hugging Face data file")
    parser.add_argument("--producthunt-file", help="Path to Product Hunt data file")
    parser.add_argument("--venturebeat-file", help="Path to VentureBeat data file")
    parser.add_argument("--techcrunch-file", help="Path to TechCrunch data file")
    parser.add_argument("--output", default="staged_newsletter_test.md", help="Output file")
    parser.add_argument("--debug", action="store_true", help="Print debug info about data sizes")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between API calls in seconds (default: 3.0)")
    parser.add_argument("--use-placeholder", action="store_true", help="Use placeholders for missing data")
    args = parser.parse_args()

    print("╔════════════════════════════════════════╗")
    print("║ STAGED NEWSLETTER GENERATOR TEST       ║")
    print("║ WITH RATE LIMIT HANDLING               ║")
    print("╚════════════════════════════════════════╝\n")
    
    # Load environment variables
    load_dotenv()
    
    # Load data from files or find most recent cached files
    reddit_data = load_cached_data(args.reddit_file, "reddit")
    x_data = load_cached_data(args.x_file, "x")
    arxiv_data = load_cached_data(args.arxiv_file, "arxiv")
    github_data = load_cached_data(args.github_file, "github")
    huggingface_data = load_cached_data(args.huggingface_file, "huggingface")
    producthunt_data = load_cached_data(args.producthunt_file, "producthunt")
    venturebeat_data = load_cached_data(args.venturebeat_file, "venturebeat")
    techcrunch_data = load_cached_data(args.techcrunch_file, "techcrunch")
    
    # Check what data we have
    print("Data sources loaded:")
    print(f"• Reddit data: {'✅ Available' if reddit_data else '❌ Not found'}")
    print(f"• X/Twitter data: {'✅ Available' if x_data else '❌ Not found'}")
    print(f"• arXiv data: {'✅ Available' if arxiv_data else '❌ Not found'}")
    print(f"• GitHub data: {'✅ Available' if github_data else '❌ Not found'}")
    print(f"• Hugging Face data: {'✅ Available' if huggingface_data else '❌ Not found'}")
    print(f"• Product Hunt data: {'✅ Available' if producthunt_data else '❌ Not found'}")
    print(f"• VentureBeat data: {'✅ Available' if venturebeat_data else '❌ Not found'}")
    print(f"• TechCrunch data: {'✅ Available' if techcrunch_data else '❌ Not found'}")
    print("─────────────────────────────────────")
    
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
        }
        
        print("\nData sizes (characters):")
        for source, size in data_sizes.items():
            kb_size = size / 1024
            print(f"• {source}: {size:,} chars ({kb_size:.1f} KB)")
        
        total_size = sum(data_sizes.values())
        print(f"• TOTAL: {total_size:,} chars ({total_size/1024:.1f} KB)")
        print("─────────────────────────────────────")
    
    # Initialize the generator
    try:
        generator = NewsletterGenerator()
        
        # Set custom delay between API calls if specified
        if args.delay != 3.0:  # If different from default
            generator.api_call_delay = args.delay
            print(f"Setting API call delay to {args.delay} seconds")
        
    except ValueError as e:
        print(f"❌ Error initializing generator: {e}")
        print("Make sure an LLM key is set: ANTHROPIC_API_KEY, or OPENAI_API_KEY with LLMDAILY_PROVIDER=openai.")
        return 1
    
    print("\nGenerating newsletter with multi-stage approach and rate limit handling...")
    print(f"Delay between API calls: {generator.api_call_delay} seconds")
    print("This may take several minutes as each section is generated separately.")
    start_time = datetime.now()
    
    try:
        # Generate the newsletter using the staged approach
        newsletter = generator.generate_content(
            reddit_data=reddit_data,
            x_data=x_data,
            arxiv_data=arxiv_data,
            github_data=github_data,
            huggingface_data=huggingface_data,
            producthunt_data=producthunt_data,
            venturebeat_data=venturebeat_data,
            techcrunch_data=techcrunch_data,
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if newsletter:
            word_count = len(newsletter.split())
            char_count = len(newsletter)
            
            print("\n✅ Newsletter generation complete!")
            print(f"• Generation time: {duration:.1f} seconds")
            print(f"• Word count: {word_count:,} words")
            print(f"• Character count: {char_count:,} chars")
            
            # Save the newsletter
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(newsletter)
            print(f"• Newsletter saved to: {args.output}")
            
            # Check for section completeness
            required_sections = ["BUSINESS", "PRODUCTS", "TECHNOLOGY", "RESEARCH"]
            found_sections = []
            
            for section in required_sections:
                if f"# {section}" in newsletter:
                    found_sections.append(section)
            
            print(f"• Sections included: {', '.join(found_sections)}")
            missing = set(required_sections) - set(found_sections)
            if missing:
                print(f"⚠️ Missing sections: {', '.join(missing)}")
            else:
                print("• All required sections are present!")
            
            return 0
        else:
            print("❌ Failed to generate newsletter - empty content returned")
            return 1
            
    except Exception as e:
        print(f"❌ Error generating newsletter: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
