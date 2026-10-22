# Data Collectors

This directory contains the data collection modules used to gather information from various sources for the LLM Daily newsletter system.

## Table of Contents

- [Overview](#overview)
- [Integration Methods](#integration-methods)
- [Adding a New Data Source](#adding-a-new-data-source)
- [Best Practices](#best-practices)
- [Handling Rate Limits](#handling-rate-limits)
- [Error Handling](#error-handling)
- [Existing Collectors](#existing-collectors)
- [Collector Requirements](#collector-requirements)

## Overview

The `collectors` module contains specialized classes that retrieve data from different sources like Reddit, arXiv, Twitter/X, GitHub, etc. Each collector inherits from the `BaseCollector` abstract class and implements the required methods to collect and format data for consumption by the LLM.

## Integration Methods

When integrating a new data source, consider these approaches in order of preference:

### 1. Official APIs (Best)

Official APIs are the most reliable and future-proof method of integration:

- Provides structured data in machine-readable format (JSON/XML)
- Changes are typically versioned and documented
- Often includes metadata like rate limits and quotas
- Usually provides authentication mechanisms

**Example**: The `RedditCollector` uses the official PRAW library which wraps the Reddit API.

### 2. RSS/Atom Feeds (Good)

RSS feeds are a standardized way to consume content updates:

- Widely supported by news sites, blogs, and publications
- Provides structured data in XML format
- Low maintenance and typically stable
- Limited by what the source chooses to include in the feed

**Example**: The `VentureBeatCollector` and `TechCrunchCollector` use RSS feeds via the `feedparser` library.

### 3. Official SDKs/Libraries (Good)

Many platforms provide official libraries for their APIs:

- Handles authentication, rate limiting, and formatting
- Maintained by the platform provider
- Typically follows best practices

**Example**: The `HuggingFaceCollector` uses the official `huggingface_hub` library.

### 4. Web Scraping (Limited Use)

Web scraping should be used only when no other options are available:

- Highly brittle and requires frequent maintenance
- May violate terms of service for some websites
- Requires careful implementation to be respectful of the source
- Use with proper rate limiting and user agents

**Example**: The `GitHubCollector` uses both the GitHub API and scraping of trending pages as a hybrid approach.

### 5. Third-Party Aggregation Services (Fallback)

Services that aggregate or proxy data from multiple sources:

- Can provide unified access to multiple data sources
- May introduce additional points of failure
- Typically have their own limitations and terms

## Adding a New Data Source

To add a new data collector:

1. Create a new file `your_source_collector.py` in this directory
2. Import and inherit from the `BaseCollector` class
3. Implement the required methods:
   - `collect_data()`: Retrieves raw data from the source
   - `format_for_llm()`: Formats data into text for the LLM
   - (Optional) `get_statistics()`: Compute statistics about the collected data

```python
from .base_collector import BaseCollector

class YourSourceCollector(BaseCollector):
    """Collector for Your Source data"""
    
    def __init__(self, config_path: str = None):
        # Initialize any API clients, authentication, etc.
        pass
        
    def collect_data(self, **kwargs) -> dict:
        """Collect data from your source"""
        # Implementation here
        return collected_data
        
    def format_for_llm(self, data: dict) -> str:
        """Format the collected data for LLM input"""
        # Implementation here
        return formatted_text
        
    def get_statistics(self, data: dict) -> dict:
        """Generate statistics about the collected data"""
        # Implementation here
        return stats
```

4. Update `main.py` to use your new collector
5. Add any required dependencies to `requirements.txt`

## Best Practices

### Authentication

- Store API keys and tokens in environment variables, not in code
- Use the `.env` file for local development
- For production, use GitHub Secrets or similar

```python
import os
from dotenv import load_dotenv

# Load from .env file in development
load_dotenv()

# Access environment variables
api_key = os.environ.get("YOUR_API_KEY")
```

### Caching

Implement caching to reduce API calls and respect rate limits:

```python
cache_file = os.path.join(self.cache_dir, f"your_source_{days_back}d.json")

# Check if cache exists and is recent
if use_cache and os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cached_data = json.load(f)
    # Check if cache is fresh enough
    # ...
    return cached_data

# If no valid cache, collect data
# ...

# Save to cache
with open(cache_file, 'w') as f:
    json.dump(result, f, indent=2)
```

### Rate Limiting

Be respectful of API rate limits:

```python
import time

# Add delay between requests
time.sleep(1)  # 1 second delay

# For more sophisticated rate limiting, consider:
# - Exponential backoff
# - Token bucket algorithms
# - Using libraries like ratelimit or requests-ratelimiter
```

## Handling Rate Limits

Many APIs enforce rate limits. Strategies to handle them:

1. **Cache aggressively**: Use cached data whenever possible
2. **Implement backoff**: Use exponential backoff for retries
3. **Monitor limits**: Track remaining quota when available
4. **Schedule efficiently**: Spread out collection over time

Example of exponential backoff:

```python
def make_request_with_backoff(url, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            if response.status_code == 429:  # Too Many Requests
                sleep_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue
            return response
        except Exception as e:
            print(f"Request failed: {e}")
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                raise
    return None
```

## Error Handling

Robust error handling is critical for reliable data collection:

```python
try:
    # Attempt data collection
    pass
except RequestException as e:
    # Handle network errors
    print(f"Network error: {e}")
    return fallback_data()
except KeyError as e:
    # Handle missing data in responses
    print(f"Data format error: {e}")
    return parsed_partial_data()
except Exception as e:
    # General error handling
    print(f"Unexpected error: {e}")
    return empty_response()
```

## Existing Collectors

| Collector | Data Source | Method | Description |
|-----------|-------------|--------|-------------|
| `RedditCollector` | Reddit | API (PRAW) | Collects posts from AI-focused subreddits |
| `XCollector` | Twitter/X | API | Collects tweets from AI expert lists |
| `ArXivCollector` | arXiv | API | Collects AI research papers |
| `GitHubCollector` | GitHub | API + Scraping | Collects trending AI repositories |
| `HuggingFaceCollector` | Hugging Face | API | Collects trending models and datasets |
| `ProductHuntCollector` | Product Hunt | API + Scraping | Collects AI product launches |
| `VentureBeatCollector` | VentureBeat | RSS | Collects AI news articles |
| `TechCrunchCollector` | TechCrunch | RSS | Collects AI news articles |

## Collector Requirements

All collectors must:

1. **Handle errors gracefully**: No uncaught exceptions
2. **Implement caching**: Avoid unnecessary API calls
3. **Respect rate limits**: Be a good API citizen
4. **Filter for relevance**: Focus on AI/LLM content
5. **Format consistently**: Follow the established patterns
6. **Include attribution**: Preserve source information
7. **Document clearly**: Include docstrings and comments

---

## Example: RSS Collector Implementation

Here's a simplified example of implementing an RSS-based collector:

```python
import feedparser
import time
from datetime import datetime, timedelta
import os
import json
from typing import Dict, Any, List

from .base_collector import BaseCollector

class ExampleRSSCollector(BaseCollector):
    """Collector for data from an RSS feed"""
    
    def __init__(self, cache_dir: str = None):
        # RSS feed URL
        self.rss_url = "https://example.com/feed.xml"
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "example_rss"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Keywords for filtering
        self.ai_keywords = [
            "llm", "large language model", "artificial intelligence", 
            "machine learning", "deep learning", "neural network"
        ]
    
    def collect_data(self, 
                     days_back: int = 7, 
                     max_articles: int = 25, 
                     use_cache: bool = True, 
                     **kwargs) -> Dict[str, Any]:
        """Collect data from RSS feed"""
        
        cache_file = os.path.join(self.cache_dir, f"example_{days_back}d.json")
        
        # Check cache
        if use_cache and os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            
            cache_time = datetime.fromisoformat(cached_data.get('collection_time', '2000-01-01T00:00:00'))
            now = datetime.now()
            cache_age_hours = (now - cache_time).total_seconds() / 3600
            
            if cache_age_hours < 12:  # Use cache if less than 12 hours old
                return cached_data
        
        # Parse RSS feed
        try:
            feed = feedparser.parse(self.rss_url)
            
            if not feed.entries:
                return {'articles': [], 'collection_time': datetime.now().isoformat()}
            
            # Process articles
            cutoff_date = datetime.now() - timedelta(days=days_back)
            articles = []
            
            for entry in feed.entries:
                # Parse date
                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                
                # Skip if too old
                if pub_date < cutoff_date:
                    continue
                
                # Create article object
                article = {
                    'title': entry.title,
                    'link': entry.link,
                    'summary': entry.summary,
                    'published': pub_date.isoformat(),
                    'source': 'Example RSS'
                }
                
                # Add if relevant
                if self._is_ai_related(article):
                    articles.append(article)
                
                # Limit articles
                if len(articles) >= max_articles:
                    break
            
            # Create result
            result = {
                'articles': articles,
                'collection_time': datetime.now().isoformat()
            }
            
            # Cache results
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            print(f"Error collecting RSS data: {e}")
            return {'articles': [], 'collection_time': datetime.now().isoformat()}
    
    def _is_ai_related(self, article: Dict[str, Any]) -> bool:
        """Check if article is related to AI"""
        text = f"{article['title']} {article['summary']}".lower()
        return any(keyword in text for keyword in self.ai_keywords)
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Format collected data for LLM input"""
        articles = data.get('articles', [])
        
        output = "# EXAMPLE RSS DATA\n\n"
        
        if not articles:
            output += "No recent AI articles found.\n\n"
            return output
        
        # Format each article
        for i, article in enumerate(articles, 1):
            output += f"## Article {i}: {article.get('title', '')}\n\n"
            output += f"Source: Example RSS\n"
            output += f"Published: {article.get('published', '').split('T')[0]}\n"
            output += f"Link: {article.get('link', '')}\n\n"
            
            if article.get('summary'):
                output += f"{article.get('summary')}\n\n"
            
            output += "---\n\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics about collected data"""
        articles = data.get('articles', [])
        
        return {
            "total_articles": len(articles),
            "collection_timestamp": datetime.now().isoformat()
        }
```
