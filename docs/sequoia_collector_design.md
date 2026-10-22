# SequoiaCollector Design Document

## Overview
The SequoiaCollector will integrate Sequoia Capital's RSS feed (https://www.sequoiacap.com/rss) as a new data source for the NewsX newsletter system. This collector will follow the established pattern of existing RSS-based collectors and provide business insights for the Business section of the newsletter.

## Architecture Analysis

### Base Collector Interface
All collectors inherit from `BaseCollector` which requires implementing:
- `collect_data(**kwargs) -> Dict[str, Any]`: Main data collection method
- `format_for_llm(data: Dict[str, Any]) -> str`: Format data for LLM consumption
- Optional: `get_statistics(data: Dict[str, Any]) -> Dict[str, Any]`: Generate stats

### RSS Feed Analysis
**Feed URL**: https://www.sequoiacap.com/rss

**Structure**: Standard WordPress RSS 2.0 format with:
- `title`: Article title
- `link`: Direct link to article
- `description`: Brief summary/excerpt
- `pubDate`: Publication date
- `categories`: Topics like AI, Fintech, Funding announcements
- `content:encoded`: Full article content

**Sample Categories**: AI, Fintech, Funding announcements, Open Source, SaaS, etc.

### Integration Points

#### Business Section
The SequoiaCollector will provide data to the Business section which covers:
- Funding & Investment: VC activity, funding rounds, and investment trends
- M&A: Mergers, acquisitions, and partnerships  
- Company Updates: Major announcements from AI companies
- Market Analysis: Emerging trends and shifts in the AI market

Sequoia content fits perfectly as they publish about:
- Partnership announcements with portfolio companies
- Investment insights and market analysis
- AI industry trends and outlooks
- Portfolio company updates and funding rounds

#### Newsletter Generator Integration
The data will be passed to `_generate_business_section()` method which accepts:
- `venturebeat_data`: VentureBeat articles
- `techcrunch_data`: TechCrunch articles  
- `x_data`: Twitter/X discussions
- **NEW**: `sequoia_data`: Sequoia Capital insights

## Implementation Design

### File Structure
```
src/collectors/sequoia_collector.py
tests/test_sequoia_collector.py
```

### Class Structure
```python
class SequoiaCollector(BaseCollector):
    def __init__(self, cache_dir: Optional[str] = None)
    def collect_data(self, days_back: int = 7, max_articles: int = 15, 
                     use_cache: bool = True, force_refresh: bool = False, **kwargs) -> Dict[str, Any]
    def _fetch_articles_from_rss(self, days_back: int) -> List[Dict[str, Any]]
    def _clean_html(self, html_text: str) -> str
    def _filter_relevant_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]
    def format_for_llm(self, data: Dict[str, Any]) -> str
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]
```

### Key Features

#### Relevance Filtering
Since Sequoia covers many topics, we'll filter for AI/tech relevant content using keywords:
- AI, artificial intelligence, machine learning
- LLM, large language model, generative AI
- Tech startups, SaaS, fintech
- Investment trends, funding, venture capital
- Digital transformation, automation

#### Data Fields
Each article will include:
```python
{
    'id': str,           # Unique identifier
    'title': str,        # Article title
    'link': str,         # Direct URL
    'summary': str,      # Clean description
    'published': str,    # ISO format datetime
    'categories': List[str], # Topic categories
    'author': str,       # "Sequoia Capital"
    'source': str,       # "Sequoia Capital"
    'relevance_score': int # 1-10 AI/tech relevance
}
```

#### Caching Strategy
- Cache file: `sequoia_{days_back}d.json`
- Cache duration: 12 hours (same as other news collectors)
- Location: `data/cache/sequoia/`

### Integration with Main Pipeline

#### Command Line Arguments
Add to `main.py`:
```python
parser.add_argument("--skip-sequoia", action="store_true", 
                   help="Skip Sequoia Capital data collection")
parser.add_argument("--sequoia-days", type=int, default=7, 
                   help="Number of days to look back for Sequoia content")
parser.add_argument("--sequoia-articles", type=int, default=15, 
                   help="Maximum number of Sequoia articles to retrieve")
```

#### Data Collection Loop
Add to main collection loop:
```python
# Collect Sequoia Capital data
if not args.skip_sequoia:
    logger.info("Collecting Sequoia Capital insights...")
    try:
        collector = SequoiaCollector()
        sequoia_formatted_data, sequoia_raw_data = collector.run(
            days_back=args.sequoia_days,
            max_articles=args.sequoia_articles,
            force_refresh=args.force_refresh
        )
        sequoia_data = sequoia_formatted_data
        sequoia_stats = collector.get_statistics(sequoia_raw_data)
        
        # Save data file
        sequoia_data_file = save_output(
            sequoia_formatted_data, 
            filename=f"sequoia_data_{datetime.now().strftime('%Y-%m-%d')}.md",
            subfolder="sequoia"
        )
        logger.info(f"Sequoia data saved to {sequoia_data_file}")
        
    except Exception as e:
        logger.error(f"Error collecting Sequoia data: {str(e)}", exc_info=True)
        logger.warning("Continuing without Sequoia data...")
```

