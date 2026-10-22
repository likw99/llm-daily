import os
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from .base_collector import BaseCollector

class ProductHuntCollector(BaseCollector):
    """Collector for AI products on Product Hunt"""
    
    def __init__(self, api_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the Product Hunt collector
        
        Args:
            api_token: Product Hunt API token (optional, defaults to environment variable)
            cache_dir: Directory for caching results (optional)
        """
        self.token = api_token or os.environ.get("PRODUCTHUNT_API_TOKEN")
        
        # GraphQL API endpoint
        self.api_url = "https://api.producthunt.com/v2/api/graphql"
        
        # Set up headers for API requests - important to format exactly as expected
        if self.token:
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            print(f"API token configured: {self.token[:4]}...{self.token[-4:]}")
        else:
            self.headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "producthunt"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # AI-related keywords for filtering
        self.ai_keywords = [
            "ai", "artificial intelligence", "machine learning", "deep learning", 
            "neural network", "llm", "language model", "generative", 
            "gpt", "chatgpt", "diffusion", "stable diffusion", "openai",
            "claude", "anthropic", "gemini", "mistral", "llama", "mixtral",
            "fine-tuning", "fine-tune", "rag", "text to image", "text to video",
            "text to speech", "speech to text", "image generation", "video generation"
        ]
    
    def collect_data(self, 
                     days_back: int = 7, 
                     posts_limit: int = 50, 
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect AI product data from Product Hunt
        
        Args:
            days_back: Number of days to look back
            posts_limit: Maximum number of posts to retrieve
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected Product Hunt data
        """
        cache_file = os.path.join(self.cache_dir, f"ph_posts_{days_back}d.json")
        
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
                    print(f"Using cached Product Hunt data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached Product Hunt data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Get posts from Product Hunt API using GraphQL
        posts = self._fetch_recent_posts(days_back, posts_limit)
        
        # Filter for AI-related products
        ai_products = self._filter_ai_products(posts)
        
        # Enrich top products with additional information
        enriched_products = self._enrich_products(ai_products[:15])  # Limit to top 15 for performance
        
        result = {
            'products': enriched_products,
            'total_posts': len(posts),
            'ai_products_count': len(ai_products),
            'enriched_count': len(enriched_products),
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Cached {len(enriched_products)} Product Hunt products to {cache_file}")
        except Exception as e:
            print(f"Error caching results: {e}")
        
        return result
    
    def _fetch_recent_posts(self, days_back: int, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch recent posts from Product Hunt API using GraphQL
        
        Args:
            days_back: Number of days to look back
            limit: Maximum number of posts to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of post data dictionaries
        """
        print(f"Fetching recent posts from Product Hunt (past {days_back} days)...")
        
        # For authenticated requests with a token
        if self.token:
            try:
                # Import subprocess to run curl command directly
                import subprocess
                import json
                import tempfile
                
                print("Using curl subprocess approach for API request...")
                
                # Create temp file for response
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_filename = temp_file.name
                temp_file.close()
                
                # Prepare curl command similar to the shell script
                query = '{"query": "query { posts(first: ' + str(limit) + ') { edges { node { id name tagline description url votesCount commentsCount website topics { edges { node { id name } } } featuredAt createdAt } } } }"}'
                
                curl_cmd = [
                    'curl', '-s', '-X', 'POST',
                    '-H', f'Authorization: Bearer {self.token}',
                    '-H', 'Content-Type: application/json',
                    '-H', 'Accept: application/json',
                    '-d', query,
                    'https://api.producthunt.com/v2/api/graphql',
                    '-o', temp_filename
                ]
                
                # Execute the curl command
                subprocess.run(curl_cmd, check=True)
                
                # Read the response
                with open(temp_filename, 'r') as f:
                    response_text = f.read()
                
                # Clean up temp file
                import os
                os.unlink(temp_filename)
                
                # Parse the response
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    print(f"Error parsing response as JSON: {response_text[:200]}...")
                    return self._fallback_to_web_scraping(days_back, limit)
                
                if "errors" in data:
                    print(f"GraphQL errors: {data['errors']}")
                    return self._fallback_to_web_scraping(days_back, limit)
                
                # Extract posts from the response
                posts = []
                edges = data.get("data", {}).get("posts", {}).get("edges", [])
                
                for edge in edges:
                    node = edge.get("node", {})
                    
                    # Extract topics
                    topics = []
                    try:
                        for topic_edge in node.get("topics", {}).get("edges", []):
                            topic_node = topic_edge.get("node", {})
                            topics.append(topic_node.get("name", ""))
                    except:
                        # Handle cases where topics might be incomplete
                        pass
                    
                    # Filter by date if featuredAt is available
                    try:
                        featured_at = node.get("featuredAt")
                        if featured_at:
                            featured_date = datetime.fromisoformat(featured_at.replace("Z", "+00:00"))
                            cutoff_date = datetime.now(featured_date.tzinfo) - timedelta(days=days_back)
                            if featured_date < cutoff_date:
                                continue
                    except:
                        # If date parsing fails, include the post anyway
                        pass
                    
                    post = {
                        "id": node.get("id", ""),
                        "name": node.get("name", ""),
                        "tagline": node.get("tagline", ""),
                        "description": node.get("description", ""),
                        "url": node.get("url", ""),
                        "votes_count": node.get("votesCount", 0),
                        "comments_count": node.get("commentsCount", 0),
                        "website": node.get("website", ""),
                        "topics": topics,
                        "featured_at": node.get("featuredAt", ""),
                        "created_at": node.get("createdAt", ""),
                    }
                    
                    posts.append(post)
                
                print(f"Fetched {len(posts)} posts from Product Hunt API")
                
                # Limit posts to the requested number
                return posts[:limit]
                    
            except Exception as e:
                print(f"Error fetching posts from Product Hunt API: {e}")
                print("Falling back to web scraping...")
                return self._fallback_to_web_scraping(days_back, limit)
        else:
            # No API token, fall back to web scraping
            print("No Product Hunt API token provided, falling back to web scraping")
            return self._fallback_to_web_scraping(days_back, limit)
    
    def _fallback_to_web_scraping(self, days_back: int, limit: int) -> List[Dict[str, Any]]:
        """
        Fall back to web scraping for Product Hunt data if API fails or no token is available
        
        Args:
            days_back: Number of days to look back
            limit: Maximum number of posts to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of post data dictionaries
        """
        print("Using web scraping fallback for Product Hunt data...")
        
        try:
            from bs4 import BeautifulSoup
            
            posts = []
            page = 1
            max_pages = (limit // 20) + 1  # Product Hunt shows about 20 items per page
            
            while len(posts) < limit and page <= max_pages:
                url = f"https://www.producthunt.com/posts?page={page}"
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
                }
                
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    print(f"Error: Received status code {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Product Hunt uses a lot of JavaScript, so web scraping might be limited
                # Try to find product items
                products = soup.find_all("div", {"data-test": "post-item"})
                
                if not products:
                    # Alternative: look for link elements that might be products
                    products = soup.select("a[href^='/posts/']")
                
                for product in products:
                    try:
                        # Extract available data
                        name_elem = product.select_one("h3") or product.select_one("span[font-weight='600']")
                        name = name_elem.get_text().strip() if name_elem else ""
                        
                        tagline_elem = product.select_one("p") or product.select_one("div > span:not([font-weight='600'])")
                        tagline = tagline_elem.get_text().strip() if tagline_elem else ""
                        
                        url_elem = product.select_one("a[href^='/posts/']")
                        url = f"https://www.producthunt.com{url_elem['href']}" if url_elem else ""
                        
                        votes_elem = product.select_one("div[data-test='vote-button'] span") or product.select_one("button span")
                        votes_count = int(votes_elem.get_text().strip()) if votes_elem and votes_elem.get_text().strip().isdigit() else 0
                        
                        # Create a basic post object with available data
                        post = {
                            "id": url.split("/")[-1] if url else f"scraped-{len(posts)}",
                            "name": name,
                            "tagline": tagline,
                            "description": "",
                            "url": url,
                            "votes_count": votes_count,
                            "comments_count": 0,
                            "website": "",
                            "topics": [],
                            "featured_at": datetime.now().isoformat(),
                            "created_at": datetime.now().isoformat(),
                            "thumbnail_url": "",
                            "makers": []
                        }
                        
                        posts.append(post)
                        
                        if len(posts) >= limit:
                            break
                    except Exception as e:
                        print(f"Error parsing product: {e}")
                
                page += 1
                
                # Be nice to the server
                time.sleep(2)
            
            print(f"Scraped {len(posts)} posts from Product Hunt website")
            return posts
            
        except Exception as e:
            print(f"Error scraping Product Hunt website: {e}")
            return []
    
    def _filter_ai_products(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter posts to only include AI-related products
        
        Args:
            posts: List of post data dictionaries
            
        Returns:
            List[Dict[str, Any]]: List of AI-related post data dictionaries
        """
        ai_products = []
        
        for post in posts:
            # Create a combined text from relevant fields
            combined_text = f"{post.get('name', '')} {post.get('tagline', '')} {post.get('description', '')} {' '.join(post.get('topics', []))}"
            combined_text = combined_text.lower()
            
            # Check for AI keywords
            for keyword in self.ai_keywords:
                if keyword in combined_text:
                    ai_products.append(post)
                    break
        
        print(f"Found {len(ai_products)} AI-related products out of {len(posts)} total posts")
        return ai_products
    
    def _enrich_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich products with additional information
        
        Args:
            products: List of product data dictionaries
            
        Returns:
            List[Dict[str, Any]]: List of enriched product data dictionaries
        """
        enriched_products = []
        
        for product in products:
            try:
                # If product has a URL but no description, try to fetch more details
                if product.get("url") and not product.get("description"):
                    more_info = self._fetch_product_details(product.get("url"))
                    if more_info:
                        product.update(more_info)
                
                enriched_products.append(product)
                
                # Be nice to the server
                time.sleep(1)
                
            except Exception as e:
                print(f"Error enriching product {product.get('name', '')}: {e}")
                enriched_products.append(product)
        
        return enriched_products
    
    def _fetch_product_details(self, url: str) -> Dict[str, Any]:
        """
        Fetch additional details for a product from its page
        
        Args:
            url: Product page URL
            
        Returns:
            Dict[str, Any]: Additional product details
        """
        try:
            from bs4 import BeautifulSoup
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                return {}
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Try to extract description
            description_elem = soup.select_one("div[data-test='post-detail'] p") or soup.select_one("div[data-test='description']")
            description = description_elem.get_text().strip() if description_elem else ""
            
            # Try to extract website URL
            website_elem = soup.select_one("a[data-test='product-website-url']") or soup.select_one("a[rel='noopener noreferrer'][target='_blank'][href^='http']")
            website = website_elem["href"] if website_elem else ""
            
            # Try to extract topics/tags
            topics = []
            topics_container = soup.select_one("div[data-test='topics-list']")
            if topics_container:
                topic_elems = topics_container.select("a")
                topics = [elem.get_text().strip() for elem in topic_elems if elem.get_text().strip()]
            
            return {
                "description": description,
                "website": website,
                "topics": topics if topics else []
            }
            
        except Exception as e:
            print(f"Error fetching product details: {e}")
            return {}
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        products = data.get('products', [])
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# PRODUCT HUNT AI PRODUCTS\n\n"
        
        if not products:
            output += "No AI products found on Product Hunt.\n\n"
            return output
        
        # Sort products by votes (descending)
        sorted_products = sorted(products, key=lambda x: x.get('votes_count', 0), reverse=True)
        
        # Format each product
        for i, product in enumerate(sorted_products, 1):
            output += f"## Product {i}: {product.get('name', '')}\n\n"
            
            if product.get('tagline'):
                output += f"**Tagline**: {product.get('tagline')}\n\n"
            
            output += f"**URL**: {product.get('url', '')}\n"
            
            if product.get('website'):
                output += f"**Website**: {product.get('website')}\n"
            
            output += f"**Votes**: {product.get('votes_count', 0)}\n"
            
            if product.get('comments_count'):
                output += f"**Comments**: {product.get('comments_count')}\n"
            
            if product.get('topics'):
                output += f"**Topics**: {', '.join(product.get('topics'))}\n"
            
            # Format featured date
            featured_at = product.get('featured_at', '')
            if featured_at and isinstance(featured_at, str) and 'T' in featured_at:
                output += f"**Featured**: {featured_at.split('T')[0]}\n"
            
            output += "\n"
            
            # Add description if available
            if product.get('description'):
                description = product.get('description')
                # Truncate if too long
                if len(description) > 500:
                    description = description[:500] + "... [truncated]"
                output += f"**Description**:\n{description}\n\n"
            
            # Add makers if available
            if product.get('makers'):
                output += "**Makers**:\n"
                for maker in product.get('makers'):
                    output += f"- {maker.get('name', '')} (@{maker.get('username', '')})\n"
                output += "\n"
            
            # Add a separator between entries
            output += "---\n\n"
        
        # Add summary statistics
        output += "\n## Summary Statistics\n"
        output += f"- Total AI products found: {len(products)}\n"
        output += f"- Collection date: {collection_time[:10]}\n"
        
        # Calculate average votes
        avg_votes = sum(product.get('votes_count', 0) for product in products) / max(len(products), 1)
        output += f"- Average votes: {avg_votes:.1f}\n"
        
        # Topic distribution
        topics_count = {}
        for product in products:
            for topic in product.get('topics', []):
                if topic not in topics_count:
                    topics_count[topic] = 0
                topics_count[topic] += 1
        
        if topics_count:
            output += "- Top topics:\n"
            for topic, count in sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(products)) * 100
                output += f"  - {topic}: {count} ({percentage:.1f}%)\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        products = data.get('products', [])
        
        # Count products by topic
        topic_counts = {}
        for product in products:
            for topic in product.get('topics', []):
                if topic not in topic_counts:
                    topic_counts[topic] = 0
                topic_counts[topic] += 1
        
        # Calculate average votes
        avg_votes = sum(product.get('votes_count', 0) for product in products) / max(len(products), 1)
        
        # Get most active makers
        maker_counts = {}
        for product in products:
            for maker in product.get('makers', []):
                maker_name = maker.get('name', '')
                if maker_name:
                    if maker_name not in maker_counts:
                        maker_counts[maker_name] = 0
                    maker_counts[maker_name] += 1
        
        # Sort and get top makers
        top_makers = [maker for maker, count in sorted(maker_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        # Get most common topics
        top_topics = [topic for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        return {
            "total_products": len(products),
            "avg_votes": avg_votes,
            "topic_counts": topic_counts,
            "maker_counts": maker_counts,
            "top_topics": top_topics,
            "top_makers": top_makers,
            "collection_timestamp": datetime.now().isoformat()
        }
