import os
import json
import feedparser
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

try:
    from .base_collector import BaseCollector
except ImportError:
    # Handle direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from base_collector import BaseCollector

class SequoiaCollector(BaseCollector):
    """Collector for Sequoia Capital insights via their official RSS feed"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the Sequoia Capital collector
        
        Args:
            cache_dir: Directory for caching results (optional)
        """
        # RSS feed URL
        self.rss_url = "https://www.sequoiacap.com/rss"
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "sequoia"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Keywords for filtering AI and tech-relevant content
        self.relevance_keywords = [
            # AI/ML Keywords
            "ai", "artificial intelligence", "machine learning", "deep learning",
            "llm", "large language model", "generative ai", "neural network",
            "gpt", "transformer", "computer vision", "natural language processing",
            "nlp", "automation", "chatbot", "generative", "foundation model",
            
            # Tech/Business Keywords  
            "fintech", "saas", "software", "platform", "api", "cloud",
            "data", "analytics", "digital transformation", "enterprise",
            "startup", "funding", "investment", "venture capital", "vc",
            "series a", "series b", "ipo", "acquisition", "partnership",
            
            # Industry Keywords
            "technology", "innovation", "developer", "open source", 
            "infrastructure", "security", "cybersecurity", "blockchain",
            "crypto", "web3", "mobile", "internet", "marketplace"
        ]
    
    def collect_data(self, 
                     days_back: int = 7, 
                     max_articles: int = 15, 
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect insights from Sequoia Capital RSS feed
        
        Args:
            days_back: Number of days to look back
            max_articles: Maximum number of articles to retrieve
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected article data
        """
        cache_file = os.path.join(self.cache_dir, f"sequoia_{days_back}d.json")
        
        # Check if we're forcing a refresh
        if force_refresh:
            print("Force refresh requested, skipping cache check")
        # Check if we have cached data and it's recent enough
        elif use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                cache_time = datetime.fromisoformat(cached_data.get('collection_time', '2000-01-01T00:00:00'))
                now = datetime.now()
                cache_age_hours = (now - cache_time).total_seconds() / 3600
                
                if cache_age_hours < 12:  # Use cache if it's less than 12 hours old
                    print(f"Using cached Sequoia data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached Sequoia data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Fetch articles from RSS feed
        print(f"Fetching Sequoia Capital insights from RSS feed: {self.rss_url}")
        articles = self._fetch_articles_from_rss(days_back)
        
        # Filter for relevant content
        relevant_articles = self._filter_relevant_articles(articles)
        
        # Sort by published date (most recent first)
        sorted_articles = sorted(relevant_articles, key=lambda x: x.get('published', ''), reverse=True)
        
        # Limit to max_articles if needed
        if len(sorted_articles) > max_articles:
            sorted_articles = sorted_articles[:max_articles]
        
        result = {
            'articles': sorted_articles,
            'source': 'Sequoia Capital',
            'url': self.rss_url,
            'article_count': len(sorted_articles),
            'total_count': len(articles),
            'days_back': days_back,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Cached {len(sorted_articles)} Sequoia articles to {cache_file}")
        
        return result
    
    def _fetch_articles_from_rss(self, days_back: int) -> List[Dict[str, Any]]:
        """
        Fetch articles from the Sequoia Capital RSS feed
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List[Dict[str, Any]]: List of article dictionaries
        """
        try:
            # Parse the RSS feed
            feed = feedparser.parse(self.rss_url)
            
            if feed.bozo:
                print(f"Warning: RSS feed parsing issues detected: {feed.bozo_exception}")
            
            articles = []
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            for entry in feed.entries:
                try:
                    # Parse publication date
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    elif hasattr(entry, 'updated_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    else:
                        # If no date is available, use current time as fallback
                        pub_date = datetime.now()
                    
                    # Skip articles older than cutoff date
                    if pub_date < cutoff_date:
                        continue
                    
                    # Extract article data
                    article = {
                        'id': entry.get('id', entry.get('link', f"sequoia-{len(articles)}")),
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link', ''),
                        'summary': self._clean_html(entry.get('summary', '')),
                        'published': pub_date.isoformat(),
                        'author': 'Sequoia Capital',
                        'source': 'Sequoia Capital'
                    }
                    
                    # Extract categories/tags
                    if hasattr(entry, 'tags'):
                        article['categories'] = [tag.get('term', '') for tag in entry.tags]
                    else:
                        article['categories'] = []
                    
                    # Extract full content if available (for better relevance scoring)
                    content = ''
                    if hasattr(entry, 'content') and entry.content:
                        content = self._clean_html(entry.content[0].value)
                    elif hasattr(entry, 'description'):
                        content = self._clean_html(entry.description)
                    
                    article['content'] = content
                    
                    articles.append(article)
                    
                except Exception as e:
                    print(f"Error processing RSS entry: {e}")
            
            print(f"Retrieved {len(articles)} articles from Sequoia Capital RSS feed")
            return articles
            
        except Exception as e:
            print(f"Error fetching RSS feed from Sequoia Capital: {e}")
            return []
    
    def _clean_html(self, html_text: str) -> str:
        """
        Clean HTML tags and entities from text
        
        Args:
            html_text: Raw HTML text
            
        Returns:
            str: Cleaned plain text
        """
        if not html_text:
            return ""
        
        try:
            # Use BeautifulSoup to parse and clean HTML
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text and clean it up
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            print(f"Error cleaning HTML: {e}")
            # Fallback: simple regex-based cleaning
            clean_text = re.sub(r'<[^>]+>', '', html_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text
    
    def _filter_relevant_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter articles for AI/tech relevance
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            List[Dict[str, Any]]: Filtered list of relevant articles
        """
        relevant_articles = []
        
        for article in articles:
            relevance_score = self._calculate_relevance_score(article)
            article['relevance_score'] = relevance_score
            
            # Include articles with relevance score >= 3 (out of 10)
            if relevance_score >= 3:
                relevant_articles.append(article)
        
        print(f"Filtered {len(relevant_articles)} relevant articles out of {len(articles)}")
        return relevant_articles
    
    def _calculate_relevance_score(self, article: Dict[str, Any]) -> int:
        """
        Calculate relevance score for an article (1-10 scale)
        
        Args:
            article: Article dictionary
            
        Returns:
            int: Relevance score from 1-10
        """
        score = 0
        
        # Combine title, summary, content, and categories for scoring
        text_to_score = " ".join([
            article.get('title', ''),
            article.get('summary', ''),
            article.get('content', ''),
            " ".join(article.get('categories', []))
        ]).lower()
        
        # Count keyword matches
        keyword_matches = 0
        for keyword in self.relevance_keywords:
            if keyword in text_to_score:
                keyword_matches += 1
        
        # Base score from keyword density
        if keyword_matches >= 5:
            score = 8
        elif keyword_matches >= 3:
            score = 6
        elif keyword_matches >= 2:
            score = 4
        elif keyword_matches >= 1:
            score = 3
        else:
            score = 1
        
        # Boost for AI-specific keywords
        ai_keywords = ["ai", "artificial intelligence", "machine learning", "llm", "generative ai"]
        for keyword in ai_keywords:
            if keyword in text_to_score:
                score = min(10, score + 2)
                break
        
        # Boost for funding/investment keywords
        investment_keywords = ["funding", "investment", "series a", "series b", "ipo", "acquisition"]
        for keyword in investment_keywords:
            if keyword in text_to_score:
                score = min(10, score + 1)
                break
        
        return min(10, max(1, score))
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        articles = data.get('articles', [])
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# SEQUOIA CAPITAL INSIGHTS\n\n"
        
        if not articles:
            output += "No recent insights found from Sequoia Capital.\n\n"
            return output
        
        # Group articles by day
        articles_by_day = {}
        for article in articles:
            pub_date = article.get('published', '')
            if pub_date and 'T' in pub_date:
                day = pub_date.split('T')[0]  # Extract just the date part
                if day not in articles_by_day:
                    articles_by_day[day] = []
                articles_by_day[day].append(article)
        
        # Format articles by day
        for day, day_articles in sorted(articles_by_day.items(), reverse=True):
            # Format date nicely
            try:
                date_obj = datetime.fromisoformat(day)
                formatted_date = date_obj.strftime('%B %d, %Y')
            except:
                formatted_date = day
            
            output += f"## {formatted_date}\n\n"
            
            for i, article in enumerate(day_articles, 1):
                output += f"### {article.get('title', 'Untitled')}\n"
                output += f"Link: {article.get('link', '')}\n\n"
                
                # Add summary if available
                if article.get('summary'):
                    summary = article.get('summary')
                    # Truncate if too long
                    if len(summary) > 500:
                        summary = summary[:500] + "... [truncated]"
                    output += f"{summary}\n\n"
                
                # Add categories if available
                if article.get('categories') and len(article.get('categories', [])) > 0:
                    output += f"Categories: {', '.join(article.get('categories'))}\n\n"
                
                # Add relevance score for debugging
                if article.get('relevance_score'):
                    output += f"Relevance Score: {article.get('relevance_score')}/10\n\n"
                
                output += "---\n\n"
        
        # Add summary statistics
        output += "## Summary Statistics\n"
        output += f"- Total insights: {len(articles)}\n"
        output += f"- Days covered: {len(articles_by_day)}\n"
        output += "- Source: Sequoia Capital\n"
        output += f"- Collection date: {collection_time[:10]}\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        articles = data.get('articles', [])
        
        # Count articles by day
        days = {}
        categories = {}
        relevance_scores = []
        
        for article in articles:
            # Count by day
            pub_date = article.get('published', '')
            if pub_date and 'T' in pub_date:
                day = pub_date.split('T')[0]
                if day not in days:
                    days[day] = 0
                days[day] += 1
            
            # Count categories
            for category in article.get('categories', []):
                if category not in categories:
                    categories[category] = 0
                categories[category] += 1
            
            # Collect relevance scores
            if article.get('relevance_score'):
                relevance_scores.append(article.get('relevance_score'))
        
        # Calculate average relevance score
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        # Calculate statistics
        return {
            "total_articles": len(articles),
            "total_fetched": data.get('total_count', len(articles)),
            "days_covered": len(days),
            "articles_per_day": round(len(articles) / max(len(days), 1), 1),
            "categories": categories,
            "top_categories": sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5],
            "average_relevance_score": round(avg_relevance, 1),
            "high_relevance_count": len([s for s in relevance_scores if s >= 7]),
            "days": days,
            "source": "Sequoia Capital",
            "collection_timestamp": datetime.now().isoformat()
        }