#### Newsletter Generator Updates
Update `generate_content()` method signature:
```python
def generate_content(self, 
                    # ... existing parameters ...
                    sequoia_data: Optional[str] = None,
                    sequoia_stats: Optional[Dict[str, Any]] = None) -> str:
```

Update `_create_stats_text()`:
```python
# Add Sequoia stats if available
if stats_sources.get('sequoia_stats'):
    articles_count = stats_sources['sequoia_stats'].get('total_articles', 0)
    if articles_count > 0:
        stats_text += f"We analyzed {articles_count} insights from Sequoia Capital. "
```

Update `_generate_business_section()`:
```python
def _generate_business_section(self, venturebeat_data: Optional[str] = None, 
                              techcrunch_data: Optional[str] = None,
                              x_data: Optional[str] = None,
                              sequoia_data: Optional[str] = None) -> str:
    # ... existing code ...
    
    sources = []
    if venturebeat_data:
        sources.append("VentureBeat AI news:\\n\\n" + venturebeat_data)
    if techcrunch_data:
        sources.append("TechCrunch AI news:\\n\\n" + techcrunch_data)
    if x_data:
        sources.append("X/Twitter discussions:\\n\\n" + x_data)
    if sequoia_data:
        sources.append("Sequoia Capital insights:\\n\\n" + sequoia_data)
```

## Testing Strategy

### Unit Tests
- Test RSS feed parsing with mock data
- Test article filtering and relevance scoring
- Test caching behavior
- Test error handling for network issues
- Test LLM formatting output

### Integration Tests  
- Test with live RSS feed (limited to avoid rate limiting)
- Test main.py integration with new arguments
- Test newsletter generation with Sequoia data

### Test Data
Create mock RSS responses with:
- AI-related articles (high relevance)
- Non-AI articles (low relevance)
- Malformed entries
- Empty feed responses

## Error Handling

### Network Issues
- Graceful fallback when RSS feed is unavailable
- Retry mechanism with exponential backoff
- Use cached data when fresh data unavailable

### Data Quality
- Handle missing fields in RSS entries
- Clean HTML content from descriptions
- Validate date formats and handle parsing errors
- Skip malformed entries without breaking collection

### Cache Issues
- Handle corrupted cache files
- Create cache directories if they don't exist
- Fallback to fresh data if cache is invalid

## Performance Considerations

### RSS Feed Size
- Sequoia's feed typically contains 10-20 recent articles
- Lightweight compared to other sources
- Fast parsing with feedparser library

### Relevance Filtering
- Efficient keyword matching
- Early filtering to reduce processing
- Configurable relevance threshold

### Memory Usage
- Process articles incrementally
- Limit cache size with article count limits
- Clean old cache files periodically

## Monitoring and Logging

### Collection Metrics
- Number of articles fetched
- Number after relevance filtering  
- Cache hit/miss rates
- Processing time

### Quality Metrics
- Relevance score distribution
- Categories found
- Date range of articles
- Failed article parsing count

## Future Enhancements

### Enhanced Filtering
- Machine learning-based relevance scoring
- Company name extraction and matching
- Investment amount parsing
- Geographic filtering

### Content Enrichment
- Full article content extraction
- Author information parsing
- Related company identification
- Investment trend analysis

### Analytics
- Track most relevant categories over time
- Monitor content freshness
- Analyze seasonal patterns in publishing

## Dependencies

### Required Packages
- `feedparser`: RSS feed parsing
- `requests`: HTTP requests (implicit via feedparser)
- `beautifulsoup4`: HTML cleaning (if needed)
- `python-dateutil`: Date parsing robustness

### Existing Dependencies
All required packages are already in the project:
- feedparser (used by other RSS collectors)
- datetime, json, os, time (standard library)
- typing (standard library)

## Deployment Checklist

### Code Implementation
- [ ] Create SequoiaCollector class
- [ ] Implement all required methods
- [ ] Add comprehensive error handling
- [ ] Create unit tests
- [ ] Create integration tests

### Integration
- [ ] Update main.py command line arguments
- [ ] Update main.py collection loop
- [ ] Update NewsletterGenerator parameters
- [ ] Update business section generation
- [ ] Update statistics collection

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing with live feed
- [ ] Performance testing
- [ ] Error scenario testing

### Documentation
- [ ] Update collector README
- [ ] Add usage examples
- [ ] Document new command line options
- [ ] Update architecture documentation

This design ensures the SequoiaCollector integrates seamlessly with the existing NewsX architecture while providing valuable business insights for the newsletter's Business section.
