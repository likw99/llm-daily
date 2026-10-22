#!/usr/bin/env python3
"""
Test script for the HackerNews collector
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from llm_daily.collectors.hackernews_collector import HackerNewsCollector


def main():
    """Run the HackerNews collector test"""
    
    # Set up argument parser for command-line testing
    parser = argparse.ArgumentParser(description="Test the HackerNewsCollector")
    parser.add_argument("--hours", type=int, default=24, help="Number of hours to look back")
    parser.add_argument("--stories", type=int, default=30, help="Maximum stories per source")
    parser.add_argument("--sources", type=str, default="top,new", help="Comma-separated list of sources (top,new,best)")
    parser.add_argument("--output", type=str, default="hackernews_data_test.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="hackernews_data_test.json", help="Output file for raw JSON data")
    parser.add_argument("--no-cache", action="store_true", help="Force refresh, ignore cache")
    parser.add_argument("--force", action="store_true", help="Force refresh of data")
    
    args = parser.parse_args()
    
    print("╔═══════════════════════════════════════╗")
    print("║     HACKERNEWS COLLECTOR TEST RUN     ║")
    print("╚═══════════════════════════════════════╝\n")
    
    # Load environment variables
    load_dotenv()
    
    # Parse sources
    sources = args.sources.split(',') if args.sources else ['top', 'new']
    
    # Configuration info
    print("Configuration:")
    print(f"• Looking back {args.hours} hours")
    print(f"• Maximum {args.stories} stories per source")
    print(f"• Sources: {', '.join(sources)}")
    print(f"• {'Force refresh' if args.force else 'Normal mode'}")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    print("─────────────────────────────────────")
    
    # Initialize collector
    collector = HackerNewsCollector()
    
    # Run the collector
    print("\nCollecting HackerNews stories...")
    start_time = datetime.now()
    
    try:
        # Call the collector with the specified parameters
        formatted_data, raw_data = collector.run(
            hours_back=args.hours,
            max_stories=args.stories,
            story_sources=sources,
            use_cache=not args.no_cache,
            force_refresh=args.force
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\nCollection completed in {duration:.2f} seconds")
        
        # Get story statistics
        stories = raw_data.get('stories', [])
        total_collected = raw_data.get('total_collected', 0)
        ai_stories_count = raw_data.get('ai_stories_count', 0)
        
        # Print summary statistics
        print("\nCollection Results:")
        print(f"• Total stories found: {len(stories)}")
        print(f"• Total stories before AI filtering: {total_collected}")
        print(f"• AI relevance ratio: {ai_stories_count / max(total_collected, 1):.2%}")
        
        # Get stats from the collector
        stats = collector.get_statistics(raw_data)
        print(f"• Recent stories (last 12h): {stats['recent_stories']}")
        print(f"• Average score: {stats['avg_score']:.1f}")
        print(f"• Average comments: {stats['avg_comments']:.1f}")
        print(f"• Top story score: {stats['top_story_score']}")
        print(f"• Sources used: {', '.join(stats['sources'])}")
        print(f"• AI relevance ratio: {stats.get('ai_relevance_ratio', 0):.2%}")
        
        # Show top stories
        if stories:
            print("\nTop 3 Stories by Score:")
            sorted_stories = sorted(stories, key=lambda x: x.get('score', 0), reverse=True)
            for i, story in enumerate(sorted_stories[:3], 1):
                score = story.get('score', 0)
                comments = story.get('descendants', 0)
                title = story.get('title', 'No title')
                # Truncate title if too long
                if len(title) > 70:
                    title = title[:67] + "..."
                print(f"  {i}. {title}")
                print(f"     Score: {score}, Comments: {comments}")
            
            print("\nMost Recent Stories:")
            # Sort by time (most recent first)
            recent_stories = sorted(stories, key=lambda x: x.get('time', 0), reverse=True)
            for i, story in enumerate(recent_stories[:3], 1):
                story_time = datetime.fromtimestamp(story.get('time', 0))
                hours_ago = (datetime.now() - story_time).total_seconds() / 3600
                title = story.get('title', 'No title')
                if len(title) > 70:
                    title = title[:67] + "..."
                print(f"  {i}. {title}")
                print(f"     {hours_ago:.1f} hours ago")
        
        # Save outputs
        print("\nSaving outputs...")
        
        # Save formatted output
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(formatted_data)
        print(f"• Formatted data saved to: {args.output}")
        
        # Save raw JSON data
        import json
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"• Raw JSON data saved to: {args.json}")
        
        # Success message
        if len(stories) == 0:
            print("\n❌ No AI-related stories found! You might want to:")
            print("   - Increase the time window (--hours)")
            print("   - Check if HackerNews has AI content today")
            print("   - Verify the AI keywords are appropriate")
        elif len(stories) < 5:
            print(f"\n⚠️  Only found {len(stories)} AI-related stories.")
            print("   Consider increasing the time window or checking more sources.")
        else:
            print(f"\n✅ Successfully collected {len(stories)} AI-related stories!")
            print("   Data is ready for newsletter generation.")
            
    except Exception as e:
        print(f"\n❌ Error during collection: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
