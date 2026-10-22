#!/usr/bin/env python3
"""
Test script for the optimized ArXiv Collector

This script allows testing the arXiv collector with domain-specific queries
independently before integrating into the main newsletter system.
"""

import os
import sys
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the main modules
sys.path.append(str(Path(__file__).parent.parent))

# Import the collector
from llm_daily.collectors.arxiv_collector import ArXivCollector

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test the optimized ArXiv collector")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--results", type=int, default=10, help="Maximum results per query")
    parser.add_argument("--output", type=str, default="arxiv_data_sample.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="arxiv_data_sample.json", help="Output file for raw JSON data")
    parser.add_argument("--no-cache", action="store_true", help="Skip using cache")
    parser.add_argument("--force", action="store_true", help="Force refresh of cache")
    parser.add_argument("--domains", type=str, help="Comma-separated list of domains to query")
    parser.add_argument("--models", type=str, help="Comma-separated list of models to query")
    parser.add_argument("--list-domains", action="store_true", help="List available domains and exit")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument("--output-dir", type=str, default="test_output", help="Directory to save output files")
    return parser.parse_args()

def list_available_domains(collector):
    """List available domain queries"""
    print("\n╔══════════════════════════════════╗")
    print("║        AVAILABLE DOMAINS         ║")
    print("╚══════════════════════════════════╝")
    print()
    for domain, query in collector.domain_queries.items():
        domain_title = domain.replace('_', ' ').title()
        print(f"• {domain}: {domain_title}")
        print(f"  Query: {query}")
        print()
    sys.exit(0)

def list_available_models(collector):
    """List available model queries"""
    print("\n╔══════════════════════════════════╗")
    print("║         AVAILABLE MODELS         ║")
    print("╚══════════════════════════════════╝")
    print()
    for model, query in collector.model_queries.items():
        model_name = model.upper() if model in ['gpt', 'llm'] else model.title() 
        print(f"• {model}: {model_name}")
        print(f"  Query: {query}")
        print()
    sys.exit(0)

def main():
    """Run the ArXiv collector test"""
    # Parse arguments
    args = parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize collector
    collector = ArXivCollector()
    
    # List domains or models if requested
    if args.list_domains:
        list_available_domains(collector)
    
    if args.list_models:
        list_available_models(collector)
    
    # Parse domains and models if provided
    domains = args.domains.split(',') if args.domains else None
    models = args.models.split(',') if args.models else None
    
    # Print configuration info
    print("╔═════════════════════════════════════╗")
    print("║      ARXIV COLLECTOR TEST RUN       ║")
    print("╚═════════════════════════════════════╝\n")
    
    print("Configuration:")
    print(f"• Looking back {args.days} days")
    print(f"• Maximum {args.results} results per query")
    print(f"• {'Force refresh' if args.force else 'Normal mode'}")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    
    if domains:
        print(f"• Domains: {', '.join(domains)}")
    else:
        print("• Domains: [all domains]")
        
    if models:
        print(f"• Models: {', '.join(models)}")
    else:
        print("• Models: [none]")
        
    print("─────────────────────────────────────")
    
    # Run collection
    print("\nCollecting data from arXiv...")
    start_time = time.time()
    
    try:
        # Call the collector with the specified parameters
        formatted_data, raw_data = collector.run(
            days_back=args.days,
            max_results_per_query=args.results,
            use_cache=not args.no_cache,
            force_refresh=args.force,
            domains=domains,
            models=models
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nCollection completed in {duration:.2f} seconds")
        
        # Get paper statistics
        stats = collector.get_statistics(raw_data)
        papers = raw_data.get('papers', [])
        
        # Print statistics
        print("\n╔══════════════════════════════════╗")
        print("║         COLLECTION RESULTS        ║")
        print("╚══════════════════════════════════╝")
        
        # Print paper count
        paper_count = stats['total_papers']
        if paper_count == 0:
            print("\n❌ No papers were collected! Check your queries.")
        elif paper_count < 5:
            print(f"\n⚠️ Only collected {paper_count} papers. Consider broadening queries.")
        else:
            print(f"\n✅ Successfully collected {paper_count} papers:")
        
        print(f"  • Published in last 7 days: {stats['last_week_count']}")
        print(f"  • Published in last 30 days: {stats['last_month_count']}")
        
        # Print domain breakdown
        if stats.get('domain_counts'):
            print("\nPapers by domain:")
            for domain, count in sorted(stats['domain_counts'].items(), key=lambda x: x[1], reverse=True):
                domain_title = domain.replace('_', ' ').title()
                print(f"  • {domain_title}: {count}")
        
        # Print model breakdown
        if stats.get('model_counts'):
            print("\nPapers by model:")
            for model, count in sorted(stats['model_counts'].items(), key=lambda x: x[1], reverse=True):
                model_name = model.upper() if model in ['gpt', 'llm'] else model.title()
                print(f"  • {model_name}: {count}")
        
        # Print category breakdown
        if paper_count > 0:
            print("\nTop categories:")
            for category, count in sorted(stats.get('category_counts', {}).items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  • {category}: {count}")
            
            # Print a few paper titles as examples
            print("\nSample papers:")
            for i, paper in enumerate(papers[:3], 1):
                # Handle potential missing keys gracefully
                title = paper.get('title', 'No title')
                authors = paper.get('authors', [])
                published = paper.get('published', 'Unknown date')
                arxiv_id = paper.get('arxiv_id', 'Unknown ID')
                domain = paper.get('domain', 'general')
                
                # Format sample output
                print(f"  {i}. {title}")
                print(f"     Authors: {', '.join(authors[:3])}{' and others' if len(authors) > 3 else ''}")
                print(f"     Published: {published}")
                print(f"     arXiv ID: {arxiv_id}")
                print(f"     Domain: {domain}")
                print()
        
        # Generate output filenames with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(args.output_dir, f"arxiv_data_{timestamp}.md")
        json_file = os.path.join(args.output_dir, f"arxiv_data_{timestamp}.json")
        
        # Save formatted data to file
        with open(output_file, "w") as f:
            f.write(formatted_data)
        print(f"Formatted data saved to {output_file}")
        
        # Save raw data as JSON
        with open(json_file, "w") as f:
            json.dump(raw_data, f, indent=2)
        print(f"Raw data saved to {json_file}")
        
        print("\n✨ Test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error testing ArXiv collector: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())