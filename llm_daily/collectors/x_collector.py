import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .base_collector import BaseCollector
from ..utils.common import load_sources


class XCollector(BaseCollector):
    """Collector for X/Twitter data from specified lists with careful rate limit handling"""
    
    def __init__(self, bearer_token: Optional[str] = None, list_id: Optional[str] = None, config_path: Optional[str] = None):
        """
        Initialize the X collector
        
        Args:
            bearer_token: X/Twitter bearer token (optional, defaults to environment variable)
            list_id: X list ID (optional; falls back to X_LIST_ID, then x.list_id in the sources config)
            config_path: Path to the configuration file (optional)
        """
        self.bearer_token = bearer_token or os.environ.get("X_BEARER_TOKEN")
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN environment variable is required.")
        
        # List ID: argument, then X_LIST_ID env, then x.list_id in the sources config
        self.list_id = list_id or os.environ.get("X_LIST_ID") or self._load_configured_list_id(config_path)
        if not self.list_id:
            raise ValueError(
                "No X list configured. Set X_LIST_ID or x.list_id in config/sources.yaml."
            )

        # Initialize the client (tweepy is an optional extra: `uv sync --extra x`)
        import tweepy

        self._tweepy = tweepy
        self.client = tweepy.Client(bearer_token=self.bearer_token)
        
        # Cache directory
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache", "x")
        os.makedirs(self.cache_dir, exist_ok=True)
    
    @staticmethod
    def _load_configured_list_id(config_path: Optional[str] = None) -> str:
        """Read x.list_id from the sources config, or return an empty string."""
        try:
            sources = load_sources(config_path)
        except Exception as e:
            print(f"Error loading X config: {e}")
            return ""
        return str((sources.get("x") or {}).get("list_id") or "").strip()

    def _enforce_rate_limit(self):
        """
        Enforce strict rate limits for Free Tier - 1 request per 15 minutes
        """
        cache_file = os.path.join(self.cache_dir, "list_tweets_last_call.txt")
        
        # Check when we last called this endpoint
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                try:
                    last_call_time = datetime.fromisoformat(f.read().strip())
                    now = datetime.now()
                    elapsed_seconds = (now - last_call_time).total_seconds()
                    
                    # For Free Tier: 1 request per 15 minutes (900 seconds)
                    if elapsed_seconds < 900:
                        wait_seconds = 900 - elapsed_seconds + 5  # Add 5-second buffer
                        print(f"Rate limit: Must wait {wait_seconds:.1f} seconds")
                        print(f"Last call: {last_call_time.strftime('%H:%M:%S')}, Next available: {(last_call_time + timedelta(seconds=900)).strftime('%H:%M:%S')}")
                        
                        if wait_seconds > 0:
                            print(f"Waiting {wait_seconds:.1f} seconds...")
                            time.sleep(wait_seconds)
                except Exception as e:
                    print(f"Error reading last call time: {e}")
        
        # Update the last call time
        with open(cache_file, 'w') as f:
            f.write(datetime.now().isoformat())
    
    def collect_data(self, 
                     hours_back: int = 48, 
                     max_results: int = 100, 
                     use_cache: bool = True, 
                     force_refresh: bool = False, 
                     **kwargs) -> Dict[str, Any]:
        """
        Collect tweets from the list with careful rate limit handling
        
        Args:
            hours_back: Number of hours to look back for tweets
            max_results: Maximum number of tweets to retrieve (max 100)
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected tweet data
        """
        list_id = kwargs.get('list_id', self.list_id)
        cache_file = os.path.join(self.cache_dir, f"list_{list_id}_tweets.json")
        
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
                    print(f"Using cached data ({cache_age_hours:.1f} hours old)")
                    return {
                        'tweets': cached_data.get('tweets', []),
                        'list_name': cached_data.get('list_name', list_id),
                        'collection_time': cached_data.get('collection_time'),
                        'from_cache': True
                    }
                else:
                    print(f"Cached data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Get tweets with strict rate limiting
        try:
            print(f"Collecting tweets from list ID: {list_id}")
            
            # Enforce rate limit for Free Tier - THIS IS CRITICAL
            self._enforce_rate_limit()
            
            try:
                # Get tweets from the list - this is our ONLY API call
                response = self.client.get_list_tweets(
                    id=list_id,
                    max_results=max_results,
                    tweet_fields=['created_at', 'public_metrics', 'text'],
                    user_fields=['name', 'username'],
                    expansions=['author_id']
                )
            except self._tweepy.errors.TooManyRequests:
                print("Rate limit exceeded")
                # Try to use cache as fallback
                if use_cache and os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r') as f:
                            cached_data = json.load(f)
                        print("Using cached data as fallback")
                        return {
                            'tweets': cached_data.get('tweets', []),
                            'list_name': cached_data.get('list_name', list_id),
                            'collection_time': cached_data.get('collection_time'),
                            'from_cache': True,
                            'rate_limited': True
                        }
                    except Exception as e:
                        print(f"Error reading cache as fallback: {e}")
                
                # If no cache or cache read failed
                return {
                    'tweets': [],
                    'list_name': 'AI Twitter List',
                    'collection_time': datetime.now().isoformat(),
                    'from_cache': False,
                    'rate_limited': True
                }
            
            if not response.data:
                print("No tweets found in list")
                return {
                    'tweets': [],
                    'list_name': 'AI Twitter List',
                    'collection_time': datetime.now().isoformat(),
                    'from_cache': False
                }
                
            # Process tweets
            tweets = []
            
            # Create a dictionary of users for easy lookup
            users = {user.id: user for user in response.includes['users']} if 'users' in response.includes else {}
            
            # Store cutoff time as a string for comparison
            cutoff_time_str = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat()
            
            for tweet in response.data:
                # Convert tweet created_at to ISO format string to avoid datetime comparison issues
                tweet_time_str = tweet.created_at.isoformat()
                
                # Skip tweets older than cutoff time
                if tweet_time_str < cutoff_time_str:
                    continue
                    
                author = users.get(tweet.author_id)
                username = author.username if author else "unknown"
                name = author.name if author else "Unknown User"
                
                tweets.append({
                    'id': tweet.id,
                    'text': tweet.text,
                    'url': f"https://twitter.com/{username}/status/{tweet.id}",
                    'created_at': tweet_time_str,
                    'retweets': tweet.public_metrics['retweet_count'],
                    'likes': tweet.public_metrics['like_count'],
                    'replies': tweet.public_metrics['reply_count'],
                    'author_name': name,
                    'author_username': username
                })
            
            print(f"Retrieved {len(tweets)} tweets from list")
            
            # Use the name of the list from the response if possible
            # No separate get_list call is made, so a generic name is used
            list_name = "AI Twitter List"
            
            # Cache the results
            collection_time = datetime.now().isoformat()
            cache_data = {
                'list_name': list_name,
                'tweets': tweets,
                'collection_time': collection_time
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            return {
                'tweets': tweets,
                'list_name': list_name,
                'collection_time': collection_time,
                'from_cache': False
            }
                
        except Exception as e:
            print(f"Error collecting tweets: {e}")
            # Check if we have cached data to use as fallback
            if use_cache and os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        cached_data = json.load(f)
                    print("Using cached data as fallback")
                    return {
                        'tweets': cached_data.get('tweets', []),
                        'list_name': cached_data.get('list_name', list_id),
                        'collection_time': cached_data.get('collection_time'),
                        'from_cache': True
                    }
                except Exception as e:
                    print(f"Error reading cache: {e}")
            
            return {
                'tweets': [],
                'list_name': 'AI Twitter List',
                'collection_time': datetime.now().isoformat(),
                'from_cache': False,
                'error': str(e)
            }
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing the collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        tweets = data.get('tweets', [])
        list_name = data.get('list_name', 'AI Twitter List')
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# X/TWITTER DATA\n\n"
        
        output += f"## {list_name}\n\n"
        
        if not tweets:
            output += "No recent tweets collected.\n\n"
        else:
            # Sort tweets by engagement (likes + retweets)
            sorted_tweets = sorted(tweets, key=lambda x: x['likes'] + x['retweets'], reverse=True)
            
            for i, tweet in enumerate(sorted_tweets, 1):
                output += f"### Tweet {i}: @{tweet['author_username']} ({tweet['author_name']})\n"
                output += f"Likes: {tweet['likes']} | Retweets: {tweet['retweets']} | Replies: {tweet['replies']} | Posted: {tweet['created_at']}\n"
                output += f"URL: {tweet['url']}\n\n"
                output += f"{tweet['text']}\n\n"
                output += "---\n\n"
        
        # Add summary statistics
        output += "\n## Summary Stats\n"
        output += f"- List name: {list_name}\n"
        output += f"- Total tweets: {len(tweets)}\n"
        output += f"- Collection timestamp: {collection_time}\n"
        if data.get('from_cache', False):
            output += "- Data source: Cache\n"
        if data.get('rate_limited', False):
            output += "- Note: Rate limit was reached, using cached data\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        tweets = data.get('tweets', [])
        list_name = data.get('list_name', 'AI Twitter List')
        
        total_likes = sum(tweet['likes'] for tweet in tweets)
        total_retweets = sum(tweet['retweets'] for tweet in tweets)
        total_replies = sum(tweet['replies'] for tweet in tweets)
        
        return {
            "total_tweets": len(tweets),
            "total_likes": total_likes,
            "total_retweets": total_retweets,
            "total_replies": total_replies,
            "list_name": list_name,
            "collection_timestamp": datetime.now().isoformat(),
            "from_cache": data.get('from_cache', False),
            "rate_limited": data.get('rate_limited', False)
        }


if __name__ == "__main__":
    # Test the collector
    from dotenv import load_dotenv
    load_dotenv()
    
    collector = XCollector()
    formatted_data, raw_data = collector.run(hours_back=48, max_results=100)
    
    # Save to a test file
    with open("x_data_sample.md", "w") as f:
        f.write(formatted_data)
    
    stats = collector.get_statistics(raw_data)
    print(f"Collected {stats['total_tweets']} tweets with {stats['total_likes']} likes and {stats['total_retweets']} retweets.")
