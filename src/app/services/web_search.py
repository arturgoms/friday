"""Web search service using SearXNG (open-source meta-search engine)."""
import requests
from app.core.config import settings
from app.core.logging import logger


class WebSearchServiceSearXNG:
    """Service for web search using SearXNG."""
    
    def __init__(self):
        """Initialize SearXNG client."""
        # Use self-hosted instance (change to your URL after deploying)
        # Default to localhost:8888 for self-hosted instance
        import os
        self.searxng_url = os.getenv('SEARXNG_URL', 'http://localhost:8888')
        self.timeout = 10
    
    def search(self, query: str, max_results: int | None = None) -> str:
        """
        Search the web using SearXNG.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default from settings)
        
        Returns:
            Formatted search results as string
        """
        max_results = max_results if max_results is not None else settings.top_k_web
        snippets = []
        
        try:
            # SearXNG API endpoint
            url = f"{self.searxng_url}/search"
            
            params = {
                'q': query,
                'format': 'json',
                'categories': 'general',
                'language': 'en',
                'time_range': '',  # empty = no time filter
                'safesearch': 0,   # 0 = off, 1 = moderate, 2 = strict
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"SearXNG search failed with status {response.status_code}")
                return ""
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                logger.warning(f"SearXNG returned no results for: {query}")
                return ""
            
            # Format results
            for r in results[:max_results]:
                title = r.get('title', '')
                content = r.get('content', '')
                url = r.get('url', '')
                
                if title and content:
                    snippet = f"Title: {title}\nSnippet: {content}\nURL: {url}"
                    snippets.append(snippet)
            
            if not snippets:
                return ""
            
            logger.info(f"SearXNG search returned {len(snippets)} results (from {self.searxng_url})")
            return "\n\n--- WEB RESULT ---\n\n".join(snippets)
        
        except requests.exceptions.Timeout:
            logger.error(f"SearXNG search timeout for: {query}")
            return ""
        except requests.exceptions.RequestException as e:
            logger.error(f"SearXNG search request failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            return ""


# Singleton instance
web_search_service = WebSearchServiceSearXNG()
