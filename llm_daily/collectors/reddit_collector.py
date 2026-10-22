import os
import praw
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from ..utils.common import load_sources
from .base_collector import BaseCollector


class RedditCollector(BaseCollector):
    """Collector for Reddit data from specified subreddits"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the Reddit collector
        
        Args:
            config_path: Path to the configuration file (optional)
        """
        # Initialize Reddit API client
        self.reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID"),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
            user_agent=os.environ.get("REDDIT_USER_AGENT", "llm-daily/1.0")
        )
        
        # Load subreddits from data sources file
        self.subreddits = self._load_subreddits(config_path)
        
    DEFAULT_SUBREDDITS = [
        "LocalLLaMA", "MachineLearning", "StableDiffusion", "OpenAI",
        "ClaudeAI", "ChatGPT", "Oobabooga",
    ]

    def _load_subreddits(self, config_path: Optional[str] = None) -> List[str]:
        """
        Load active subreddit names from the sources config.

        Falls back to DEFAULT_SUBREDDITS if the config cannot be read.
        """
        try:
            sources = load_sources(config_path)
            entries = (sources.get("reddit") or {}).get("subreddits") or []
            return [e["name"] for e in entries if e.get("active", True)]
        except Exception as e:
            print(f"Error loading subreddit config: {e}")
            return list(self.DEFAULT_SUBREDDITS)

    def collect_data(self, time_period: int = 24, limit: int = 10, **kwargs) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect top posts from each subreddit within the specified time period
        
        Args:
            time_period: Time period in hours to look back
            limit: Maximum number of posts to collect per subreddit
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary with subreddit names as keys and lists of post data as values
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_period)
        collected_data = {}
        
        for configured_name in self.subreddits:
            subreddit_name = configured_name.split('/')[-1]
            
            print(f"Collecting posts from r/{subreddit_name}...")
            
            posts = []
            try:
                # Get top posts from the subreddit
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # First try hot posts
                for post in subreddit.hot(limit=limit*2):  # Get more to filter by time
                    post_time = datetime.utcfromtimestamp(post.created_utc)
                    if post_time >= cutoff_time:
                        # Get top comments
                        post.comments.replace_more(limit=0)  # Don't fetch MoreComments
                        top_comments = [comment.body for comment in list(post.comments)[:3] if hasattr(comment, 'body')]
                        
                        posts.append({
                            'title': post.title,
                            'url': f"https://www.reddit.com{post.permalink}",
                            'score': post.score,
                            'num_comments': post.num_comments,
                            'created_utc': post_time.isoformat(),
                            'author': str(post.author) if post.author else "[deleted]",
                            'selftext': post.selftext if hasattr(post, 'selftext') else "",
                            'top_comments': top_comments,
                            'subreddit': subreddit_name
                        })
                        
                        if len(posts) >= limit:
                            break
                
                collected_data[subreddit_name] = posts
                
            except Exception as e:
                print(f"Error collecting posts from r/{subreddit_name}: {e}")
                collected_data[subreddit_name] = []
        
        return collected_data
    
    def format_for_llm(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format the collected data for input to the LLM
        
        Args:
            data: Dictionary with subreddit names and post data
            
        Returns:
            str: Formatted text for LLM input
        """
        formatted_text = "# REDDIT DATA\n\n"
        
        for subreddit, posts in data.items():
            formatted_text += f"## r/{subreddit}\n\n"
            
            if not posts:
                formatted_text += "No recent posts collected.\n\n"
                continue
                
            for i, post in enumerate(posts, 1):
                formatted_text += f"### Post {i}: {post['title']}\n"
                formatted_text += f"Score: {post['score']} | Comments: {post['num_comments']} | Author: {post['author']} | Posted: {post['created_utc']}\n"
                formatted_text += f"URL: {post['url']}\n\n"
                
                # Include post content if available
                if post['selftext']:
                    # Truncate if too long
                    selftext = post['selftext']
                    if len(selftext) > 500:
                        selftext = selftext[:500] + "... [truncated]"
                    formatted_text += f"Content:\n{selftext}\n\n"
                
                # Include top comments
                if post['top_comments']:
                    formatted_text += "Top comments:\n"
                    for j, comment in enumerate(post['top_comments'], 1):
                        comment_text = comment
                        if len(comment_text) > 200:
                            comment_text = comment_text[:200] + "... [truncated]"
                        formatted_text += f"- Comment {j}: {comment_text}\n"
                    formatted_text += "\n"
                
                formatted_text += "---\n\n"
        
        # Add statistics about the data
        total_posts = sum(len(posts) for posts in data.values())
        total_subreddits = len(data)
        formatted_text += "\n## Summary Statistics\n"
        formatted_text += f"- Total subreddits: {total_subreddits}\n"
        formatted_text += f"- Total posts: {total_posts}\n"
        formatted_text += f"- Collection timestamp: {datetime.now().isoformat()}\n"
        
        return formatted_text
    
    def get_statistics(self, data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with subreddit names and post data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        total_posts = sum(len(posts) for posts in data.values())
        total_comments = sum(sum(post['num_comments'] for post in posts) for posts in data.values())
        subreddit_count = len(data)
        
        return {
            "total_posts": total_posts,
            "total_comments": total_comments,
            "subreddit_count": subreddit_count,
            "collection_timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Test the collector
    from dotenv import load_dotenv
    load_dotenv()
    
    collector = RedditCollector()
    formatted_data, raw_data = collector.run(time_period=48, limit=5)
    
    # Save to a test file
    with open("reddit_data_sample.md", "w") as f:
        f.write(formatted_data)
    
    stats = collector.get_statistics(raw_data)
    print(f"Collected {stats['total_posts']} posts from {stats['subreddit_count']} subreddits with approximately {stats['total_comments']} comments.")
