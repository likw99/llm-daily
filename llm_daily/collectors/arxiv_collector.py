import os
import json
import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set

from .base_collector import BaseCollector

class ArXivCollector(BaseCollector):
    """Collector for arXiv research papers related to LLMs with domain-specific queries"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the arXiv collector
        
        Args:
            cache_dir: Directory for caching results (optional)
        """
        # API base URL
        self.base_url = "http://export.arxiv.org/api/query"
        
        # XML namespace for parsing
        self.namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "arxiv"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Predefined domain-specific queries for LLM research
        self.domain_queries = {
            "transformers": "abs:\"transformer architecture\" AND (abs:\"large language model\" OR abs:LLM)",
            "reasoning": "abs:reasoning AND (abs:\"large language model\" OR abs:LLM)",
            "multimodal": "(abs:\"multimodal\" OR abs:\"multi-modal\") AND (abs:\"large language model\" OR abs:LLM)",
            "fine-tuning": "(abs:\"fine-tuning\" OR abs:\"finetuning\" OR abs:\"fine tune\") AND (abs:\"large language model\" OR abs:LLM)",
            "world_models": "(abs:\"world model\" OR abs:\"world modeling\") AND (abs:\"large language model\" OR abs:LLM)",
            "agents": "abs:agent AND (abs:\"large language model\" OR abs:LLM) AND NOT abs:\"software agent\"",
            "reinforcement_learning": "(abs:\"reinforcement learning\" OR abs:RLHF OR abs:\"RL\") AND (abs:\"large language model\" OR abs:LLM)",
            "efficiency": "(abs:\"efficient\" OR abs:\"efficiency\" OR abs:\"quantization\" OR abs:\"pruning\") AND (abs:\"large language model\" OR abs:LLM)",
            "evaluation": "(abs:\"evaluation\" OR abs:\"benchmark\" OR abs:\"comparison\") AND (abs:\"large language model\" OR abs:LLM)",
            "science": "(abs:\"scientific\" OR abs:\"science\" OR abs:\"research\" OR abs:\"discovery\") AND (abs:\"large language model\" OR abs:LLM)"
        }
        
        # Model-specific queries for tracking important model families
        self.model_queries = {
            "gpt": "abs:GPT AND (abs:\"large language model\" OR abs:LLM)",
            "llama": "abs:Llama AND (abs:\"large language model\" OR abs:LLM)",
            "mistral": "abs:Mistral AND (abs:\"large language model\" OR abs:LLM)",
            "gemini": "abs:Gemini AND (abs:\"large language model\" OR abs:LLM)",
            "claude": "abs:Claude AND (abs:\"large language model\" OR abs:LLM)",
            "qwen": "abs:Qwen AND (abs:\"large language model\" OR abs:LLM)",
            "phi": "(abs:\"Phi-2\" OR abs:\"Phi-3\") AND (abs:\"large language model\" OR abs:LLM)",
            "deepseek": "abs:DeepSeek AND (abs:\"large language model\" OR abs:LLM)"
        }
        
        # General catch-all queries
        self.general_queries = [
            "(abs:\"large language model\" OR abs:LLM)",
            "abs:\"foundation model\""
        ]
    
    def collect_data(self, 
                    days_back: int = 30, 
                    max_results_per_query: int = 15, 
                    use_cache: bool = True,
                    force_refresh: bool = False,
                    domains: Optional[List[str]] = None,
                    models: Optional[List[str]] = None,
                    **kwargs) -> Dict[str, Any]:
        """
        Collect papers from arXiv using domain-specific queries
        
        Args:
            days_back: Number of days to look back
            max_results_per_query: Maximum number of results per query
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            domains: Specific domains to query (default: all domains)
            models: Specific models to query (default: none)
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected papers
        """
        # Double the time range for better results
        search_days_back = days_back * 2
        cache_file = os.path.join(self.cache_dir, f"papers_{days_back}d_{max_results_per_query}r.json")
        
        # Try to load from cache if requested
        if not force_refresh and use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                cache_time = datetime.fromisoformat(cached_data.get('collection_time', '2000-01-01T00:00:00'))
                now = datetime.now()
                cache_age_hours = (now - cache_time).total_seconds() / 3600
                
                if cache_age_hours < 24:  # Use cache if less than 24 hours old
                    print(f"Using cached arXiv data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached arXiv data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Initialize tracking
        all_papers = []
        seen_ids = set()  # For deduplication
        domain_counts = {}
        model_counts = {}
        
        # Filter domains if specified
        active_domains = {}
        if domains:
            active_domains = {domain: self.domain_queries[domain] for domain in domains if domain in self.domain_queries}
        else:
            active_domains = self.domain_queries
        
        # Filter models if specified
        active_models = {}
        if models:
            active_models = {model: self.model_queries[model] for model in models if model in self.model_queries}
        else:
            # By default, we don't run model queries unless specifically requested
            active_models = {}
        
        # Run general queries first (broad coverage)
        for i, query in enumerate(self.general_queries):
            print(f"Running general query {i+1}/{len(self.general_queries)}")
            papers = self._execute_query(
                query=query, 
                days_back=search_days_back,  # Use extended time range
                max_results=max_results_per_query,
                seen_ids=seen_ids
            )
            
            for paper in papers:
                paper['query_type'] = 'general'
            
            all_papers.extend(papers)
            # Update seen IDs
            for paper in papers:
                seen_ids.add(paper['arxiv_id'])
            
            # Respect rate limits with delay
            time.sleep(3)
        
        # Then run domain-specific queries
        for i, (domain, query) in enumerate(active_domains.items()):
            print(f"Running domain query {i+1}/{len(active_domains)}: {domain}")
            papers = self._execute_query(
                query=query, 
                days_back=search_days_back,  # Use extended time range
                max_results=max_results_per_query,
                seen_ids=seen_ids
            )
            
            # Tag papers with domain
            for paper in papers:
                paper['domain'] = domain
                paper['query_type'] = 'domain'
            
            # Track domain counts
            domain_counts[domain] = len(papers)
            
            all_papers.extend(papers)
            # Update seen IDs
            for paper in papers:
                seen_ids.add(paper['arxiv_id'])
            
            # Respect rate limits with delay
            time.sleep(3)
        
        # Finally, run model-specific queries if requested
        for i, (model, query) in enumerate(active_models.items()):
            print(f"Running model query {i+1}/{len(active_models)}: {model}")
            papers = self._execute_query(
                query=query, 
                days_back=search_days_back,  # Use extended time range
                max_results=max_results_per_query,
                seen_ids=seen_ids
            )
            
            # Tag papers with model
            for paper in papers:
                paper['model'] = model
                paper['query_type'] = 'model'
            
            # Track model counts
            model_counts[model] = len(papers)
            
            all_papers.extend(papers)
            # Update seen IDs
            for paper in papers:
                seen_ids.add(paper['arxiv_id'])
            
            # Respect rate limits with delay
            time.sleep(3)
        
        print(f"Total unique papers collected: {len(all_papers)}")
        
        # Organize papers by domain for better presentation
        papers_by_domain = {}
        for paper in all_papers:
            domain = paper.get('domain', 'general')
            if domain not in papers_by_domain:
                papers_by_domain[domain] = []
            papers_by_domain[domain].append(paper)
        
        # Count papers by category
        category_counts = {}
        for paper in all_papers:
            for category in paper.get('categories', []):
                if category not in category_counts:
                    category_counts[category] = 0
                category_counts[category] += 1
        
        # Count papers by recency
        now = datetime.now()
        last_week = 0
        last_month = 0
        older = 0
        
        for paper in all_papers:
            try:
                pub_date = datetime.strptime(paper['published'], "%Y-%m-%d")
                days_ago = (now - pub_date).days
                
                if days_ago <= 7:
                    last_week += 1
                elif days_ago <= 30:
                    last_month += 1
                else:
                    older += 1
            except:
                older += 1
        
        # Prepare result data
        result = {
            'papers': all_papers,
            'papers_by_domain': papers_by_domain,
            'domain_counts': domain_counts,
            'model_counts': model_counts,
            'category_counts': category_counts,
            'total_papers': len(all_papers),
            'last_week_count': last_week,
            'last_month_count': last_month,
            'older_count': older,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache results
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            print(f"Error caching results: {e}")
        
        return result
    
    def _execute_query(self, query: str, days_back: int, max_results: int, seen_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Execute a single query with proper date constraints
        
        Args:
            query: arXiv query string
            days_back: Number of days to look back
            max_results: Maximum number of results to retrieve
            seen_ids: Set of already seen arXiv IDs for deduplication
            
        Returns:
            List[Dict[str, Any]]: List of paper data dictionaries
        """
        # We'll handle date filtering after receiving results
        # Rather than restricting the search query with dates that might be problematic
        query_with_date = query
        # Log what we're searching for
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        print(f"Looking for papers from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        print(f"Executing query: {query}")
        
        # Prepare request parameters
        params = {
            "search_query": query_with_date,
            "start": 0,
            "max_results": max_results * 2,  # Request more to have room for filtering
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        # Prepare user agent header
        headers = {
            "User-Agent": "LLM-Daily/1.0 (+https://github.com/likw99/llm-daily)"
        }
        
        try:
            # Make API request
            response = requests.get(self.base_url, params=params, headers=headers)
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                return []
            
            # Parse XML response
            try:
                papers = self._parse_response(response.text, seen_ids, days_back, max_results)
                print(f"Retrieved {len(papers)} papers for query")
                return papers
            except Exception as parse_error:
                print(f"Error parsing response: {parse_error}")
                # Try to extract at least some valid papers even if there was an error
                try:
                    # Simple fallback extraction using XML ElementTree
                    root = ET.fromstring(response.text)
                    entries = root.findall(".//atom:entry", self.namespace)
                    
                    if entries and len(entries) > 0:
                        print(f"Attempting fallback parsing for {len(entries)} entries")
                        papers = []
                        for entry in entries[:max_results]:
                            try:
                                paper = self._parse_entry(entry)
                                if paper and 'arxiv_id' in paper and paper['arxiv_id'] not in seen_ids:
                                    papers.append(paper)
                            except:
                                continue
                        
                        if papers:
                            print(f"Fallback parsing recovered {len(papers)} papers")
                            return papers
                except:
                    pass
                return []
            
        except Exception as e:
            print(f"Error executing query: {e}")
            return []
    
    def _parse_response(self, xml_response: str, seen_ids: Set[str], days_back: int, max_results: int) -> List[Dict[str, Any]]:
        """
        Parse arXiv API response XML
        
        Args:
            xml_response: XML response from arXiv API
            seen_ids: Set of already seen arXiv IDs for deduplication
            days_back: Number of days to look back for filtering
            max_results: Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of paper data dictionaries
        """
        papers = []
        
        try:
            # Parse XML
            root = ET.fromstring(xml_response)
            entries = root.findall(".//atom:entry", self.namespace)
            
            # Get the cutoff date
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            print(f"Found {len(entries)} entries in response")
            
            for entry in entries:
                # Extract arXiv ID
                arxiv_url = entry.find("atom:id", self.namespace).text
                arxiv_id = arxiv_url.split("/")[-1]
                
                # Skip if we've already seen this paper
                if arxiv_id in seen_ids:
                    continue
                
                # Parse entry to extract paper data
                paper = self._parse_entry(entry)
                
                # Apply date filtering manually 
                try:
                    published_date = datetime.strptime(paper['published'], "%Y-%m-%d")
                    # Filter based on original days_back requirement, not the expanded search_days_back
                    start_date = end_date - timedelta(days=days_back)  
                    if published_date < start_date:
                        # Skip papers that are too old
                        continue
                except Exception as date_error:
                    # If we can't parse the date, include the paper anyway
                    print(f"Warning: couldn't parse date for paper {arxiv_id}: {date_error}")
                
                # Add to results if we haven't hit the limit
                papers.append(paper)
                
                # If we've reached our limit, stop processing entries
                if len(papers) >= max_results:
                    break
                
        except Exception as e:
            import traceback
            print(f"Error parsing XML response: {e}")
            print(traceback.format_exc())
            print(f"First 500 chars of response: {xml_response[:500] if xml_response else 'Empty response'}")
        
        return papers
    
    def _parse_entry(self, entry) -> Dict[str, Any]:
        """
        Parse an entry (paper) from the API response
        
        Args:
            entry: XML entry element
            
        Returns:
            Dict[str, Any]: Dictionary containing paper information
        """
        # Extract basic information
        title = entry.find("atom:title", self.namespace).text.strip()
        summary = entry.find("atom:summary", self.namespace).text.strip()
        published = entry.find("atom:published", self.namespace).text
        updated = entry.find("atom:updated", self.namespace).text
        
        # Format publish date
        published_date = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
        
        # Extract authors
        authors = []
        for author_elem in entry.findall("atom:author", self.namespace):
            name = author_elem.find("atom:name", self.namespace).text
            authors.append(name)
        
        # Extract arXiv ID
        arxiv_url = entry.find("atom:id", self.namespace).text
        arxiv_id = arxiv_url.split("/")[-1]
        
        # Extract PDF URL
        pdf_url = None
        for link in entry.findall("atom:link", self.namespace):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        
        # Extract categories
        categories = []
        for category in entry.findall("arxiv:category", self.namespace):
            categories.append(category.get("term"))
        
        # Extract comments if available
        comment = entry.find("arxiv:comment", self.namespace)
        comment_text = comment.text if comment is not None else None
        
        # Extract journal reference if available
        journal_ref = entry.find("arxiv:journal_ref", self.namespace)
        journal_ref_text = journal_ref.text if journal_ref is not None else None
        
        # Create paper object
        paper = {
            "title": title,
            "authors": authors,
            "summary": summary,
            "published": published_date,
            "updated": datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d"),
            "arxiv_id": arxiv_id,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf_url,
            "categories": categories,
            "primary_category": entry.find("arxiv:primary_category", self.namespace).get("term"),
            "comment": comment_text,
            "journal_ref": journal_ref_text
        }
        
        return paper
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing collected papers
            
        Returns:
            str: Formatted text for LLM input
        """
        papers = data.get('papers', [])
        papers_by_domain = data.get('papers_by_domain', {})
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# ARXIV RESEARCH DATA\n\n"
        
        if not papers:
            output += "No relevant papers found.\n\n"
            return output
        
        # Add a general overview
        output += "## Overview\n\n"
        output += f"Total papers: {len(papers)}\n"
        output += f"Collection date: {collection_time[:10]}\n"
        
        last_week = data.get('last_week_count', 0)
        last_month = data.get('last_month_count', 0)
        
        output += f"Papers published in the last week: {last_week}\n"
        output += f"Papers published in the last month: {last_month}\n\n"
        
        # Format domain-specific sections
        for domain, domain_papers in papers_by_domain.items():
            # Skip empty domains
            if not domain_papers:
                continue
                
            if domain == 'general':
                domain_title = "General LLM Research"
            else:
                # Convert domain to title case and replace underscores with spaces
                domain_title = domain.replace('_', ' ').title()
            
            output += f"## {domain_title} ({len(domain_papers)} papers)\n\n"
            
            # Sort papers by published date (most recent first)
            sorted_papers = sorted(domain_papers, key=lambda x: x.get('published', ''), reverse=True)
            
            for i, paper in enumerate(sorted_papers[:10], 1):  # Limit to top 10 papers per domain
                # Format paper information
                output += f"### Paper {i}: {paper['title']}\n"
                output += f"Authors: {', '.join(paper['authors'])}\n"
                output += f"Published: {paper['published']}\n"
                output += f"arXiv: [{paper['arxiv_id']}]({paper['arxiv_url']})\n"
                
                if paper.get('primary_category'):
                    output += f"Primary Category: {paper['primary_category']}\n"
                
                # Add journal reference if available
                if paper.get('journal_ref'):
                    output += f"Journal Reference: {paper['journal_ref']}\n"
                
                output += "\n"
                
                # Format abstract (truncate if too long)
                summary = paper['summary']
                if len(summary) > 500:
                    summary = summary[:500] + "... [truncated]"
                output += f"Abstract:\n{summary}\n\n"
                
                output += "---\n\n"
        
        # Add summary statistics
        output += "\n## Summary Statistics\n"
        
        # Top categories
        category_counts = data.get('category_counts', {})
        if category_counts:
            output += "### Top Categories\n"
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                output += f"- {category}: {count} papers\n"
            output += "\n"
        
        # Domain distribution
        domain_counts = data.get('domain_counts', {})
        if domain_counts:
            output += "### Domain Distribution\n"
            for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
                domain_title = domain.replace('_', ' ').title()
                output += f"- {domain_title}: {count} papers\n"
            output += "\n"
        
        # Model distribution
        model_counts = data.get('model_counts', {})
        if model_counts:
            output += "### Model-Specific Papers\n"
            for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
                model_name = model.upper() if model in ['gpt', 'llm'] else model.title()
                output += f"- {model_name}: {count} papers\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        papers = data.get('papers', [])
        
        # Return pre-calculated statistics if available
        if all(key in data for key in ['last_week_count', 'last_month_count', 'category_counts', 'domain_counts']):
            return {
                "total_papers": len(papers),
                "category_counts": data.get('category_counts', {}),
                "domain_counts": data.get('domain_counts', {}),
                "model_counts": data.get('model_counts', {}),
                "last_week_count": data.get('last_week_count', 0),
                "last_month_count": data.get('last_month_count', 0),
                "collection_timestamp": data.get('collection_time', datetime.now().isoformat())
            }
        
        # Otherwise calculate statistics
        
        # Count papers by category
        category_counts = {}
        for paper in papers:
            for category in paper.get('categories', []):
                if category not in category_counts:
                    category_counts[category] = 0
                category_counts[category] += 1
        
        # Count papers by domain
        domain_counts = {}
        for paper in papers:
            domain = paper.get('domain', 'general')
            if domain not in domain_counts:
                domain_counts[domain] = 0
            domain_counts[domain] += 1
        
        # Count papers by model
        model_counts = {}
        for paper in papers:
            if 'model' in paper:
                model = paper['model']
                if model not in model_counts:
                    model_counts[model] = 0
                model_counts[model] += 1
        
        # Count papers by recency
        now = datetime.now()
        last_week = 0
        last_month = 0
        
        for paper in papers:
            try:
                pub_date = datetime.strptime(paper['published'], "%Y-%m-%d")
                days_ago = (now - pub_date).days
                
                if days_ago <= 7:
                    last_week += 1
                elif days_ago <= 30:
                    last_month += 1
            except:
                # Skip papers with unparseable dates
                pass
        
        return {
            "total_papers": len(papers),
            "category_counts": category_counts,
            "domain_counts": domain_counts,
            "model_counts": model_counts,
            "last_week_count": last_week,
            "last_month_count": last_month,
            "collection_timestamp": datetime.now().isoformat()
        }


# Test function when run directly
if __name__ == "__main__":
    import argparse
    
    # Set up argument parser for command-line testing
    parser = argparse.ArgumentParser(description="Test the ArXivCollector")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--results", type=int, default=10, help="Maximum results per query")
    parser.add_argument("--output", type=str, default="arxiv_data_sample.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="arxiv_data_sample.json", help="Output file for raw JSON data")
    parser.add_argument("--no-cache", action="store_true", help="Skip using cache")
    parser.add_argument("--domains", type=str, help="Comma-separated list of domains to query")
    parser.add_argument("--models", type=str, help="Comma-separated list of models to query")
    args = parser.parse_args()
    
    print("╔═════════════════════════════════════╗")
    print("║      ARXIV COLLECTOR TEST RUN       ║")
    print("╚═════════════════════════════════════╝\n")
    
    # Parse domains and models if provided
    domains = args.domains.split(',') if args.domains else None
    models = args.models.split(',') if args.models else None
    
    print("Configuration:")
    print(f"• Looking back {args.days} days")
    print(f"• Maximum {args.results} results per query")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    if domains:
        print(f"• Domains: {', '.join(domains)}")
    if models:
        print(f"• Models: {', '.join(models)}")
    print("─────────────────────────────────────")
    
    # Initialize collector
    collector = ArXivCollector()
    
    # Collect data
    print("\nCollecting data from arXiv...")
    start_time = time.time()
    
    # Execute collection
    raw_data = collector.collect_data(
        days_back=args.days, 
        max_results_per_query=args.results, 
        use_cache=not args.no_cache,
        domains=domains,
        models=models
    )
    
    end_time = time.time()
    collection_time = end_time - start_time
    
    # Format data for LLM
    print("Formatting data for LLM...")
    format_start = time.time()
    formatted_data = collector.format_for_llm(raw_data)
    format_time = time.time() - format_start
    
    # Calculate statistics
    stats = collector.get_statistics(raw_data)
    papers = raw_data.get('papers', [])
    
    # Print statistics
    print("\n╔══════════════════════════════════╗")
    print("║         COLLECTION RESULTS        ║")
    print("╚══════════════════════════════════╝")
    
    print(f"\nCollection completed in {collection_time:.2f} seconds")
    print(f"Formatting completed in {format_time:.2f} seconds")
    
    # Print paper count with color coding
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
    if stats['domain_counts']:
        print("\nPapers by domain:")
        for domain, count in sorted(stats['domain_counts'].items(), key=lambda x: x[1], reverse=True):
            domain_title = domain.replace('_', ' ').title()
            print(f"  • {domain_title}: {count}")
    
    # Print category breakdown
    if paper_count > 0:
        print("\nPapers by category:")
        for category, count in sorted(stats['category_counts'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  • {category}: {count}")
        
        # Print a few paper titles as examples
        print("\nSample papers:")
        for i, paper in enumerate(papers[:3], 1):
            print(f"  {i}. {paper['title']}")
            print(f"     Authors: {', '.join(paper['authors'][:3])}{' and others' if len(paper['authors']) > 3 else ''}")
            print(f"     Published: {paper['published']}")
            print(f"     arXiv ID: {paper['arxiv_id']}")
            print()
    
    # Save formatted data
    with open(args.output, "w") as f:
        f.write(formatted_data)
    print(f"Formatted data saved to {args.output}")
    
    # Save raw data as JSON
    try:
        import json
        with open(args.json, "w") as f:
            json.dump(raw_data, f, indent=2)
        print(f"Raw JSON data saved to {args.json}")
    except Exception as e:
        print(f"Error saving JSON data: {e}")
    
    print("\n✨ Test completed successfully!")