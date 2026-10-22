#!/usr/bin/env python3
"""
Test script for running the VentureBeat and TechCrunch collectors

This script allows testing the RSS feed collectors in isolation to verify
they're working properly before integrating them into the main system.
"""

import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the main modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from llm_daily.collectors.venturebeat_collector import VentureBeatCollector
from llm_daily.collectors.techcrunch_collector import TechCrunchCollector

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test VentureBeat and TechCrunch collectors")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    parser.add_argument("--articles", type=int, default=10, help="Maximum number of articles to retrieve")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh of data caches")
    parser.add_argument("--venturebeat-only", action="store_true", help="Test only VentureBeat collector")
    parser.add_argument("--techcrunch-only", action="store_true", help="Test only TechCrunch collector")
    parser.add_argument("--output-dir", type=str, default="test_output", help="Directory to save output files")
    return parser.parse_args()

def main():
    """Run the collector tests"""
    # Parse arguments
    args = parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Testing with: days={args.days}, max_articles={args.articles}, force_refresh={args.force_refresh}")
    
    # Test VentureBeat collector if requested
    if not args.techcrunch_only:
        print("\n" + "="*50)
        print("TESTING VENTUREBEAT COLLECTOR")
        print("="*50)
        
        try:
            # Initialize collector
            collector = VentureBeatCollector()
            
            # Run the collector
            print("\nCollecting VentureBeat articles...")
            formatted_data, raw_data = collector.run(
                days_back=args.days,
                max_articles=args.articles,
                force_refresh=args.force_refresh
            )
            
            # Get statistics
            stats = collector.get_statistics(raw_data)
            
            # Print statistics
            print("\nVentureBeat Collection Results:")
            print(f"- Total articles: {stats['total_articles']}")
            print(f"- Days covered: {stats['days_covered']}")
            print(f"- Articles per day: {stats['articles_per_day']}")
            
            # Print a few article titles
            articles = raw_data.get('articles', [])
            if articles:
                print("\nSample Articles:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"{i}. {article.get('title', 'No Title')}")
                    print(f"   Published: {article.get('published', '').split('T')[0]}")
                    print(f"   Link: {article.get('link', '')}")
                    print()
            
            # Save formatted data to file
            output_file = os.path.join(args.output_dir, f"venturebeat_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(output_file, "w") as f:
                f.write(formatted_data)
            print(f"Formatted data saved to {output_file}")
            
        except Exception as e:
            print(f"Error testing VentureBeat collector: {e}")
    
    # Test TechCrunch collector if requested
    if not args.venturebeat_only:
        print("\n" + "="*50)
        print("TESTING TECHCRUNCH COLLECTOR")
        print("="*50)
        
        try:
            # Initialize collector
            collector = TechCrunchCollector()
            
            # Run the collector
            print("\nCollecting TechCrunch articles...")
            formatted_data, raw_data = collector.run(
                days_back=args.days,
                max_articles=args.articles,
                force_refresh=args.force_refresh
            )
            
            # Get statistics
            stats = collector.get_statistics(raw_data)
            
            # Print statistics
            print("\nTechCrunch Collection Results:")
            print(f"- Total articles: {stats['total_articles']}")
            print(f"- Days covered: {stats['days_covered']}")
            print(f"- Articles per day: {stats['articles_per_day']}")
            
            # Print a few article titles
            articles = raw_data.get('articles', [])
            if articles:
                print("\nSample Articles:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"{i}. {article.get('title', 'No Title')}")
                    print(f"   Published: {article.get('published', '').split('T')[0]}")
                    print(f"   Link: {article.get('link', '')}")
                    print()
            
            # Save formatted data to file
            output_file = os.path.join(args.output_dir, f"techcrunch_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(output_file, "w") as f:
                f.write(formatted_data)
            print(f"Formatted data saved to {output_file}")
            
        except Exception as e:
            print(f"Error testing TechCrunch collector: {e}")
    
    print("\n" + "="*50)
    print("TEST COMPLETED")
    print("="*50)

if __name__ == "__main__":
    main()
