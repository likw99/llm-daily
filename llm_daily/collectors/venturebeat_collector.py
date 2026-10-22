import os
import json
import feedparser
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re

from .base_collector import BaseCollector

class VentureBeatCollector(BaseCollector):
    """Collector for AI news articles from VentureBeat"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the VentureBeat collector
        
        Args:
            cache_dir: Directory for caching results (optional)
        """
        # RSS feed URL
        self.rss_url = "https://venturebeat.com/category/ai/feed/"
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "venturebeat"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # AI-related keywords for additional filtering (beyond the AI category)
        self.ai_keywords = [
            "llm", "large language model", "artificial intelligence", 
            "machine learning", "deep learning", "neural network", 
            "generative ai", "openai", "anthropic", "claude", "gpt", 
            "stable diffusion", "midjourney", "mistral", "ai investment",
            "ai funding", "ai startup", "ai acquisition"
        ]
    
    def collect_data(self, 
                     days_back: int = 7, 
                     max_articles: int = 25, 
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect AI news articles from VentureBeat RSS feed
        
        Args:
            days_back: Number of days to look back
            max_articles: Maximum number of articles to retrieve
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected article data
        """
        cache_file = os.path.join(self.cache_dir, f"venturebeat_{days_back}d.json")
        
        # Check if we're forcing a refresh
        if force_refresh:
            print("Force refresh requested, skipping cache check")
        # Check if we have cached data and it's recent enough
        elif use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                cache_time = datetime.fromisoformat(cached_data.get('collection_time', '2000-01-01T00:00:00'))
                now = datetime.now()
                cache_age_hours = (now - cache_time).total_seconds() / 3600
                
                if cache_age_hours < 12:  # Use cache if it's less than 12 hours old
                    print(f"Using cached VentureBeat data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached VentureBeat data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Fetch articles from RSS feed
        print(f"Fetching VentureBeat AI articles from RSS feed: {self.rss_url}")
        articles = self._fetch_articles_from_rss(days_back)
        
        # Limit to max_articles if needed
        if len(articles) > max_articles:
            articles = articles[:max_articles]
        
        result = {
            'articles': articles,
            'source': 'VentureBeat',
            'url': self.rss_url,
            'article_count': len(articles),
            'days_back': days_back,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Cached {len(articles)} VentureBeat articles to {cache_file}")
        
        return result
    
    def _fetch_articles_from_rss(self, days_back: int) -> List[Dict[str, Any]]:
        """
        Fetch articles from the VentureBeat RSS feed
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List[Dict[str, Any]]: List of article data dictionaries
        """
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        try:
            # Parse the RSS feed
            feed = feedparser.parse(self.rss_url)
            
            if not feed.entries:
                print("No entries found in the RSS feed")
                return []
            
            articles = []
            
            for entry in feed.entries:
                try:
                    # Parse the published date
                    pub_date = None
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    elif hasattr(entry, 'updated_parsed'):
                        pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    else:
                        # If no date is available, use current time as fallback
                        # This ensures we don't miss articles due to date parsing issues
                        pub_date = datetime.now()
                    
                    # Skip articles older than cutoff date
                    if pub_date < cutoff_date:
                        continue
                    
                    # Extract article data
                    article = {
                        'id': entry.get('id', entry.get('link', f"vb-{len(articles)}")),
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link', ''),
                        'summary': self._clean_html(entry.get('summary', '')),
                        'published': pub_date.isoformat(),
                        'authors': [author.get('name', 'Unknown') for author in entry.get('authors', [])],
                        'categories': [tag.get('term', '') for tag in entry.get('tags', [])],
                    }
                    
                    # Extract the thumbnail image if available
                    if 'media_thumbnail' in entry and entry.media_thumbnail:
                        article['thumbnail'] = entry.media_thumbnail[0]['url']
                    
                    # Add relevance score based on AI keywords in title and summary
                    score = self._calculate_ai_relevance(article['title'], article['summary'])
                    article['ai_relevance'] = score
                    
                    articles.append(article)
                    
                except Exception as e:
                    print(f"Error processing RSS entry: {e}")
            
            # Sort articles by published date (most recent first)
            articles = sorted(articles, key=lambda x: x.get('published', ''), reverse=True)
            
            print(f"Retrieved {len(articles)} articles from VentureBeat RSS feed")
            return articles
            
        except Exception as e:
            print(f"Error fetching RSS feed from VentureBeat: {e}")
            return []
    
    def _clean_html(self, html_text: str) -> str:
        """
        Clean HTML tags from text
        
        Args:
            html_text: Text with HTML tags
            
        Returns:
            str: Cleaned text
        """
        # Simple regex-based HTML tag removal
        clean_text = re.sub(r'<.*?>', '', html_text)
        
        # Replace multiple whitespaces and newlines with a single space
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def _calculate_ai_relevance(self, title: str, summary: str) -> int:
        """
        Calculate relevance score based on AI keywords
        
        Args:
            title: Article title
            summary: Article summary
            
        Returns:
            int: Relevance score
        """
        combined_text = (title + " " + summary).lower()
        score = 0
        
        # Check for AI keywords
        for keyword in self.ai_keywords:
            if keyword in combined_text:
                # Keywords in title are more important
                if keyword in title.lower():
                    score += 3
                else:
                    score += 1
        
        return score
    
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
        
        output = "# VENTUREBEAT AI NEWS\n\n"
        
        if not articles:
            output += "No recent AI articles found on VentureBeat.\n\n"
            return output
        
        # Sort by published date (most recent first)
        sorted_articles = sorted(articles, key=lambda x: x.get('published', ''), reverse=True)
        
        # Group articles by day
        articles_by_day = {}
        for article in sorted_articles:
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
                
                # Add authors if available
                if article.get('authors'):
                    authors = ', '.join(article.get('authors'))
                    output += f"By: {authors}\n"
                
                output += f"Link: {article.get('link', '')}\n\n"
                
                # Add summary if available
                if article.get('summary'):
                    summary = article.get('summary')
                    # Truncate if too long
                    if len(summary) > 500:
                        summary = summary[:500] + "... [truncated]"
                    output += f"{summary}\n\n"
                
                # Add categories if available
                if article.get('categories'):
                    output += f"Categories: {', '.join(article.get('categories'))}\n\n"
                
                output += "---\n\n"
        
        # Add summary statistics
        output += "## Summary Statistics\n"
        output += f"- Total articles: {len(articles)}\n"
        output += f"- Days covered: {len(articles_by_day)}\n"
        output += "- Source: VentureBeat AI category\n"
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
        for article in articles:
            pub_date = article.get('published', '')
            if pub_date and 'T' in pub_date:
                day = pub_date.split('T')[0]
                if day not in days:
                    days[day] = 0
                days[day] += 1
        
        # Calculate statistics
        return {
            "total_articles": len(articles),
            "days_covered": len(days),
            "articles_per_day": round(len(articles) / max(len(days), 1), 1),
            "days": days,
            "source": "VentureBeat",
            "collection_timestamp": datetime.now().isoformat()
        }
