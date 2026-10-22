import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from json import JSONEncoder

from huggingface_hub import HfApi

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

from .base_collector import BaseCollector

class HuggingFaceCollector(BaseCollector):
    """Collector for trending AI repositories on Hugging Face Hub"""
    
    def __init__(self, hf_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the Hugging Face collector
        
        Args:
            hf_token: Hugging Face API token (optional, defaults to environment variable)
            cache_dir: Directory for caching results (optional)
        """
        self.token = hf_token or os.environ.get("HF_TOKEN")
        
        # Initialize HfApi client
        self.api = HfApi(token=self.token)
        
        # Cache directory
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "cache", "huggingface"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # AI-related keywords for filtering
        self.ai_keywords = [
            "llm", "large language model", "language model", "transformer", 
            "gpt", "bert", "diffusion", "generative", "text-to-image",
            "text-generation", "chat", "instruct", "rag", "embedding",
            "fine-tuned", "fine-tune", "mistral", "llama", "mixtral",
            "claude", "ai", "ml", "machine learning", "deep learning"
        ]
    
    def collect_data(self, 
                     days_back: int = 30, 
                     model_limit: int = 30,
                     dataset_limit: int = 15,
                     space_limit: int = 15,
                     use_cache: bool = True, 
                     force_refresh: bool = False,
                     sort_option: str = "trendingScore",
                     **kwargs) -> Dict[str, Any]:
        """
        Collect trending models, datasets, and spaces from Hugging Face Hub
        
        Args:
            days_back: Number of days to look back
            model_limit: Maximum number of models to retrieve
            dataset_limit: Maximum number of datasets to retrieve
            space_limit: Maximum number of spaces to retrieve
            use_cache: Whether to use cached data if available
            force_refresh: Whether to force a refresh of the data
            sort_option: How to sort results ('trendingScore', 'likes', 'downloads', 'lastModified')
            **kwargs: Additional parameters
            
        Returns:
            Dict[str, Any]: Dictionary containing collected Hugging Face data
        """
        cache_file = os.path.join(self.cache_dir, f"hf_trending_{days_back}d_{sort_option}.json")
        
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
                    print(f"Using cached Hugging Face data ({cache_age_hours:.1f} hours old)")
                    return cached_data
                else:
                    print(f"Cached Hugging Face data is {cache_age_hours:.1f} hours old, fetching fresh data")
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Validate sort option
        valid_sort_options = ["trendingScore", "likes", "downloads", "lastModified"]
        if sort_option not in valid_sort_options:
            print(f"Invalid sort option: {sort_option}. Using 'trendingScore' instead.")
            sort_option = "trendingScore"
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Collect trending models
        print(f"Collecting {sort_option} models from Hugging Face...")
        models = self._collect_trending_models(cutoff_date, model_limit, sort_option)
        
        # Collect trending datasets
        print(f"Collecting {sort_option} datasets from Hugging Face...")
        datasets = self._collect_trending_datasets(cutoff_date, dataset_limit, sort_option)
        
        # Collect trending spaces
        print(f"Collecting {sort_option} spaces from Hugging Face...")
        spaces = self._collect_trending_spaces(cutoff_date, space_limit, sort_option)
        
        # REMOVED: No longer enriching models with README content
        enriched_models = models  # Just use the models as-is without README enrichment
        
        result = {
            'models': enriched_models,
            'datasets': datasets,
            'spaces': spaces,
            'model_count': len(models),
            'dataset_count': len(datasets),
            'space_count': len(spaces),
            'enriched_model_count': len(enriched_models),
            'sort_option': sort_option,
            'collection_time': datetime.now().isoformat()
        }
        
        # Cache the results
        try:
            with open(cache_file, 'w') as f:
                # Use custom JSON encoder to handle datetime objects
                json.dump(result, f, indent=2, cls=DateTimeEncoder)
            print(f"Cached Hugging Face data to {cache_file}")
        except Exception as e:
            print(f"Error caching results: {e}")
        
        return result
    
    def _collect_trending_models(self, cutoff_date: datetime, limit: int = 30, sort_option: str = "trendingScore") -> List[Dict[str, Any]]:
        """
        Collect trending models from Hugging Face Hub
        
        Args:
            cutoff_date: Cutoff date for model creation/update
            limit: Maximum number of models to retrieve
            sort_option: How to sort results ('trendingScore', 'likes', 'downloads', 'lastModified')
            
        Returns:
            List[Dict[str, Any]]: List of model data dictionaries
        """
        try:
            print(f"Fetching models sorted by '{sort_option}'...")
            
            # Get models using the requested sort option
            models = []
            
            # Try to use the requested sort_option, with fallback
            try:
                # First retrieve the models using the API with specified sort option
                model_list = self.api.list_models(
                    limit=limit*2,  # Get more to filter for AI-related
                    sort=sort_option,
                    direction=-1,  # Descending order
                    fetch_config=True
                )
                
                # Convert iterator to list for multiple iterations
                model_items = list(model_list)
                print(f"Retrieved {len(model_items)} models from HF API")
                
            except ValueError as e:
                # If trendingScore isn't supported, fallback to likes
                print(f"Error with '{sort_option}' sort, falling back to likes: {e}")
                print("This can happen if the HuggingFace Hub API version doesn't support 'trendingScore' yet")
                
                model_list = self.api.list_models(
                    limit=limit*2,  # Get more to filter for AI-related
                    sort="likes",
                    direction=-1,  # Descending order
                    fetch_config=True
                )
                
                # Convert iterator to list
                model_items = list(model_list)
                print(f"Retrieved {len(model_items)} models using fallback sort")
                
                sort_option = "likes"  # Update the sort option to reflect what we used
            
            # Process model data
            for model_info in model_items:
                # Skip models older than cutoff date
                try:
                    last_modified = datetime.fromisoformat(model_info.last_modified.replace('Z', '+00:00'))
                    if last_modified < cutoff_date:
                        continue
                except (ValueError, AttributeError):
                    # If we can't parse the date, include the model anyway
                    pass
                
                # Process model data
                model_data = {
                    'id': model_info.id,
                    'name': model_info.id.split('/')[-1],
                    'author': model_info.id.split('/')[0],
                    'likes': model_info.likes,
                    'downloads': getattr(model_info, 'downloads', None),
                    'tags': getattr(model_info, 'tags', []),
                    'pipeline_tag': getattr(model_info, 'pipeline_tag', None),
                    'last_modified': model_info.last_modified,
                    'url': f"https://huggingface.co/{model_info.id}",
                    'source': f'{sort_option}_sort'
                }
                
                # Only add if it's AI-related
                if self._is_ai_related(model_data):
                    models.append(model_data)
                
                # If we have enough AI-related models, stop collecting
                if len(models) >= limit:
                    break
            
            print(f"Collected {len(models)} AI-related models from Hugging Face")
            return models
            
        except Exception as e:
            print(f"Error collecting models from Hugging Face: {e}")
            return []

    def _collect_trending_datasets(self, cutoff_date: datetime, limit: int = 15, sort_option: str = "trendingScore") -> List[Dict[str, Any]]:
        """
        Collect trending datasets from Hugging Face Hub
        
        Args:
            cutoff_date: Cutoff date for dataset creation/update
            limit: Maximum number of datasets to retrieve
            sort_option: How to sort results ('trendingScore', 'likes', 'downloads', 'lastModified')
            
        Returns:
            List[Dict[str, Any]]: List of dataset data dictionaries
        """
        try:
            print(f"Fetching datasets sorted by '{sort_option}'...")
            
            # Try to use the requested sort_option, with fallback
            try:
                dataset_list = self.api.list_datasets(
                    limit=limit*2,  # Get more to filter
                    sort=sort_option,
                    direction=-1  # Descending order
                )
                
                # Convert iterator to list
                dataset_items = list(dataset_list)
                print(f"Retrieved {len(dataset_items)} datasets from HF API")
                
            except ValueError as e:
                # If trendingScore isn't supported, fallback to likes
                print(f"Error with '{sort_option}' sort, falling back to likes: {e}")
                
                dataset_list = self.api.list_datasets(
                    limit=limit*2,  # Get more to filter
                    sort="likes",
                    direction=-1  # Descending order
                )
                
                # Convert iterator to list
                dataset_items = list(dataset_list)
                print(f"Retrieved {len(dataset_items)} datasets using fallback sort")
                
                sort_option = "likes"  # Update the sort option to reflect what we used
            
            # Make sure cutoff_date is timezone naive if needed
            if cutoff_date.tzinfo is not None:
                # Convert to naive
                cutoff_date = cutoff_date.replace(tzinfo=None)
            
            datasets = []
            for dataset_info in dataset_items:
                # Process dataset data - handle fields carefully
                try:
                    dataset_data = {
                        'id': dataset_info.id,
                        'name': dataset_info.id.split('/')[-1] if '/' in dataset_info.id else dataset_info.id,
                        'author': dataset_info.id.split('/')[0] if '/' in dataset_info.id else 'unknown',
                        'likes': getattr(dataset_info, 'likes', 0),
                        'tags': getattr(dataset_info, 'tags', []),
                        'url': f"https://huggingface.co/datasets/{dataset_info.id}",
                        'source': f'{sort_option}_sort'
                    }
                    
                    # Handle last_modified date
                    try:
                        # Check if last_modified exists and convert to consistent format
                        last_modified = None
                        
                        if hasattr(dataset_info, 'last_modified'):
                            last_modified_value = dataset_info.last_modified
                        elif hasattr(dataset_info, 'lastModified'):
                            last_modified_value = dataset_info.lastModified
                        else:
                            last_modified_value = None
                        
                        # Convert the date string to a datetime object if it's a string
                        if isinstance(last_modified_value, str):
                            if 'T' in last_modified_value:
                                # Remove timezone info for consistent comparison
                                last_modified = datetime.fromisoformat(last_modified_value.replace('Z', ''))
                            else:
                                last_modified = datetime.fromisoformat(last_modified_value)
                        else:
                            # If it's already a datetime object
                            last_modified = last_modified_value
                            # Make naive if needed
                            if last_modified and last_modified.tzinfo is not None:
                                last_modified = last_modified.replace(tzinfo=None)
                        
                        # Add to dataset data
                        dataset_data['last_modified'] = str(last_modified) if last_modified else None
                        
                        # Skip datasets older than cutoff date
                        if last_modified and last_modified < cutoff_date:
                            continue
                        
                    except Exception as date_error:
                        print(f"Date handling error for dataset {dataset_info.id}: {date_error}")
                        # If we can't parse the date, include the dataset anyway
                        dataset_data['last_modified'] = str(datetime.now())
                    
                    # Handle downloads separately as it might be causing issues
                    try:
                        if hasattr(dataset_info, 'downloads'):
                            dataset_data['downloads'] = dataset_info.downloads
                    except Exception:
                        dataset_data['downloads'] = None
                    
                    # Only add if it's AI-related
                    if self._is_ai_related(dataset_data):
                        datasets.append(dataset_data)
                    
                    # If we have enough AI-related datasets, stop collecting
                    if len(datasets) >= limit:
                        break
                        
                except Exception as e:
                    print(f"Error processing dataset {getattr(dataset_info, 'id', 'unknown')}: {e}")
            
            print(f"Collected {len(datasets)} AI-related datasets from Hugging Face")
            return datasets
            
        except Exception as e:
            print(f"Error collecting datasets from Hugging Face: {e}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
            return []

    def _collect_trending_spaces(self, cutoff_date: datetime, limit: int = 15, sort_option: str = "trendingScore") -> List[Dict[str, Any]]:
        """
        Collect trending spaces from Hugging Face Hub
        
        Args:
            cutoff_date: Cutoff date for space creation/update
            limit: Maximum number of spaces to retrieve
            sort_option: How to sort results ('trendingScore', 'likes', 'downloads', 'lastModified')
            
        Returns:
            List[Dict[str, Any]]: List of space data dictionaries
        """
        try:
            print(f"Fetching spaces sorted by '{sort_option}'...")
            
            # Try to use the requested sort_option, with fallback
            try:
                space_list = self.api.list_spaces(
                    limit=limit*2,  # Get more to filter
                    sort=sort_option,
                    direction=-1  # Descending order
                )
                
                # Convert iterator to list
                space_items = list(space_list)
                print(f"Retrieved {len(space_items)} spaces from HF API")
                
            except ValueError as e:
                # If trendingScore isn't supported, fallback to likes
                print(f"Error with '{sort_option}' sort, falling back to likes: {e}")
                
                space_list = self.api.list_spaces(
                    limit=limit*2,  # Get more to filter
                    sort="likes",
                    direction=-1  # Descending order
                )
                
                # Convert iterator to list
                space_items = list(space_list)
                print(f"Retrieved {len(space_items)} spaces using fallback sort")
                
                sort_option = "likes"  # Update the sort option to reflect what we used
            
            spaces = []
            for space_info in space_items:
                # Skip spaces older than cutoff date
                try:
                    last_modified = datetime.fromisoformat(space_info.last_modified.replace('Z', '+00:00'))
                    if last_modified < cutoff_date:
                        continue
                except (ValueError, AttributeError):
                    # If we can't parse the date, include the space anyway
                    pass
                
                # Process space data
                space_data = {
                    'id': space_info.id,
                    'name': space_info.id.split('/')[-1],
                    'author': space_info.id.split('/')[0],
                    'likes': space_info.likes,
                    'tags': getattr(space_info, 'tags', []),
                    'sdk': getattr(space_info, 'sdk', None),
                    'last_modified': space_info.last_modified,
                    'url': f"https://huggingface.co/spaces/{space_info.id}",
                    'source': f'{sort_option}_sort'
                }
                
                # Only add if it's AI-related
                if self._is_ai_related(space_data):
                    spaces.append(space_data)
                
                # If we have enough AI-related spaces, stop collecting
                if len(spaces) >= limit:
                    break
            
            print(f"Collected {len(spaces)} AI-related spaces from Hugging Face")
            return spaces
            
        except Exception as e:
            print(f"Error collecting spaces from Hugging Face: {e}")
            return []
    
    def _is_ai_related(self, item: Dict[str, Any]) -> bool:
        """
        Check if an item is AI-related
        
        Args:
            item: Item data dictionary
            
        Returns:
            bool: True if item is AI-related, False otherwise
        """
        # Create a combined text from relevant fields
        combined_text = f"{item.get('id', '')} {' '.join(str(i) for i in item.get('tags', []))}"
        combined_text = combined_text.lower()
        
        # Natural language models and text generation are always AI-related
        if item.get('pipeline_tag') in ["text-generation", "text2text-generation", "text-classification", "token-classification"]:
            return True
        
        # Check for AI keywords
        for keyword in self.ai_keywords:
            if keyword.lower() in combined_text:
                return True
        
        return False
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Format the collected data for LLM input
        
        Args:
            data: Dictionary containing collected data
            
        Returns:
            str: Formatted text for LLM input
        """
        models = data.get('models', [])
        datasets = data.get('datasets', [])
        spaces = data.get('spaces', [])
        sort_option = data.get('sort_option', 'trendingScore')
        collection_time = data.get('collection_time', datetime.now().isoformat())
        
        output = "# HUGGING FACE HUB TRENDING CONTENT\n\n"
        
        # Format trending models
        output += "## Trending Models\n\n"
        
        if not models:
            output += "No trending AI models found.\n\n"
        else:
            for i, model in enumerate(models[:15], 1):  # Limit to top 15
                output += f"### Model {i}: {model.get('id', '')}\n\n"
                output += f"**URL**: {model.get('url', '')}\n"
                output += f"**Likes**: {model.get('likes', 0)}\n"
                
                if model.get('downloads'):
                    output += f"**Downloads**: {model.get('downloads')}\n"
                
                if model.get('tags'):
                    tags = model.get('tags', [])
                    if isinstance(tags, list) and tags:
                        output += f"**Tags**: {', '.join(tags)}\n"
                
                if model.get('model_type'):
                    output += f"**Model Type**: {model.get('model_type')}\n"
                
                if model.get('language'):
                    output += f"**Language**: {model.get('language')}\n"
                
                if model.get('license'):
                    output += f"**License**: {model.get('license')}\n"
                
                last_modified = model.get('last_modified', '')
                if last_modified and isinstance(last_modified, str) and 'T' in last_modified:
                    output += f"**Last Modified**: {last_modified.split('T')[0]}\n\n"
                else:
                    output += f"**Last Modified**: {last_modified}\n\n"
                
                output += "---\n\n"
        
        # Format trending datasets
        output += "## Trending Datasets\n\n"
        
        if not datasets:
            output += "No trending AI datasets found.\n\n"
        else:
            for i, dataset in enumerate(datasets[:10], 1):  # Limit to top 10
                output += f"### Dataset {i}: {dataset.get('id', '')}\n\n"
                output += f"**URL**: {dataset.get('url', '')}\n"
                output += f"**Likes**: {dataset.get('likes', 0)}\n"
                
                if dataset.get('downloads'):
                    output += f"**Downloads**: {dataset.get('downloads')}\n"
                
                if dataset.get('tags'):
                    tags = dataset.get('tags', [])
                    if isinstance(tags, list) and tags:
                        output += f"**Tags**: {', '.join(tags)}\n"
                
                last_modified = dataset.get('last_modified', '')
                if last_modified and isinstance(last_modified, str) and 'T' in last_modified:
                    output += f"**Last Modified**: {last_modified.split('T')[0]}\n\n"
                else:
                    output += f"**Last Modified**: {last_modified}\n\n"
                
                output += "---\n\n"
        
        # Format trending spaces
        output += "## Trending Spaces\n\n"
        
        if not spaces:
            output += "No trending AI spaces found.\n\n"
        else:
            for i, space in enumerate(spaces[:10], 1):  # Limit to top 10
                output += f"### Space {i}: {space.get('id', '')}\n\n"
                output += f"**URL**: {space.get('url', '')}\n"
                output += f"**Likes**: {space.get('likes', 0)}\n"
                
                if space.get('sdk'):
                    output += f"**SDK**: {space.get('sdk')}\n"
                
                if space.get('tags'):
                    tags = space.get('tags', [])
                    if isinstance(tags, list) and tags:
                        output += f"**Tags**: {', '.join(tags)}\n"
                
                last_modified = space.get('last_modified', '')
                if last_modified and isinstance(last_modified, str) and 'T' in last_modified:
                    output += f"**Last Modified**: {last_modified.split('T')[0]}\n\n"
                else:
                    output += f"**Last Modified**: {last_modified}\n\n"
                
                output += "---\n\n"
        
        # Add summary statistics
        output += "## Summary Statistics\n"
        output += f"- Total AI models: {len(models)}\n"
        output += f"- Total AI datasets: {len(datasets)}\n"
        output += f"- Total AI spaces: {len(spaces)}\n"
        output += f"- Collection date: {collection_time[:10] if isinstance(collection_time, str) and len(collection_time) > 10 else collection_time}\n"
        output += f"- Sort option used: {sort_option}\n"
        
        return output
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics about the collected data
        
        Args:
            data: Dictionary with collected data
            
        Returns:
            Dict[str, Any]: Statistics about the collected data
        """
        models = data.get('models', [])
        datasets = data.get('datasets', [])
        spaces = data.get('spaces', [])
        
        # Count models by author
        author_counts = {}
        for model in models:
            author = model.get('author')
            if author:
                if author not in author_counts:
                    author_counts[author] = 0
                author_counts[author] += 1
        
        # Get most common tags
        tag_counts = {}
        for model in models:
            for tag in model.get('tags', []):
                if tag not in tag_counts:
                    tag_counts[tag] = 0
                tag_counts[tag] += 1
        
        # Sort and get top authors and tags
        top_authors = [author for author, count in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        top_tags = [tag for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        return {
            "total_models": len(models),
            "total_datasets": len(datasets),
            "total_spaces": len(spaces),
            "author_counts": author_counts,
            "tag_counts": tag_counts,
            "top_authors": top_authors,
            "top_tags": top_tags,
            "sort_option": data.get('sort_option', 'trendingScore'),
            "collection_timestamp": datetime.now().isoformat()
        }