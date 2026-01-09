"""
Vector Store for Friday Knowledge System

Uses ChromaDB for persistent vector storage with embeddings.
Provides CRUD operations for document indexing and semantic search.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid

import chromadb
from chromadb.config import Settings as ChromaSettings

from settings import settings
from src.core.embeddings import get_embeddings

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document to be indexed in vector store."""
    content: str
    metadata: Dict[str, Any]  # {source, section, timestamp, type, etc.}
    embedding: Optional[List[float]] = None
    doc_id: Optional[str] = None


@dataclass
class SearchResult:
    """Search result with metadata and similarity score."""
    content: str
    metadata: Dict[str, Any]
    similarity: float
    doc_id: str


class VectorStore:
    """
    ChromaDB vector store wrapper for Friday knowledge base.
    
    Stores and retrieves document chunks with semantic search.
    """
    
    def __init__(self):
        """Initialize ChromaDB with persistent storage."""
        self.store_path = settings.KNOWLEDGE["vector_store_path"]
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.store_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.collection_name = settings.KNOWLEDGE["collection_name"]
        self.embeddings_model = get_embeddings()
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Friday knowledge base - vault, person notes, conversations"}
        )
        
        logger.info(f"[VECTOR_STORE] Initialized at {self.store_path}, collection: {self.collection_name}")
    
    def add_documents(self, documents: List[Document]) -> int:
        """
        Add documents to vector store.
        
        Args:
            documents: List of documents to add
            
        Returns:
            Number of documents added
        """
        if not documents:
            return 0
        
        try:
            ids = []
            embeddings = []
            metadatas = []
            contents = []
            
            for doc in documents:
                # Generate ID if not provided
                doc_id = doc.doc_id or str(uuid.uuid4())
                ids.append(doc_id)
                
                # Generate embedding if not provided
                if doc.embedding is None:
                    # encode() returns 2D array, get first element for single doc
                    embedding = self.embeddings_model.encode(doc.content)[0].tolist()
                else:
                    embedding = doc.embedding
                
                embeddings.append(embedding)
                metadatas.append(doc.metadata)
                contents.append(doc.content)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=contents
            )
            
            logger.info(f"[VECTOR_STORE] Added {len(documents)} documents")
            return len(documents)
        
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Error adding documents: {e}", exc_info=True)
            return 0
    
    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.4,
        filter_metadata: Optional[Dict] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query: Search query text
            top_k: Maximum number of results to return
            threshold: Minimum similarity score (0-1)
            filter_metadata: Optional metadata filter (e.g., {"type": "person"})
            
        Returns:
            List of search results sorted by similarity
        """
        try:
            # Generate query embedding (encode() returns 2D, get first element)
            query_embedding = self.embeddings_model.encode(query)[0].tolist()
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,  # Get more, filter by threshold
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )
            
            # Parse results
            search_results = []
            
            if results and results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    # ChromaDB returns L2 distance (lower = more similar)
                    # Convert to similarity score (higher = more similar)
                    # For L2: similarity = 1 / (1 + distance)
                    distance = results["distances"][0][i]
                    similarity = 1.0 / (1.0 + distance)
                    
                    # Filter by threshold
                    if similarity >= threshold:
                        search_results.append(SearchResult(
                            content=results["documents"][0][i],
                            metadata=results["metadatas"][0][i],
                            similarity=similarity,
                            doc_id=results["ids"][0][i]
                        ))
            
            # Sort by similarity (descending) and limit
            search_results.sort(key=lambda x: x.similarity, reverse=True)
            search_results = search_results[:top_k]
            
            logger.info(f"[VECTOR_STORE] Search returned {len(search_results)} results (threshold: {threshold})")
            return search_results
        
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Error searching: {e}", exc_info=True)
            return []
    
    def delete_by_source(self, source: str) -> int:
        """
        Delete all documents from a specific source.
        
        Useful for reindexing a specific file or source.
        
        Args:
            source: Source identifier (e.g., file path, "conversation_history")
            
        Returns:
            Number of documents deleted
        """
        try:
            # Get all documents with this source
            results = self.collection.get(
                where={"source": source},
                include=["metadatas"]
            )
            
            if results and results["ids"]:
                count = len(results["ids"])
                self.collection.delete(ids=results["ids"])
                logger.info(f"[VECTOR_STORE] Deleted {count} documents from source: {source}")
                return count
            
            return 0
        
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Error deleting by source: {e}", exc_info=True)
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dict with stats: total_docs, by_source, by_type
        """
        try:
            # Get total count
            total = self.collection.count()
            
            # Get all metadata to analyze
            results = self.collection.get(include=["metadatas"])
            
            by_source = {}
            by_type = {}
            
            if results and results["metadatas"]:
                for metadata in results["metadatas"]:
                    # Count by source
                    source = metadata.get("source", "unknown")
                    by_source[source] = by_source.get(source, 0) + 1
                    
                    # Count by type
                    doc_type = metadata.get("type", "unknown")
                    by_type[doc_type] = by_type.get(doc_type, 0) + 1
            
            return {
                "total_docs": total,
                "by_source": by_source,
                "by_type": by_type,
                "collection_name": self.collection_name,
                "store_path": str(self.store_path)
            }
        
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Error getting stats: {e}", exc_info=True)
            return {"error": str(e)}
    
    def clear_all(self) -> bool:
        """
        Clear entire collection.
        
        WARNING: This deletes all indexed data!
        Use only for testing or full reindex.
        
        Returns:
            True if successful
        """
        try:
            # Delete and recreate collection
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Friday knowledge base - vault, person notes, conversations"}
            )
            logger.warning("[VECTOR_STORE] Cleared all documents from collection")
            return True
        
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Error clearing collection: {e}", exc_info=True)
            return False


# Global instance (lazy initialized)
_vector_store_instance = None


def get_vector_store() -> VectorStore:
    """
    Get global vector store instance (singleton).
    
    Returns:
        VectorStore instance
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