# Test function when run directly
if __name__ == "__main__":
    import argparse
    
    # Set up argument parser for command-line testing
    parser = argparse.ArgumentParser(description="Test the SequoiaCollector")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--articles", type=int, default=15, help="Maximum articles to retrieve")
    parser.add_argument("--output", type=str, default="sequoia_data_sample.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="sequoia_data_sample.json", help="Output file for raw JSON data")
    parser.add_argument("--no-cache", action="store_true", help="Force refresh, ignore cache")
    
    args = parser.parse_args()
    
    print("╔══════════════════════════════════╗")
    print("║      SEQUOIA COLLECTOR TEST      ║")
    print("╚══════════════════════════════════╝")
    print(f"Looking back: {args.days} days")
    print(f"Max articles: {args.articles}")
    print(f"Output file: {args.output}")
    print(f"JSON file: {args.json}")
    if args.no_cache:
        print("Cache: Disabled (force refresh)")
    print("─────────────────────────────────────")
    
    # Initialize collector
    collector = SequoiaCollector()
    
    # Collect data
    print("\nCollecting data from Sequoia Capital...")
    start_time = time.time()
    
    # Execute collection
    raw_data = collector.collect_data(
        days_back=args.days, 
        max_articles=args.articles, 
        use_cache=not args.no_cache,
        force_refresh=args.no_cache
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
    articles = raw_data.get('articles', [])
    
    # Save formatted output
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(formatted_data)
    
    # Save raw JSON data
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    
    # Print statistics
    print("\n╔══════════════════════════════════╗")
    print("║         COLLECTION RESULTS        ║")
    print("╚══════════════════════════════════╝")
    
    print(f"\nCollection completed in {collection_time:.2f} seconds")
    print(f"Formatting completed in {format_time:.2f} seconds")
    
    # Print article count with color coding
    article_count = stats['total_articles']
    if article_count == 0:
        print("\n❌ No articles were collected! Check the RSS feed.")
    elif article_count < 3:
        print(f"\n⚠️ Only collected {article_count} articles. Consider extending the time range.")
    else:
        print(f"\n✅ Successfully collected {article_count} articles:")
    
    print(f"  • Total fetched from RSS: {stats['total_fetched']}")
    print(f"  • After relevance filtering: {article_count}")
    print(f"  • High relevance (7+/10): {stats['high_relevance_count']}")
    print(f"  • Average relevance score: {stats['average_relevance_score']}/10")
    print(f"  • Days covered: {stats['days_covered']}")
    print(f"  • Articles per day: {stats['articles_per_day']}")
    
    # Show top categories
    if stats['top_categories']:
        print("\n📊 Top Categories:")
        for category, count in stats['top_categories']:
            print(f"  • {category}: {count}")
    
    print("\n📁 Files saved:")
    print(f"  • Formatted: {args.output}")
    print(f"  • Raw JSON: {args.json}")
    
    print(f"\n🎯 Summary: Found {article_count} relevant Sequoia Capital insights")
    if article_count > 0:
        print("Ready for integration into the newsletter Business section!")
    
    print("\n" + "="*50)
