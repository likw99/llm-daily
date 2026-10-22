# Guidelines for arXiv Data Collection

This document provides comprehensive guidelines for collecting research paper data from arXiv using their official API in accordance with their terms of service and best practices.

## Official API Documentation

Before implementing any data collection from arXiv, thoroughly review the official documentation:

- **API User Manual**: [https://info.arxiv.org/help/api/user-manual.html](https://info.arxiv.org/help/api/user-manual.html)
- **Terms of Use**: [https://info.arxiv.org/help/api/tou.html](https://info.arxiv.org/help/api/tou.html)

## API Basics

arXiv provides an API based on the Atom syndication format that allows for programmatic access to its content.

### Base URL
```
http://export.arxiv.org/api/query
```

### Query Parameters

| Parameter    | Description                                                                      |
|--------------|----------------------------------------------------------------------------------|
| search_query | The query string (required)                                                      |
| id_list      | Comma-delimited list of arXiv IDs                                                |
| start        | Offset for results (default: 0)                                                  |
| max_results  | Maximum number of results returned (default: 10, maximum: 2000)                  |
| sortBy       | Sort order (`relevance`, `lastUpdatedDate`, `submittedDate`) (default: relevance)|
| sortOrder    | Sort direction (`ascending`, `descending`) (default: descending)                 |

## Rate Limiting and Responsible Use

arXiv does not impose hard API rate limits, but requires responsible usage:

- **Request Spacing**: Leave a 3-second interval between API requests
- **Bulk Harvesting**: For bulk downloads (>100 papers), use their OAI-PMH interface instead
- **Crawl Timing**: Schedule batch requests during off-peak hours (nights and weekends in US time zones)
- **Max Results**: Limit `max_results` to reasonable values (30-50) for normal operations
- **User Agent**: Set a descriptive user agent with contact information

## Query Syntax

arXiv uses a robust query syntax for its API:

### Search Fields

| Field        | Description                                     | Example                         |
|--------------|-------------------------------------------------|---------------------------------|
| ti           | Title                                           | `ti:"large language model"`     |
| au           | Author                                          | `au:Hinton`                     |
| abs          | Abstract                                        | `abs:transformer`               |
| co           | Comment                                         | `co:acknowledgments`            |
| jr           | Journal Reference                               | `jr:"Nature 2023"`              |
| cat          | Subject Category                                | `cat:cs.CL`                     |
| all          | All fields                                      | `all:ChatGPT`                   |

### Boolean Operators
- `AND`: Logical AND (default operator between terms)
- `OR`: Logical OR
- `ANDNOT`: Logical NOT
- Parentheses can be used for grouping

### Examples
- Basic search: `search_query=ti:"large language model" AND cat:cs.CL`
- Date range: `search_query=submittedDate:[20220101 TO 20221231] AND cat:cs.AI`
- Complex query: `search_query=(ti:"GPT" OR ti:"ChatGPT") AND (cat:cs.CL OR cat:cs.AI) ANDNOT au:"OpenAI"`

## Response Parsing

arXiv API returns responses in Atom XML format. Key points for parsing:

### Namespaces
```
xmlns="http://www.w3.org/2005/Atom"
xmlns:arxiv="http://arxiv.org/schemas/atom"
```

### Entry Structure
Each paper is contained in an `<entry>` element with:
- `<title>`: Paper title
- `<id>`: arXiv ID URL
- `<published>`: Initial publication date
- `<updated>`: Last update date
- `<summary>`: Abstract
- `<author>`: Author information (multiple elements possible)
- `<category>`: Subject classification (multiple elements possible)
- `<link>`: Links to different versions (PDF, HTML, etc.)
- `<arxiv:primary_category>`: Primary category
- `<arxiv:comment>`: Comments from author
- `<arxiv:journal_ref>`: Journal reference if published

## Implementation Best Practices

### Error Handling
- Implement exponential backoff for retries
- Handle network failures gracefully
- Parse XML with error handling to manage malformed responses

### Caching
- Cache responses for 24 hours to minimize API calls
- Implement a local database to store paper information
- Use conditional requests if available

### Filtering
- Filter results post-query rather than crafting overly complex queries
- Process date filtering client-side for more accurate control

### Data Storage
- Save both raw XML and processed data
- Implement proper database indexing for efficient access
- Regularly clean up old cache entries

## LLM-Specific Recommendations

For our specific use case of collecting LLM-related research papers:

### Recommended Query Categories
- `cs.CL`: Computation and Language
- `cs.AI`: Artificial Intelligence
- `cs.LG`: Machine Learning
- `cs.NE`: Neural and Evolutionary Computing

### Effective Search Terms
- "large language model"
- "LLM"
- "foundation model"
- "transformer"
- Model-specific terms: "GPT", "Claude", "Llama", "Mistral", "Gemini", "PaLM"
- Technique-specific: "fine-tuning", "instruction tuning", "RLHF", "alignment"

### Collection Strategy
1. Use broad queries with model-agnostic terms like "large language model" or "LLM"
2. Use model-specific queries to catch papers about specific implementations
3. Use technique-specific queries to find methodological papers
4. Set a reasonable timeframe for the newsletter (7-30 days)
5. Sort by submission date for the most recent papers
6. Cache results to avoid redundant API calls

## Sample Implementation

The following code demonstrates proper arXiv API usage:

```python
import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta
import os
import json

def fetch_arxiv_papers(query, max_results=30):
    """Fetch papers from arXiv with proper rate limiting"""
    base_url = "http://export.arxiv.org/api/query"
    
    params = {
        "search_query": query,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    headers = {
        "User-Agent": "NewsX/1.0 (https://github.com/username/newsx; email@example.com)"
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Exception during API call: {e}")
        return None
    finally:
        # Always respect rate limits
        time.sleep(3)
```

## Ethical Considerations

When collecting data from arXiv:

1. **Attribution**: Always properly cite papers and include arXiv IDs
2. **Privacy**: Respect author information and do not scrape additional data
3. **Load**: Minimize impact on their infrastructure through responsible querying
4. **Purpose**: Use the data for legitimate research or informational purposes
5. **Sharing**: Do not redistribute bulk downloads of papers

## Troubleshooting

Common issues and solutions:

1. **No results**: Check your query syntax and try broader terms
2. **XML parsing errors**: Use robust parsers with namespace handling
3. **Timeouts**: Implement connection timeouts and retry logic
4. **Categories not matching**: Verify category codes in the documentation

## Resources

- arXiv API Examples: [https://info.arxiv.org/help/api/examples.html](https://info.arxiv.org/help/api/examples.html)
- OAI-PMH Interface (for bulk collection): [https://info.arxiv.org/help/oa/index.html](https://info.arxiv.org/help/oa/index.html)
- arXiv API Python Library: [https://pypi.org/project/arxiv/](https://pypi.org/project/arxiv/)
