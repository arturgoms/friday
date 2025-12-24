"""
Friday 3.0 Embeddings

Sentence transformer embeddings for semantic search and RAG.

Usage:
    from src.core.embeddings import get_embeddings, EmbeddingsModel
    
    embeddings = get_embeddings()
    vectors = embeddings.encode(["Hello world", "How are you?"])
"""

import logging
import threading
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from .config import get_config

logger = logging.getLogger(__name__)


class EmbeddingsModel:
    """Sentence transformer embeddings model wrapper."""
    
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
        cache_dir: Optional[Path] = None
    ):
        """Initialize the embeddings model.
        
        Args:
            model_name: HuggingFace model name or path
            device: Device to run on ('cpu', 'cuda', 'mps')
            cache_dir: Optional cache directory for model files
        """
        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir
        self._model = None
        self._dimension: Optional[int] = None
    
    def _load_model(self):
        """Lazy load the model on first use."""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading embeddings model: {self.model_name}")
            
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=str(self.cache_dir) if self.cache_dir else None
            )
            
            # Get embedding dimension
            self._dimension = self._model.get_sentence_embedding_dimension()
            
            logger.info(f"Embeddings model loaded. Dimension: {self._dimension}")
            
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Failed to load embeddings model: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        self._load_model()
        return self._dimension or 384  # Default for MiniLM
    
    def encode(
        self,
        texts: Union[str, List[str]],
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """Encode texts to embeddings.
        
        Args:
            texts: Single text or list of texts to encode
            normalize: Whether to L2-normalize embeddings
            show_progress: Show progress bar for large batches
            
        Returns:
            numpy array of shape (n_texts, dimension)
        """
        self._load_model()
        
        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def encode_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """Encode a query for similarity search.
        
        Some models have different encoding for queries vs documents.
        
        Args:
            query: Query text
            normalize: Whether to normalize
            
        Returns:
            1D numpy array of shape (dimension,)
        """
        embedding = self.encode(query, normalize=normalize)
        return embedding[0]
    
    def similarity(
        self,
        query_embedding: np.ndarray,
        document_embeddings: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between query and documents.
        
        Args:
            query_embedding: Query embedding (1D or 2D)
            document_embeddings: Document embeddings (2D)
            
        Returns:
            Similarity scores array
        """
        # Ensure query is 2D
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # Cosine similarity (embeddings should be normalized)
        similarities = np.dot(document_embeddings, query_embedding.T).flatten()
        
        return similarities
    
    def most_similar(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar documents to a query.
        
        Args:
            query: Query text
            documents: List of document texts
            top_k: Number of results to return
            
        Returns:
            List of (index, document, score) tuples
        """
        query_embedding = self.encode_query(query)
        doc_embeddings = self.encode(documents)
        
        similarities = self.similarity(query_embedding, doc_embeddings)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = [
            (int(idx), documents[idx], float(similarities[idx]))
            for idx in top_indices
        ]
        
        return results


# =============================================================================
# Text Chunking Utilities
# =============================================================================

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separator: str = "\n\n"
) -> List[str]:
    """Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        separator: Preferred split point
        
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    
    # Try to split on separator first
    segments = text.split(separator)
    
    current_chunk = ""
    
    for segment in segments:
        # If adding this segment exceeds chunk size
        if len(current_chunk) + len(segment) + len(separator) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Keep overlap from end of current chunk
                if chunk_overlap > 0:
                    overlap_start = max(0, len(current_chunk) - chunk_overlap)
                    current_chunk = current_chunk[overlap_start:]
                else:
                    current_chunk = ""
        
        current_chunk += segment + separator
    
    # Add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # If chunks are still too large, split by sentences
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size * 1.5:
            # Split on sentence boundaries
            sentences = chunk.replace(". ", ".\n").split("\n")
            sub_chunk = ""
            for sentence in sentences:
                if len(sub_chunk) + len(sentence) > chunk_size:
                    if sub_chunk:
                        final_chunks.append(sub_chunk.strip())
                    sub_chunk = sentence
                else:
                    sub_chunk += " " + sentence
            if sub_chunk:
                final_chunks.append(sub_chunk.strip())
        else:
            final_chunks.append(chunk)
    
    return final_chunks


def chunk_markdown(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[dict]:
    """Chunk markdown text preserving headers as metadata.
    
    Args:
        text: Markdown text
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of dicts with 'text' and 'metadata' keys
    """
    import re
    
    # Split on headers
    header_pattern = r'^(#{1,6})\s+(.+)$'
    
    chunks = []
    current_headers = {}
    current_content = []
    
    for line in text.split("\n"):
        header_match = re.match(header_pattern, line)
        
        if header_match:
            # Save current content if any
            if current_content:
                content_text = "\n".join(current_content).strip()
                if content_text:
                    for chunk in chunk_text(content_text, chunk_size, chunk_overlap):
                        chunks.append({
                            "text": chunk,
                            "metadata": current_headers.copy()
                        })
                current_content = []
            
            # Update headers
            level = len(header_match.group(1))
            header_text = header_match.group(2)
            
            # Clear lower-level headers
            current_headers = {
                k: v for k, v in current_headers.items()
                if int(k[1:]) < level
            }
            current_headers[f"h{level}"] = header_text
        else:
            current_content.append(line)
    
    # Don't forget final content
    if current_content:
        content_text = "\n".join(current_content).strip()
        if content_text:
            for chunk in chunk_text(content_text, chunk_size, chunk_overlap):
                chunks.append({
                    "text": chunk,
                    "metadata": current_headers.copy()
                })
    
    return chunks


# =============================================================================
# Global Instance
# =============================================================================

_embeddings: Optional[EmbeddingsModel] = None
_embeddings_lock = threading.Lock()


def get_embeddings() -> EmbeddingsModel:
    """Get the global embeddings model instance (thread-safe).
    
    Returns:
        EmbeddingsModel instance
    """
    global _embeddings
    
    if _embeddings is None:
        with _embeddings_lock:
            # Double-check pattern for thread safety
            if _embeddings is None:
                config = get_config()
                _embeddings = EmbeddingsModel(
                    model_name=config.embeddings.model_name,
                    device=config.embeddings.device
                )
                logger.info(f"EmbeddingsModel initialized: {config.embeddings.model_name} on {config.embeddings.device}")
    
    return _embeddings
