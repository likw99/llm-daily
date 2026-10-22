#!/usr/bin/env python3
"""
Test script for the optimized Hugging Face Collector.

This script tests the HuggingFaceCollector class by fetching trending
models, datasets, and spaces from Hugging Face Hub using the trendingScore parameter.
"""

import os
import sys
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the collector
sys.path.append(str(Path(__file__).parent.parent))

# Import the collector
try:
    from llm_daily.collectors.huggingface_collector import HuggingFaceCollector, DateTimeEncoder
    print("Successfully imported HuggingFaceCollector")
except ImportError as e:
    print(f"Error importing HuggingFaceCollector: {e}")
    sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test the Hugging Face Collector")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--models", type=int, default=20, help="Maximum number of models to retrieve")
    parser.add_argument("--datasets", type=int, default=10, help="Maximum number of datasets to retrieve")
    parser.add_argument("--spaces", type=int, default=10, help="Maximum number of spaces to retrieve")
    parser.add_argument("--no-cache", action="store_true", help="Skip using cache")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh of cache")
    parser.add_argument("--output-dir", type=str, default="test_output", help="Directory to save output files")
    parser.add_argument("--sort", type=str, default="trendingScore", 
                        help="Sort option (trendingScore, likes, downloads, lastModified)")
    return parser.parse_args()

def main():
    """Run the Hugging Face collector test"""
    print("Starting Hugging Face collector test...")
    
    # Parse arguments
    args = parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Check if HF_TOKEN is set
    if not os.environ.get("HF_TOKEN"):
        print("Warning: HF_TOKEN environment variable is not set. Some API features may be limited.")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    print("╔═════════════════════════════════════╗")
    print("║   HUGGING FACE COLLECTOR TEST RUN   ║")
    print("╚═════════════════════════════════════╝\n")
    
    print("Configuration:")
    print(f"• Looking back {args.days} days")
    print(f"• Maximum {args.models} models")
    print(f"• Maximum {args.datasets} datasets")
    print(f"• Maximum {args.spaces} spaces")
    print(f"• Sort option: {args.sort}")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    print(f"• {'Force refresh' if args.force_refresh else 'Normal mode'}")
    print("─────────────────────────────────────")
    
    # Initialize the collector
    collector = HuggingFaceCollector()
    
    # Directly call collect_data and format_for_llm instead of run()
    print("\nCollecting data from Hugging Face Hub...")
    start_time = time.time()
    
    try:
        # Manually collect the data and format it
        raw_data = collector.collect_data(
            days_back=args.days,
            model_limit=args.models,
            dataset_limit=args.datasets,
            space_limit=args.spaces,
            use_cache=not args.no_cache,
            force_refresh=args.force_refresh,
            sort_option=args.sort
        )
        
        formatted_data = collector.format_for_llm(raw_data)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nCollection completed in {duration:.2f} seconds")
        
        # Get statistics
        stats = collector.get_statistics(raw_data)
        
        # Print summary statistics
        print("\nCollection Results:")
        print(f"• Total models found: {stats['total_models']}")
        print(f"• Total datasets found: {stats['total_datasets']}")
        print(f"• Total spaces found: {stats['total_spaces']}")
        
        if stats.get('top_authors'):
            print("\nTop authors:")
            for author in stats['top_authors'][:5]:
                print(f"  • {author}")
        
        if stats.get('top_tags'):
            print("\nTop tags:")
            for tag in stats['top_tags'][:5]:
                print(f"  • {tag}")
        
        # Save formatted data to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(args.output_dir, f"huggingface_data_{timestamp}.md")
        with open(output_file, "w") as f:
            f.write(formatted_data)
        print(f"\nFormatted data saved to {output_file}")
        
        # Save raw data as JSON
        json_file = os.path.join(args.output_dir, f"huggingface_data_{timestamp}.json")
        with open(json_file, "w") as f:
            json.dump(raw_data, f, indent=2, cls=DateTimeEncoder)
        print(f"Raw data saved to {json_file}")
        
        # Print some sample model info
        models = raw_data.get('models', [])
        if models:
            print("\nSample models:")
            for i, model in enumerate(models[:3], 1):
                print(f"  {i}. {model.get('id', 'Unknown ID')}")
                print(f"     Likes: {model.get('likes', 'N/A')}")
                if model.get('readme_excerpt'):
                    excerpt = model.get('readme_excerpt', '')[:100].replace('\n', ' ')
                    print(f"     Description: {excerpt}...")
                print()
        
        print("\n✓ Test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error running Hugging Face collector: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"Unhandled exception in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)