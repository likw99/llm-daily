import os
import json
import requests
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import base64

from .base_collector import BaseCollector

class GitHubCollector(BaseCollector):
    """Collector for trending AI repositories on GitHub with optimized language-specific approach"""
    
    def __init__(self, github_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the GitHub collector
        
        Args:
            github_token: GitHub API token (optional, defaults to environment variable)
            cache_dir: Directory for caching results (optional)
        """
        self.token = github_token or os.environ.get("GITHUB_TOKEN")
        
        # Set up headers for API requests
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}
        
        # Add a user agent to avoid 403 errors
        self.user_agent = {"User-Agent": "LLM-Daily/1.0 (+https://github.com/likw99/llm-daily)"}
        if self.headers:
            self.headers.update(self.user_agent)
        else:
            self.headers = self.user_agent
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "github"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Define target language trending pages
        self.target_languages = [
            "jupyter-notebook",
            "python",
            "typescript"
        ]
        
        # AI-related keywords for filtering - categorized by relevance
        self.high_relevance_keywords = [
            "llm", "large language model", "gpt", "llama", "mistral", "claude", "gemini",
            "diffusion", "stable diffusion", "text-to-image", "dall-e", "midjourney",
            "transformer", "attention mechanism", "fine-tuning", "fine-tune",
            "rag", "retrieval augmented", "vector database", "embeddings",
            "prompt engineering", "agent", "multimodal", "multi-modal"
        ]
        
        self.medium_relevance_keywords = [
            "machine learning", "deep learning", "neural network",
            "artificial intelligence", "ai model", "ml model",
            "tensorflow", "pytorch", "hugging face", "langchain", "llamaindex",
            "embedding", "tokenizer", "inference", "openai", "anthropic",
            "chatbot", "text generation", "image generation"
        ]
        
        self.context_keywords = [
            "model", "training", "inference", "pipeline",
            "optimization", "vectors", "tokens", "chat"
        ]
    
    def collect_data(self, 
                     days_back: int = 7, 
                     per_page: int = 25, 
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect trending AI repositories from GitHub using language-specific trending pages
        
        Args:
            days_back: Number of days to look back (not directly used in trending scrape)
            per_page: Maximum number of repositories to return
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected repository data
        """
        cache_file = os.path.join(self.cache_dir, "ai_repos_trending.json")
        
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
                
                if cache_age_hours < 24:  # Use cache if it's less than 24 hours old
                    print(f"Using cached GitHub data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached GitHub data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Initialize tracking
        all_repos = []
        seen_ids = set()  # For deduplication
        language_counts = {}
        
        # Scrape each target language trending page
        for language in self.target_languages:
            print(f"Scraping trending {language} repositories...")
            trending_repos = self._scrape_trending_page(language=language)
            
            # Track language counts
            language_counts[language] = len(trending_repos)
            
            # Add to all repos
            for repo in trending_repos:
                repo_full_name = repo.get('full_name')
                if repo_full_name and repo_full_name not in seen_ids:
                    seen_ids.add(repo_full_name)
                    all_repos.append(repo)
            
            # Be nice to GitHub, add delay between requests
            time.sleep(2)
        
        print(f"Collected {len(all_repos)} trending repositories across {len(self.target_languages)} languages")
        
        # Filter for AI-related repositories
        ai_repos = self._filter_ai_repos(all_repos)
        
        # If we don't have enough AI repositories, try the API as fallback
        if len(ai_repos) < per_page and self.token:
            missing_count = per_page - len(ai_repos)
            print(f"Only found {len(ai_repos)} AI repositories from trending pages, looking for {missing_count} more via API...")
            api_repos = self._search_ai_repositories_fallback(days_back, missing_count)
            
            # Add API results, avoiding duplicates
            for repo in api_repos:
                repo_full_name = repo.get('full_name')
                if repo_full_name and repo_full_name not in seen_ids:
                    seen_ids.add(repo_full_name)
                    ai_repos.append(repo)
        
        # Sort by stars (descending)
        sorted_repos = sorted(ai_repos, key=lambda x: x.get('stargazers_count', 0), reverse=True)
        
        # Limit to the requested number
        if len(sorted_repos) > per_page:
            sorted_repos = sorted_repos[:per_page]
        
        # Enrich top repositories with additional information
        max_to_enrich = min(15, len(sorted_repos))
        enriched_repos = self._enrich_repositories(sorted_repos[:max_to_enrich])
        
        # Add the non-enriched repositories
        if max_to_enrich < len(sorted_repos):
            enriched_repos.extend(sorted_repos[max_to_enrich:])
        
        # Prepare result
        result = {
            'repositories': enriched_repos,
            'trending_count': len([r for r in enriched_repos if r.get('source') == 'trending_page']),
            'api_count': len([r for r in enriched_repos if r.get('source') == 'api_search']),
            'language_counts': language_counts,
            'total_repos': len(all_repos),
            'ai_repos_count': len(ai_repos),
            'enriched_count': max_to_enrich,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Cached {len(enriched_repos)} GitHub repositories")
        except Exception as e:
            print(f"Error caching results: {e}")
        
        return result
    
    def _scrape_trending_page(self, language: str = None, time_period: str = "daily") -> List[Dict[str, Any]]:
        """
        Scrape the GitHub trending page for a specific language
        
        Args:
            language: Programming language to filter by
            time_period: Time period for trending (daily, weekly, monthly)
            
        Returns:
            List[Dict[str, Any]]: List of repository data dictionaries
        """
        # Build URL
        url = "https://github.com/trending"
        if language:
            url += f"/{language}"
        url += f"?since={time_period}"
        
        print(f"Fetching trending repositories from: {url}")
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code} from {url}")
                return []
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            trending_repos = []
            # Find all repository articles in the trending list
            repo_articles = soup.select("article.Box-row")
            
            for article in repo_articles:
                try:
                    # Extract title/full name
                    title_elem = article.select_one("h2 a")
                    if not title_elem:
                        continue
                        
                    # Clean up the repository name
                    repo_path = title_elem["href"].strip()
                    if repo_path.startswith("/"):
                        repo_path = repo_path[1:]  # Remove leading slash
                    
                    # Split owner and name
                    owner, name = repo_path.split("/")
                    
                    # Extract description
                    desc_elem = article.select_one("p")
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # Extract language
                    lang_elem = article.select_one("[itemprop='programmingLanguage']")
                    repo_language = lang_elem.get_text(strip=True) if lang_elem else None
                    
                    # Extract stars and forks
                    stat_elems = article.select("a.Link--muted")
                    stars = 0
                    forks = 0
                    if len(stat_elems) > 0:
                        stars_text = stat_elems[0].get_text(strip=True).replace(",", "")
                        stars = int(stars_text) if stars_text.isdigit() else 0
                    if len(stat_elems) > 1:
                        forks_text = stat_elems[1].get_text(strip=True).replace(",", "")
                        forks = int(forks_text) if forks_text.isdigit() else 0
                    
                    # Extract stars today
                    today_elem = article.select_one("span.d-inline-block.float-sm-right")
                    stars_today = 0
                    if today_elem:
                        today_text = today_elem.get_text(strip=True)
                        today_text = today_text.replace("stars today", "").replace(",", "").strip()
                        stars_today = int(today_text) if today_text.isdigit() else 0
                    
                    # Extract topics if available
                    topics = []
                    topics_elem = article.select_one("div.topic-tag-list")
                    if topics_elem:
                        topic_tags = topics_elem.select("a.topic-tag")
                        topics = [tag.get_text(strip=True) for tag in topic_tags]
                    
                    # Create repository object
                    repo = {
                        "owner": owner,
                        "name": name,
                        "full_name": f"{owner}/{name}",
                        "html_url": f"https://github.com/{owner}/{name}",
                        "description": description,
                        "language": repo_language,
                        "stargazers_count": stars,
                        "forks_count": forks,
                        "stars_today": stars_today,
                        "topics": topics,
                        "source": "trending_page",
                        "trending_language": language,
                        "trending_period": time_period,
                        "collection_time": datetime.now().isoformat()
                    }
                    
                    # Calculate an AI relevance score for later filtering
                    repo["ai_relevance_score"] = self._calculate_ai_relevance(repo)
                    
                    trending_repos.append(repo)
                    
                except Exception as e:
                    print(f"Error parsing repository article: {e}")
            
            print(f"Scraped {len(trending_repos)} repositories from {language} trending page")
            return trending_repos
            
        except Exception as e:
            print(f"Error scraping trending page for {language}: {e}")
            return []
    
    def _calculate_ai_relevance(self, repo: Dict[str, Any]) -> int:
        """
        Calculate AI relevance score for a repository
        
        Args:
            repo: Repository data dictionary
            
        Returns:
            int: AI relevance score (higher is more relevant)
        """
        score = 0
        
        # Create a combined text from relevant fields for searching
        repo_name = repo.get('name', '').lower()
        repo_full_name = repo.get('full_name', '').lower()
        description = repo.get('description', '').lower()
        topics = [t.lower() for t in repo.get('topics', [])]
        
        # Check for high relevance keywords (strong indicators)
        for keyword in self.high_relevance_keywords:
            # Higher weight in name
            if keyword in repo_name:
                score += 10
            # Higher weight in full name
            elif keyword in repo_full_name:
                score += 8
            # Medium weight in description
            elif keyword in description:
                score += 5
            # Check in topics
            elif any(keyword in topic for topic in topics):
                score += 7
        
        # Check for medium relevance keywords
        for keyword in self.medium_relevance_keywords:
            if keyword in repo_name:
                score += 5
            elif keyword in repo_full_name:
                score += 4
            elif keyword in description:
                score += 3
            elif any(keyword in topic for topic in topics):
                score += 4
        
        # Check for context keywords (only count if multiple appear or with other relevance)
        context_matches = 0
        for keyword in self.context_keywords:
            if keyword in repo_name or keyword in description or any(keyword in topic for topic in topics):
                context_matches += 1
        
        # Only add context keywords score if multiple appear or score is already positive
        if (context_matches > 1) or (context_matches > 0 and score > 0):
            score += context_matches
        
        # Give bonus for trending AI-related languages
        if repo.get('language') in ['Python', 'Jupyter Notebook', 'TypeScript']:
            score += 1
        
        # Give bonus for star momentum
        stars_today = repo.get('stars_today', 0)
        if stars_today > 50:
            score += 3
        elif stars_today > 20:
            score += 2
        elif stars_today > 10:
            score += 1
        
        return score
    
    def _filter_ai_repos(self, repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter repositories to only include AI-related ones
        
        Args:
            repos: List of repository data dictionaries
            
        Returns:
            List[Dict[str, Any]]: Filtered list of AI-related repositories
        """
        ai_repos = []
        ai_threshold = 5  # Minimum score to be considered AI-related
        
        for repo in repos:
            # If score was already calculated, use it
            score = repo.get('ai_relevance_score', 0)
            
            # If not, calculate it
            if score == 0:
                score = self._calculate_ai_relevance(repo)
            
            # Include repositories with score above threshold
            if score >= ai_threshold:
                # Store the score for later sorting
                repo['ai_relevance_score'] = score
                ai_repos.append(repo)
        
        print(f"Filtered {len(ai_repos)} AI-related repositories out of {len(repos)}")
        return ai_repos
    
    def _search_ai_repositories_fallback(self, days_back: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fallback method to search for AI-related repositories using GitHub API
        
        Args:
            days_back: Number of days to look back
            limit: Maximum number of repositories to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of repository data dictionaries
        """
        # If no token, skip API search to avoid rate limits
        if not self.token:
            print("No GitHub token provided, skipping API search to avoid rate limits")
            return []
        
        # Date range for search
        date_query = f"created:>{days_back}d"
        
        all_repos = []
        headers = self.headers
        
        # Try searching for the most specific AI terms
        search_queries = [
            f"topic:llm {date_query}",
            f"topic:large-language-model {date_query}",
            f"topic:ai-agents {date_query}"
        ]
        
        for query in search_queries:
            try:
                url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={min(limit, 30)}"
                
                print(f"Searching GitHub API with query: {query}")
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    repos = result.get("items", [])
                    print(f"Found {len(repos)} repositories with query '{query}'")
                    
                    # Process repositories
                    for repo in repos:
                        processed_repo = {
                            "id": repo.get("id"),
                            "name": repo.get("name"),
                            "owner": repo.get("owner", {}).get("login"),
                            "full_name": repo.get("full_name"),
                            "html_url": repo.get("html_url"),
                            "description": repo.get("description"),
                            "created_at": repo.get("created_at"),
                            "updated_at": repo.get("updated_at"),
                            "pushed_at": repo.get("pushed_at"),
                            "stargazers_count": repo.get("stargazers_count", 0),
                            "forks_count": repo.get("forks_count", 0),
                            "open_issues_count": repo.get("open_issues_count", 0),
                            "topics": repo.get("topics", []),
                            "language": repo.get("language"),
                            "source": "api_search",
                            "search_query": query
                        }
                        all_repos.append(processed_repo)
                else:
                    print(f"Error {response.status_code}: {response.text}")
                
                # If we have enough repositories, stop searching
                if len(all_repos) >= limit:
                    break
                    
                # Be nice to the API
                time.sleep(2)
            
            except Exception as e:
                print(f"Error searching with query '{query}': {e}")
        
        # Filter results for AI relevance
        ai_repos = self._filter_ai_repos(all_repos)
        
        print(f"API search found {len(ai_repos)} AI-related repositories")
        return ai_repos
    
    def _get_repository_readme(self, owner: str, repo_name: str) -> Optional[str]:
        """
        Get the README content for a repository
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Optional[str]: README content if available
        """
        url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                readme_data = response.json()
                # README content is base64 encoded
                content = base64.b64decode(readme_data.get("content", "")).decode("utf-8")
                return content
            else:
                print(f"Error getting README for {owner}/{repo_name}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error getting README for {owner}/{repo_name}: {e}")
            return None
    
    def _get_recent_commits(self, owner: str, repo_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get recent commits for a repository
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            limit: Maximum number of commits to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of recent commits
        """
        url = f"https://api.github.com/repos/{owner}/{repo_name}/commits?per_page={limit}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                commits_data = response.json()
                
                commits = []
                for commit in commits_data:
                    commit_data = commit.get("commit", {})
                    commits.append({
                        "sha": commit.get("sha", "")[:7],  # Short SHA
                        "message": commit_data.get("message", "").split('\n')[0],  # Just the first line
                        "author": commit_data.get("author", {}).get("name", "Unknown"),
                        "date": commit_data.get("author", {}).get("date", "")
                    })
                return commits
            else:
                print(f"Error getting commits for {owner}/{repo_name}: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting commits for {owner}/{repo_name}: {e}")
            return []
    
    def _enrich_repositories(self, repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich repository data with additional information
        
        Args:
            repos: List of repository data dictionaries
            
        Returns:
            List[Dict[str, Any]]: List of enriched repository data dictionaries
        """
        enriched_repos = []
        
        for repo in repos:
            try:
                owner = repo.get("owner")
                name = repo.get("name")
                
                if not owner or not name:
                    enriched_repos.append(repo)
                    continue
                
                # Get README content
                readme_content = self._get_repository_readme(owner, name)
                if readme_content:
                    repo["readme_excerpt"] = readme_content[:1000] if len(readme_content) > 1000 else readme_content
                
                # Get recent commits
                recent_commits = self._get_recent_commits(owner, name, 3)
                if recent_commits:
                    repo["recent_commits"] = recent_commits
                
                # Add to enriched repos
                enriched_repos.append(repo)
                
                # Be nice to the API
                time.sleep(1)
                
            except Exception as e:
                print(f"Error enriching repository {repo.get('full_name', '')}: {e}")
                enriched_repos.append(repo)
        
        return enriched_repos
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        repositories = data.get('repositories', [])
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# GITHUB TRENDING AI PROJECTS\n\n"
        
        if not repositories:
            output += "No trending AI repositories found.\n\n"
            return output
        
        # Sort repositories by stars (descending)
        sorted_repos = sorted(repositories, key=lambda x: x.get('stargazers_count', 0), reverse=True)
        
        # Format each repository
        for i, repo in enumerate(sorted_repos, 1):
            output += f"## Project {i}: {repo.get('full_name', '')}\n\n"
            output += f"**URL**: {repo.get('html_url', '')}\n"
            
            if repo.get('description'):
                output += f"**Description**: {repo.get('description')}\n\n"
            
            # Add metadata
            output += f"**Language**: {repo.get('language') or 'Not specified'}\n"
            output += f"**Stars**: {repo.get('stargazers_count', 0)}"
            
            if repo.get('stars_today'):
                output += f" (+{repo.get('stars_today')} today)"
            
            output += f"\n**Forks**: {repo.get('forks_count', 0)}\n"
            
            # Add topics if available
            if repo.get('topics'):
                output += f"**Topics**: {', '.join(repo.get('topics'))}\n"
            
            output += "\n"
            
            # Add README excerpt if available
            if repo.get('readme_excerpt'):
                excerpt = repo.get('readme_excerpt')
                # Truncate if too long
                if len(excerpt) > 500:
                    excerpt = excerpt[:500] + "... [truncated]"
                output += f"**README Excerpt**:\n{excerpt}\n\n"
            
            # Add recent commits if available
            if repo.get('recent_commits'):
                output += "**Recent Commits**:\n"
                for commit in repo.get('recent_commits'):
                    # Only show first line of commit message
                    message = commit.get('message', '').split('\n')[0]
                    date = commit.get('date', '').split('T')[0]  # Just show the date part
                    output += f"- {date}: {message}\n"
                output += "\n"
            
            # Add a separator between entries
            output += "---\n\n"
        
        # Add summary statistics
        output += "\n## Summary Statistics\n"
        output += f"- Total AI repositories found: {len(repositories)}\n"
        output += f"- Collection date: {collection_time[:10]}\n"
        
        # Calculate average metrics
        avg_stars = sum(repo.get('stargazers_count', 0) for repo in repositories) / max(len(repositories), 1)
        avg_forks = sum(repo.get('forks_count', 0) for repo in repositories) / max(len(repositories), 1)
        
        output += f"- Average stars: {avg_stars:.1f}\n"
        output += f"- Average forks: {avg_forks:.1f}\n"
        
        # Language distribution
        lang_count = {}
        for repo in repositories:
            lang = repo.get('language')
            if lang:
                if lang not in lang_count:
                    lang_count[lang] = 0
                lang_count[lang] += 1
        
        if lang_count:
            output += "- Language distribution:\n"
            for lang, count in sorted(lang_count.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(repositories)) * 100
                output += f"  - {lang}: {count} ({percentage:.1f}%)\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        repositories = data.get('repositories', [])
        
        # Count repositories by language
        language_counts = {}
        for repo in repositories:
            language = repo.get('language')
            if language:
                if language not in language_counts:
                    language_counts[language] = 0
                language_counts[language] += 1
        
        # Calculate average metrics
        avg_stars = sum(repo.get('stargazers_count', 0) for repo in repositories) / max(len(repositories), 1)
        avg_forks = sum(repo.get('forks_count', 0) for repo in repositories) / max(len(repositories), 1)
        
        # Get most common topics
        topic_counts = {}
        for repo in repositories:
            for topic in repo.get('topics', []):
                if topic not in topic_counts:
                    topic_counts[topic] = 0
                topic_counts[topic] += 1
        
        # Sort and get top topics
        top_topics = [topic for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        # Count by source
        trending_count = len([r for r in repositories if r.get('source') == 'trending_page'])
        api_count = len([r for r in repositories if r.get('source') == 'api_search'])
        
        return {
            "total_repos": len(repositories),
            "language_counts": language_counts,
            "avg_stars": avg_stars,
            "avg_forks": avg_forks,
            "top_topics": top_topics,
            "api_count": api_count,
            "trending_count": trending_count,
            "collection_timestamp": datetime.now().isoformat()
        }