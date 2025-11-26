"""Embedding service."""
from typing import List
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """Service for generating embeddings."""
    
    def __init__(self):
        """Initialize embedding model."""
        self.model = None
    
    def _ensure_loaded(self):
        """Lazy load the model on first use."""
        if self.model is None:
            try:
                self.model = SentenceTransformer(
                    settings.embed_model_name,
                    device='cpu'  # Keep embeddings on CPU to save GPU memory
                )
                logger.info(f"Loaded embedding model: {settings.embed_model_name} (CPU)")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        self._ensure_loaded()
        return self.model.encode(texts, show_progress_bar=False).tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        self._ensure_loaded()
        return self.model.encode([text], show_progress_bar=False)[0].tolist()


# Singleton instance
embedding_service = EmbeddingService()
