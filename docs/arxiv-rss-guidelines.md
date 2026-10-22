# arXiv RSS Feed Guidelines

This document outlines how to effectively use arXiv's official RSS feeds to monitor new research papers. RSS (Really Simple Syndication) provides a lightweight alternative to the arXiv API for tracking new submissions in specific categories.

## Official Documentation

For the most up-to-date information, refer to arXiv's official RSS documentation:
- **RSS Feeds Documentation**: [https://info.arxiv.org/help/rss.html](https://info.arxiv.org/help/rss.html)

## Available RSS Feeds

arXiv provides several types of RSS feeds:

### 1. New Submissions Feeds

These feeds provide information about new papers submitted to arXiv.

**URL Format**:
```
https://export.arxiv.org/rss/CATEGORY
```

Where `CATEGORY` is the arXiv category code (e.g., `cs.CL`, `cs.AI`).

**Examples**:
- Computer Science - Artificial Intelligence: [https://export.arxiv.org/rss/cs.AI](https://export.arxiv.org/rss/cs.AI)
- Computer Science - Computation and Language: [https://export.arxiv.org/rss/cs.CL](https://export.arxiv.org/rss/cs.CL)
- Computer Science - Machine Learning: [https://export.arxiv.org/rss/cs.LG](https://export.arxiv.org/rss/cs.LG)

### 2. Recent Updates Feeds

These feeds include both new submissions and cross-lists to the specified category.

**URL Format**:
```
https://export.arxiv.org/rss/CATEGORY?version=2.0
```

**Examples**:
- Recent Updates in CS - AI: [https://export.arxiv.org/rss/cs.AI?version=2.0](https://export.arxiv.org/rss/cs.AI?version=2.0)

### 3. Author Feeds

These feeds provide updates on papers by a specific author.

**URL Format**:
```
https://export.arxiv.org/a/AUTHOR_ID.rss2
```

Where `AUTHOR_ID` is the arXiv author identifier.

### 4. Search Result Feeds

arXiv allows subscribing to search result feeds.

**URL Format**:
```
https://export.arxiv.org/rss/search_query?search_query=QUERY
```

Where `QUERY` is a URL-encoded search query.

**Examples**:
- Papers with "large language model" in the title:
  ```
  https://export.arxiv.org/rss/search_query?search_query=ti:"large+language+model"
  ```

## Feed Contents

Each feed entry typically contains:

- Title of the paper
- Authors
- Categories/subjects
- Abstract (summary)
- Publication and update dates
- Links to the paper (abstract page and PDF)
- arXiv ID

## Refresh Rate

- arXiv RSS feeds are updated **once per day** when new papers are announced
- New papers are typically announced Sunday through Thursday at 8:00 PM Eastern Time
- Updates to existing papers follow the same schedule

## Recommended Usage for LLM Newsletter

For an LLM-focused newsletter, consider these specific RSS feeds:

### Primary Categories
- `cs.CL` (Computation and Language)
- `cs.AI` (Artificial Intelligence)
- `cs.LG` (Machine Learning)

### Search-Based Feeds
For more targeted content, use search query feeds:

1. **LLM-specific papers**:
   ```
   https://export.arxiv.org/rss/search_query?search_query=ti:"large+language+model"+OR+ti:LLM
   ```

2. **Popular model papers**:
   ```
   https://export.arxiv.org/rss/search_query?search_query=ti:GPT+OR+ti:BERT+OR+ti:Llama+OR+ti:Claude+OR+ti:Gemini
   ```

3. **LLM capabilities and techniques**:
   ```
   https://export.arxiv.org/rss/search_query?search_query=(ti:reasoning+OR+ti:alignment+OR+ti:RLHF)+AND+(ti:"language+model"+OR+ti:LLM)
   ```

## Benefits of RSS vs API

For newsletter purposes, RSS feeds offer several advantages:

1. **Simplicity**: No authentication or API keys required
2. **No Rate Limits**: Unlike the API, RSS has no usage quotas
3. **Built-in Timing**: Feeds are automatically updated daily with new submissions
4. **Lightweight**: Minimal processing required to parse

## Implementation Considerations

When using RSS feeds for your newsletter:

1. **Fetch Frequency**: Check feeds once daily after the arXiv update time
2. **Avoid Duplicates**: Track previously processed papers by arXiv ID
3. **Combine Feeds**: Merge multiple feeds and remove duplicates for comprehensive coverage
4. **Parse Effectively**: Use standard RSS parsing libraries (e.g., `feedparser` in Python)
5. **Cache Results**: Store feed data locally to avoid unnecessary requests

## Limitations

Be aware of these limitations when using RSS:

1. **Limited Parameters**: Cannot sort or filter as flexibly as the API
2. **Fixed Content**: Feeds contain predetermined fields; cannot request additional metadata
3. **No Advanced Search**: Complex queries may require multiple feeds or additional filtering
4. **Entry Lifespan**: Entries may drop from the feed as new papers are published

## Monitoring Multiple Feeds Example

For LLM newsletter purposes, a comprehensive monitoring approach might include:

1. **Core Categories**: 
   - cs.CL (Computation and Language)
   - cs.AI (Artificial Intelligence)
   - cs.LG (Machine Learning)

2. **Specialized Queries**:
   - Large language models (LLMs)
   - Foundation models
   - Model architectures (transformers, etc.)
   - Training techniques (RLHF, fine-tuning)
   - Evaluation and benchmarking

3. **Key Institutions**: Author feeds from:
   - OpenAI researchers
   - Anthropic researchers
   - DeepMind teams
   - Leading university AI labs

## Etiquette and Best Practices

While RSS doesn't have strict rate limits, follow these best practices:

1. **Cache Feed Content**: Store feed data locally and refresh only once a day
2. **Use Conditional Requests**: Implement HTTP caching with ETag and If-None-Match headers
3. **Link Back**: Always include proper attribution and links to original arXiv papers
4. **Respect Attribution**: Credit authors appropriately in your newsletter

## Resources

- **arXiv Categories**: [https://arxiv.org/category_taxonomy](https://arxiv.org/category_taxonomy)
- **arXiv API Documentation**: [https://info.arxiv.org/help/api/index.html](https://info.arxiv.org/help/api/index.html)
- **arXiv Terms of Use**: [https://info.arxiv.org/help/api/tou.html](https://info.arxiv.org/help/api/tou.html)
