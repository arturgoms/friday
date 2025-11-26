"""Web search service."""
from duckduckgo_search import DDGS
from app.core.config import settings
from app.core.logging import logger


class WebSearchService:
    """Service for web search."""
    
    def search(self, query: str, max_results: int = None) -> str:
        """Search the web using DuckDuckGo."""
        max_results = max_results or settings.top_k_web
        snippets = []
        
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    title = r.get("title") or ""
                    body = r.get("body") or ""
                    url = r.get("href") or ""
                    snippet = f"Title: {title}\nSnippet: {body}\nURL: {url}"
                    snippets.append(snippet)
            
            if not snippets:
                return ""
            
            logger.info(f"Web search returned {len(snippets)} results")
            return "\n\n--- WEB RESULT ---\n\n".join(snippets)
        
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ""


# Singleton instance
web_search_service = WebSearchService()
