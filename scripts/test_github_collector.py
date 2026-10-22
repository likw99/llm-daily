#!/usr/bin/env python3
"""
Test script for the updated GitHub collector

This script tests the new language-specific GitHub collector that
focuses on Jupyter Notebook, Python, and TypeScript trending pages.
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path to import modules
sys.path.append(str(Path(__file__).parent.parent))

# Import the collector
from llm_daily.collectors.github_collector import GitHubCollector

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test the updated GitHub collector")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    parser.add_argument("--limit", type=int, default=25, help="Maximum repositories to retrieve")
    parser.add_argument("--force", action="store_true", help="Force refresh of cache")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cache")
    parser.add_argument("--output", type=str, default="github_test_output.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="github_test_output.json", help="Output file for raw JSON data")
    return parser.parse_args()

def test_github_collector():
    """Test the updated GitHub collector"""
    
    # Parse arguments
    args = parse_args()
    
    print("╔═════════════════════════════════════╗")
    print("║     UPDATED GITHUB COLLECTOR TEST   ║")
    print("╚═════════════════════════════════════╝\n")
    
    # Load environment variables (to get GitHub token if available)
    load_dotenv()
    
    # Initialize collector
    collector = GitHubCollector()
    
    # Check if GitHub token is available
    if os.environ.get("GITHUB_TOKEN"):
        print("✅ GitHub token found in environment variables")
    else:
        print("⚠️ No GitHub token found. API fallback will be limited to avoid rate limits.")
    
    # Print configuration
    print("\nTest Configuration:")
    print(f"• Looking back {args.days} days")
    print(f"• Maximum {args.limit} repositories")
    print(f"• {'Force refresh' if args.force else 'Normal mode'}")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    print("─────────────────────────────────────")
    
    # Run collection
    start_time = time.time()
    print("\nRunning GitHub collector...")
    
    try:
        # Call the collector with the specified parameters
        formatted_data, raw_data = collector.run(
            days_back=args.days,
            per_page=args.limit,
            use_cache=not args.no_cache,
            force_refresh=args.force
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nCollection completed in {duration:.2f} seconds")
        
        # Get repository statistics
        repositories = raw_data.get('repositories', [])
        
        # Print summary statistics
        print("\nCollection Results:")
        print(f"• Total repositories found: {len(repositories)}")
        print(f"• From trending page: {raw_data.get('trending_count', 0)}")
        print(f"• From API search: {raw_data.get('api_count', 0)}")
        
        # Print language distribution
        languages = {}
        for repo in repositories:
            lang = repo.get('language')
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        
        if languages:
            print("\nLanguage distribution:")
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"• {lang}: {count}")
        
        # Print top topics if available
        topics_count = {}
        for repo in repositories:
            for topic in repo.get('topics', []):
                if topic not in topics_count:
                    topics_count[topic] = 0
                topics_count[topic] += 1
        
        if topics_count:
            print("\nTop topics:")
            for topic, count in sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"• {topic}: {count}")
        
        # Print top repositories
        if repositories:
            print("\nTop 5 repositories by stars:")
            sorted_repos = sorted(repositories, key=lambda x: x.get('stargazers_count', 0), reverse=True)[:5]
            for i, repo in enumerate(sorted_repos, 1):
                print(f"{i}. {repo.get('full_name', '')} - {repo.get('stargazers_count', 0)} stars")
                if repo.get('description'):
                    desc = repo.get('description')
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    print(f"   {desc}")
        
        # Save formatted data to file
        with open(args.output, "w") as f:
            f.write(formatted_data)
        print(f"\nFormatted data saved to {args.output}")
        
        # Save raw data to JSON file
        with open(args.json, "w") as f:
            json.dump(raw_data, f, indent=2)
        print(f"Raw data saved to {args.json}")
        
        print("\n✅ Test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error testing GitHub collector: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_github_collector())