"""
Friday 3.0 Context Builder

Builds context for LLM prompts using RAG and user profiles.

Usage:
    from src.core.context import ContextBuilder, get_context_builder
    
    builder = get_context_builder()
    context = builder.build("user123", "What's my schedule?")
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import get_config
from .vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context for LLM prompts using RAG and user profiles."""
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        brain_path: Optional[Path] = None,
        top_k: int = 5
    ):
        """Initialize the context builder.
        
        Args:
            vector_store: Vector store for RAG
            brain_path: Path to Obsidian vault
            top_k: Number of RAG results to include
        """
        self.vector_store = vector_store
        self.brain_path = brain_path
        self.top_k = top_k
        
        self._user_profiles: Dict[str, str] = {}
    
    def _get_vector_store(self) -> VectorStore:
        """Get the vector store."""
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        return self.vector_store
    
    def _get_brain_path(self) -> Path:
        """Get the brain path."""
        if self.brain_path is None:
            config = get_config()
            self.brain_path = config.paths.brain
        return self.brain_path
    
    def load_user_profile(self, user_id: str) -> Optional[str]:
        """Load user profile from brain folder.
        
        Looks for a markdown file with the user's name in the brain folder.
        
        Args:
            user_id: User identifier
            
        Returns:
            Profile content or None if not found
        """
        if user_id in self._user_profiles:
            return self._user_profiles[user_id]
        
        config = get_config()
        brain_path = self._get_brain_path()
        
        # Try to find profile file
        profile_file = config.user.profile_file
        possible_paths = [
            brain_path / profile_file,
            brain_path / "1. Notes" / profile_file,
            brain_path / "profiles" / profile_file,
        ]
        
        for path in possible_paths:
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    self._user_profiles[user_id] = content
                    logger.info(f"Loaded user profile from {path}")
                    return content
                except Exception as e:
                    logger.error(f"Error loading profile from {path}: {e}")
        
        logger.debug(f"No profile found for user {user_id}")
        return None
    
    def get_relevant_context(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get relevant context from vector store.
        
        Args:
            query: Search query
            top_k: Number of results (default: self.top_k)
            
        Returns:
            List of relevant document chunks
        """
        try:
            store = self._get_vector_store()
            results = store.search(query, top_k=top_k or self.top_k)
            return results
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return []
    
    def format_rag_context(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG results for inclusion in prompt.
        
        Args:
            results: Search results from vector store
            
        Returns:
            Formatted context string
        """
        if not results:
            return ""
        
        parts = ["## Relevant Knowledge\n"]
        
        for i, result in enumerate(results, 1):
            source = result.get("metadata", {}).get("source", "unknown")
            text = result.get("text", "")
            score = result.get("score", 0)
            
            # Only include high-relevance results
            if score < 0.3:
                continue
            
            parts.append(f"### [{source}] (relevance: {score:.2f})")
            parts.append(text)
            parts.append("")
        
        return "\n".join(parts) if len(parts) > 1 else ""
    
    def format_user_profile(self, profile: str) -> str:
        """Format user profile for inclusion in prompt.
        
        Args:
            profile: Raw profile content
            
        Returns:
            Formatted profile string
        """
        if not profile:
            return ""
        
        # Truncate if too long
        max_length = 2000
        if len(profile) > max_length:
            profile = profile[:max_length] + "\n...[truncated]"
        
        return f"## User Profile\n{profile}\n"
    
    def build(
        self,
        user_id: str,
        query: str,
        include_profile: bool = True,
        include_rag: bool = True,
        include_time: bool = True
    ) -> str:
        """Build the full context for a prompt.
        
        Args:
            user_id: User identifier
            query: User's query
            include_profile: Whether to include user profile
            include_rag: Whether to include RAG context
            include_time: Whether to include current time
            
        Returns:
            Combined context string
        """
        parts = []
        
        # Add current time
        if include_time:
            now = datetime.now()
            config = get_config()
            
            # Adjust for user timezone
            # Note: This is a simple offset, not proper timezone handling
            offset_hours = config.user.timezone_offset_hours
            if offset_hours:
                from datetime import timedelta
                now = now + timedelta(hours=offset_hours)
            
            parts.append(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            parts.append(f"Day of week: {now.strftime('%A')}")
            parts.append("")
        
        # Add user profile
        if include_profile:
            profile = self.load_user_profile(user_id)
            if profile:
                parts.append(self.format_user_profile(profile))
        
        # Add RAG context
        if include_rag and query:
            results = self.get_relevant_context(query)
            rag_context = self.format_rag_context(results)
            if rag_context:
                parts.append(rag_context)
        
        return "\n".join(parts)
    
    def build_for_query(
        self,
        user_id: str,
        query: str
    ) -> str:
        """Convenience method to build context for a query.
        
        This is the main method called by the agent.
        
        Args:
            user_id: User identifier
            query: User's query
            
        Returns:
            Context string for system prompt
        """
        return self.build(user_id, query)


# =============================================================================
# Global Instance
# =============================================================================

_context_builder: Optional[ContextBuilder] = None


def get_context_builder() -> ContextBuilder:
    """Get the global context builder instance.
    
    Returns:
        ContextBuilder instance
    """
    global _context_builder
    
    if _context_builder is None:
        config = get_config()
        _context_builder = ContextBuilder(
            top_k=config.memory.rag_top_k
        )
    
    return _context_builder
