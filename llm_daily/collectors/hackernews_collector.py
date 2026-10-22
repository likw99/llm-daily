import os
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_collector import BaseCollector


class HackerNewsCollector(BaseCollector):
    """Collector for AI-related stories from Hacker News"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the HackerNews collector
        
        Args:
            cache_dir: Directory for caching results (optional)
        """
        # HackerNews API endpoints
        self.base_url = "https://hacker-news.firebaseio.com/v0"
        self.topstories_url = f"{self.base_url}/topstories.json"
        self.newstories_url = f"{self.base_url}/newstories.json"
        self.beststories_url = f"{self.base_url}/beststories.json"
        self.item_url = f"{self.base_url}/item"
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "hackernews"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # AI-related keywords for filtering stories
        self.ai_keywords = [
            # Core AI/ML terms
            "ai", "artificial intelligence", "machine learning", "deep learning",
            "neural network", "neural net", "llm", "large language model",
            "transformer", "gpt", "openai", "anthropic", "claude", "gemini",
            "chatgpt", "llama", "mistral", "mixtral", "falcon", "alpaca",
            
            # AI Applications
            "generative ai", "text-to-image", "stable diffusion", "midjourney",
            "dall-e", "text generation", "image generation", "code generation",
            "chatbot", "ai assistant", "voice assistant", "conversational ai",
            
            # Technical terms
            "fine-tuning", "fine-tune", "rag", "retrieval augmented", 
            "prompt engineering", "embedding", "vector database", "tokenizer",
            "inference", "training", "model compression", "quantization",
            
            # Companies and tools
            "hugging face", "langchain", "llamaindex", "tensorflow", "pytorch",
            "autogpt", "agent", "multimodal", "computer vision", "nlp",
            "natural language processing", "reinforcement learning"
        ]
        
        # Request session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LLM-Daily/1.0 (+https://github.com/likw99/llm-daily)'
        })
    
    def collect_data(self, 
                     hours_back: int = 24, 
                     max_stories: int = 50,
                     story_sources: List[str] = None,
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect AI-related stories from HackerNews
        
        Args:
            hours_back: Number of hours to look back for stories
            max_stories: Maximum number of stories to retrieve from each source
            story_sources: List of story sources ('top', 'new', 'best'). Default is ['top', 'new']
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected HackerNews data
        """
        if story_sources is None:
            story_sources = ['top', 'new']
            
        cache_file = os.path.join(self.cache_dir, f"hackernews_{hours_back}h.json")
        
        # Check if we're forcing a refresh
        if force_refresh:
            print("Force refresh requested, ignoring cache")
        elif use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                # Check cache age
                cache_time = datetime.fromisoformat(cached_data.get('collection_time', ''))
                cache_age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                
                if cache_age_hours < 6:  # Use cache if it's less than 6 hours old
                    print(f"Using cached HackerNews data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached HackerNews data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Collect stories from different sources
        all_stories = []
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        print(f"Fetching HackerNews stories from sources: {', '.join(story_sources)}")
        
        for source in story_sources:
            print(f"Collecting {source} stories...")
            try:
                source_stories = self._fetch_stories_from_source(source, max_stories, cutoff_time)
                all_stories.extend(source_stories)
                print(f"Found {len(source_stories)} {source} stories")
                time.sleep(1)  # Be respectful to the API
            except Exception as e:
                print(f"Error fetching {source} stories: {e}")
                continue
        
        # Remove duplicates based on story ID
        unique_stories = {}
        for story in all_stories:
            story_id = story.get('id')
            if story_id and story_id not in unique_stories:
                unique_stories[story_id] = story
        
        deduplicated_stories = list(unique_stories.values())
        print(f"Total unique stories collected: {len(deduplicated_stories)}")
        
        # Filter for AI-related content
        ai_stories = self._filter_ai_stories(deduplicated_stories)
        print(f"AI-related stories found: {len(ai_stories)}")
        
        # Sort by score and time (recent + popular first)
        sorted_stories = sorted(ai_stories, key=lambda x: (
            x.get('score', 0) * 0.7 + (1000 if self._is_recent(x, hours=12) else 0)
        ), reverse=True)
        
        result = {
            'stories': sorted_stories,
            'total_collected': len(deduplicated_stories),
            'ai_stories_count': len(ai_stories),
            'story_sources': story_sources,
            'hours_back': hours_back,
            'max_stories_per_source': max_stories,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Cached {len(ai_stories)} HackerNews stories to {cache_file}")
        except Exception as e:
            print(f"Error caching results: {e}")
        
        return result
    
    def _fetch_stories_from_source(self, source: str, max_stories: int, cutoff_time: datetime) -> List[Dict[str, Any]]:
        """Fetch stories from a specific HackerNews source"""
        
        # Get story IDs from the appropriate endpoint
        if source == 'top':
            response = self.session.get(self.topstories_url, timeout=30)
        elif source == 'new':
            response = self.session.get(self.newstories_url, timeout=30)
        elif source == 'best':
            response = self.session.get(self.beststories_url, timeout=30)
        else:
            raise ValueError(f"Unknown story source: {source}")
        
        response.raise_for_status()
        story_ids = response.json()
        
        # Limit the number of stories to fetch
        story_ids = story_ids[:max_stories * 2]  # Fetch extra to account for filtering
        
        stories = []
        
        # Fetch story details in parallel for better performance
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit requests for story details
            future_to_id = {
                executor.submit(self._fetch_story_details, story_id): story_id 
                for story_id in story_ids[:max_stories * 2]
            }
            
            for future in as_completed(future_to_id):
                try:
                    story = future.result()
                    if story and self._is_story_recent(story, cutoff_time):
                        story['source'] = source
                        stories.append(story)
                        
                        # Stop if we have enough stories
                        if len(stories) >= max_stories:
                            break
                            
                except Exception as e:
                    print(f"Error fetching story details: {e}")
                    continue
        
        return stories
    
    def _fetch_story_details(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Fetch details for a single story"""
        try:
            response = self.session.get(f"{self.item_url}/{story_id}.json", timeout=10)
            response.raise_for_status()
            story = response.json()
            
            # Filter out stories that aren't actual stories (jobs, polls, etc.)
            if story and story.get('type') == 'story' and story.get('title'):
                return {
                    'id': story.get('id'),
                    'title': story.get('title', ''),
                    'url': story.get('url', ''),
                    'score': story.get('score', 0),
                    'by': story.get('by', 'unknown'),
                    'time': story.get('time', 0),
                    'descendants': story.get('descendants', 0),  # comment count
                    'text': story.get('text', ''),  # story text if it's a text post
                    'hn_url': f"https://news.ycombinator.com/item?id={story.get('id')}"
                }
        except Exception as e:
            print(f"Error fetching story {story_id}: {e}")
            return None
    
    def _is_story_recent(self, story: Dict[str, Any], cutoff_time: datetime) -> bool:
        """Check if a story is within the time window"""
        story_time = story.get('time', 0)
        if story_time:
            story_datetime = datetime.fromtimestamp(story_time)
            return story_datetime >= cutoff_time
        return False
    
    def _is_recent(self, story: Dict[str, Any], hours: int = 12) -> bool:
        """Check if a story is recent (for ranking purposes)"""
        story_time = story.get('time', 0)
        if story_time:
            story_datetime = datetime.fromtimestamp(story_time)
            cutoff = datetime.now() - timedelta(hours=hours)
            return story_datetime >= cutoff
        return False
    
    def _filter_ai_stories(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter stories for AI-related content"""
        ai_stories = []
        
        for story in stories:
            if self._calculate_ai_relevance(story) > 0:
                story['ai_relevance_score'] = self._calculate_ai_relevance(story)
                ai_stories.append(story)
        
        return ai_stories
    
    def _calculate_ai_relevance(self, story: Dict[str, Any]) -> int:
        """Calculate AI relevance score for a story"""
        score = 0
        title = story.get('title', '').lower()
        text = story.get('text', '').lower()
        url = story.get('url', '').lower()
        
        # Check title (highest weight)
        for keyword in self.ai_keywords:
            if keyword in title:
                score += 3
        
        # Check story text (medium weight)
        for keyword in self.ai_keywords:
            if keyword in text:
                score += 2
        
        # Check URL (lower weight)
        for keyword in self.ai_keywords:
            if keyword in url:
                score += 1
        
        return score
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Format the collected data for LLM input"""
        stories = data.get('stories', [])
        collection_time = data.get('collection_time', '')
        total_collected = data.get('total_collected', 0)
        ai_stories_count = data.get('ai_stories_count', 0)
        story_sources = data.get('story_sources', [])
        hours_back = data.get('hours_back', 24)
        
        output = "# HACKER NEWS DATA\n\n"
        
        if not stories:
            output += "No AI-related stories found in the specified time period.\n"
            return output
        
        # Group stories by recency
        now = datetime.now()
        recent_stories = []  # Last 12 hours
        older_stories = []   # 12+ hours ago
        
        for story in stories:
            story_time = story.get('time', 0)
            if story_time:
                story_datetime = datetime.fromtimestamp(story_time)
                hours_ago = (now - story_datetime).total_seconds() / 3600
                
                if hours_ago <= 12:
                    recent_stories.append(story)
                else:
                    older_stories.append(story)
        
        # Recent stories section
        if recent_stories:
            output += "## Recent Stories (Last 12 Hours)\n\n"
            for i, story in enumerate(recent_stories[:15], 1):
                story_time = datetime.fromtimestamp(story.get('time', 0))
                hours_ago = (now - story_time).total_seconds() / 3600
                
                output += f"### Story {i}: {story.get('title', '')}\n\n"
                output += f"**URL**: {story.get('url', 'N/A')}\n"
                output += f"**HN Discussion**: {story.get('hn_url', '')}\n"
                output += f"**Score**: {story.get('score', 0)} points\n"
                output += f"**Comments**: {story.get('descendants', 0)}\n"
                output += f"**Author**: {story.get('by', 'unknown')}\n"
                output += f"**Time**: {hours_ago:.1f} hours ago\n"
                output += f"**Source**: {story.get('source', 'unknown')}\n"
                
                if story.get('text'):
                    # Truncate text if too long
                    text = story.get('text', '')
                    if len(text) > 300:
                        text = text[:300] + "..."
                    output += f"**Text**: {text}\n"
                
                output += f"**AI Relevance Score**: {story.get('ai_relevance_score', 0)}\n\n"
        
        # Older stories section
        if older_stories:
            output += "## Earlier Stories\n\n"
            for i, story in enumerate(older_stories[:15], 1):
                story_time = datetime.fromtimestamp(story.get('time', 0))
                hours_ago = (now - story_time).total_seconds() / 3600
                
                output += f"### Story {i}: {story.get('title', '')}\n\n"
                output += f"**URL**: {story.get('url', 'N/A')}\n"
                output += f"**HN Discussion**: {story.get('hn_url', '')}\n"
                output += f"**Score**: {story.get('score', 0)} points\n"
                output += f"**Comments**: {story.get('descendants', 0)}\n"
                output += f"**Author**: {story.get('by', 'unknown')}\n"
                output += f"**Time**: {hours_ago:.1f} hours ago\n"
                output += f"**Source**: {story.get('source', 'unknown')}\n"
                
                if story.get('text'):
                    # Truncate text if too long
                    text = story.get('text', '')
                    if len(text) > 300:
                        text = text[:300] + "..."
                    output += f"**Text**: {text}\n"
                
                output += f"**AI Relevance Score**: {story.get('ai_relevance_score', 0)}\n\n"
        
        # Summary statistics
        output += "## Summary Statistics\n"
        output += f"- Total stories collected: {total_collected}\n"
        output += f"- AI-related stories: {ai_stories_count}\n"
        output += f"- Recent stories (last 12h): {len(recent_stories)}\n"
        output += f"- Earlier stories: {len(older_stories)}\n"
        output += f"- Story sources: {', '.join(story_sources)}\n"
        output += f"- Time window: {hours_back} hours\n"
        output += f"- Collection date: {collection_time[:10] if isinstance(collection_time, str) and len(collection_time) > 10 else collection_time}\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate statistics about the collected data"""
        stories = data.get('stories', [])
        
        if not stories:
            return {
                'total_stories': 0,
                'recent_stories': 0,
                'avg_score': 0,
                'avg_comments': 0,
                'top_story_score': 0,
                'sources': [],
                'collection_timestamp': datetime.now().isoformat()
            }
        
        # Calculate statistics
        scores = [story.get('score', 0) for story in stories]
        comments = [story.get('descendants', 0) for story in stories]
        sources = list(set(story.get('source', 'unknown') for story in stories))
        
        # Count recent stories (last 12 hours)
        now = datetime.now()
        recent_count = 0
        for story in stories:
            story_time = story.get('time', 0)
            if story_time:
                story_datetime = datetime.fromtimestamp(story_time)
                hours_ago = (now - story_datetime).total_seconds() / 3600
                if hours_ago <= 12:
                    recent_count += 1
        
        return {
            'total_stories': len(stories),
            'recent_stories': recent_count,
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'avg_comments': sum(comments) / len(comments) if comments else 0,
            'top_story_score': max(scores) if scores else 0,
            'sources': sources,
            'total_collected': data.get('total_collected', 0),
            'ai_relevance_ratio': len(stories) / max(data.get('total_collected', 1), 1),
            'collection_timestamp': datetime.now().isoformat()
        }


# Test function when run directly
if __name__ == "__main__":
    import argparse
    
    # Set up argument parser for command-line testing
    parser = argparse.ArgumentParser(description="Test the HackerNewsCollector")
    parser.add_argument("--hours", type=int, default=24, help="Number of hours to look back")
    parser.add_argument("--stories", type=int, default=50, help="Maximum stories per source")
    parser.add_argument("--sources", type=str, default="top,new", help="Comma-separated list of sources (top,new,best)")
    parser.add_argument("--output", type=str, default="hackernews_data_sample.md", help="Output file for formatted data")
    parser.add_argument("--json", type=str, default="hackernews_data_sample.json", help="Output file for raw JSON data")
    parser.add_argument("--no-cache", action="store_true", help="Skip using cache")
    args = parser.parse_args()
    
    print("╔═══════════════════════════════════════╗")
    print("║     HACKERNEWS COLLECTOR TEST RUN     ║")
    print("╚═══════════════════════════════════════╝\n")
    
    # Parse sources
    sources = args.sources.split(',') if args.sources else ['top', 'new']
    
    print("Configuration:")
    print(f"• Looking back {args.hours} hours")
    print(f"• Maximum {args.stories} stories per source")
    print(f"• Sources: {', '.join(sources)}")
    print(f"• {'Not using' if args.no_cache else 'Using'} cache")
    print("─────────────────────────────────────")
    
    # Initialize collector
    collector = HackerNewsCollector()
    
    # Collect data
    print("\nCollecting data from HackerNews...")
    start_time = time.time()
    
    # Execute collection
    raw_data = collector.collect_data(
        hours_back=args.hours, 
        max_stories=args.stories,
        story_sources=sources,
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
    stories = raw_data.get('stories', [])
    
    # Save formatted output
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(formatted_data)
    
    # Save raw JSON data
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    
    print("\n╔═══════════════════════════════════════╗")
    print("║         COLLECTION RESULTS            ║")
    print("╚═══════════════════════════════════════╝")
    
    print(f"\nCollection completed in {collection_time:.2f} seconds")
    print(f"Formatting completed in {format_time:.2f} seconds")
    
    # Print story count with color coding
    story_count = stats['total_stories']
    if story_count == 0:
        print("\n❌ No AI-related stories found! Check the time window or keywords.")
    elif story_count < 5:
        print(f"\n⚠️ Only found {story_count} AI-related stories. Consider expanding the time window.")
    else:
        print(f"\n✅ Successfully collected {story_count} AI-related stories:")
    
    print(f"  • Total stories fetched: {stats['total_collected']}")
    print(f"  • AI-related stories: {story_count}")
    print(f"  • Recent stories (12h): {stats['recent_stories']}")
    print(f"  • Average score: {stats['avg_score']:.1f}")
    print(f"  • Average comments: {stats['avg_comments']:.1f}")
    print(f"  • Top story score: {stats['top_story_score']}")
    print(f"  • Sources used: {', '.join(stats['sources'])}")
    print(f"  • AI relevance ratio: {stats['ai_relevance_ratio']:.2%}")
    
    print("\nOutput files generated:")
    print(f"  • Formatted: {args.output}")
    print(f"  • Raw JSON: {args.json}")
    
    if story_count > 0:
        # Show top 3 stories
        print("\nTop 3 Stories by Score:")
        sorted_stories = sorted(stories, key=lambda x: x.get('score', 0), reverse=True)
        for i, story in enumerate(sorted_stories[:3], 1):
            print(f"  {i}. {story.get('title', 'No title')[:60]}... "
                  f"({story.get('score', 0)} points)")
