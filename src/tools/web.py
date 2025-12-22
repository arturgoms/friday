"""
Friday 3.0 Web Tools

Tools for web search and fetching using SearXNG.
"""

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from src.core.registry import friday_tool

# Get SearXNG URL from environment
SEARXNG_URL = os.getenv("SEARXNG_URL", "https://searxng.arturgomes.com")


@friday_tool(name="web_search")
def web_search(
    query: str,
    num_results: int = 5,
    categories: str = "general"
) -> str:
    """Search the web using SearXNG.
    
    Use this to find current information, news, documentation, or any 
    information not available in the vault or your knowledge.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default 5, max 10)
        categories: Search categories - "general", "news", "images", "videos", "science", "it"
    
    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    try:
        num_results = min(max(1, num_results), 10)  # Clamp between 1-10
        
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
        }
        
        url = f"{SEARXNG_URL}/search?{urlencode(params)}"
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
        
        results = data.get("results", [])[:num_results]
        
        if not results:
            return f"No results found for: {query}"
        
        lines = [f"Search results for '{query}':", "=" * 50]
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "")[:200]  # Truncate long snippets
            
            lines.append(f"\n{i}. {title}")
            lines.append(f"   URL: {url}")
            if content:
                lines.append(f"   {content}...")
        
        lines.append(f"\nFound {len(results)} result(s)")
        return "\n".join(lines)
        
    except httpx.TimeoutException:
        return f"Search timed out for: {query}"
    except httpx.HTTPStatusError as e:
        return f"Search error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Search error: {e}"


@friday_tool(name="web_fetch")
def web_fetch(url: str, max_length: int = 5000) -> str:
    """Fetch and extract text content from a web page.
    
    Use this to read the full content of a webpage after finding it via web_search.
    
    Args:
        url: URL of the webpage to fetch
        max_length: Maximum characters to return (default 5000)
    
    Returns:
        Extracted text content from the page
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Friday/3.0; +https://github.com/friday-ai)"
        }
        
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            # Only process HTML/text content
            if "html" not in content_type and "text" not in content_type:
                return f"Cannot extract text from content type: {content_type}"
            
            html = response.text
        
        # Simple HTML to text extraction
        text = _html_to_text(html)
        
        if len(text) > max_length:
            text = text[:max_length] + "\n\n[Content truncated...]"
        
        if not text.strip():
            return "Could not extract text content from page"
        
        return f"Content from {url}:\n{'=' * 50}\n{text}"
        
    except httpx.TimeoutException:
        return f"Request timed out for: {url}"
    except httpx.HTTPStatusError as e:
        return f"HTTP error {e.response.status_code} for: {url}"
    except Exception as e:
        return f"Error fetching {url}: {e}"


def _html_to_text(html: str) -> str:
    """Simple HTML to text conversion without external dependencies."""
    import re
    
    # Remove script and style elements
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML comments
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    # Replace common block elements with newlines
    html = re.sub(r'<(p|div|br|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    html = re.sub(r'<[^>]+>', '', html)
    
    # Decode common HTML entities
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')
    html = html.replace('&#39;', "'")
    
    # Clean up whitespace
    lines = []
    for line in html.split('\n'):
        line = ' '.join(line.split())  # Normalize whitespace
        if line:
            lines.append(line)
    
    return '\n'.join(lines)


@friday_tool(name="web_news")
def web_news(query: str, num_results: int = 5) -> str:
    """Search for recent news articles.
    
    Use this specifically for finding news and current events.
    
    Args:
        query: News search query
        num_results: Number of results (default 5, max 10)
    
    Returns:
        Formatted news results
    """
    return web_search(query, num_results=num_results, categories="news")
