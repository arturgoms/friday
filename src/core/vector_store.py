"""
Friday 3.0 Vector Store

ChromaDB-based vector store for RAG.

Usage:
    from src.core.vector_store import get_vector_store, VectorStore
    
    store = get_vector_store()
    store.add_documents(["Hello", "World"], [{"source": "test"}])
    results = store.search("Hi there", top_k=5)
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import get_config
from .embeddings import EmbeddingsModel, get_embeddings

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB vector store for document storage and retrieval."""
    
    def __init__(
        self,
        collection_name: str = "friday_docs",
        persist_path: Optional[Path] = None,
        embeddings: Optional[EmbeddingsModel] = None
    ):
        """Initialize the vector store.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_path: Path to persist the database
            embeddings: Embeddings model to use
        """
        self.collection_name = collection_name
        self.persist_path = persist_path
        self.embeddings = embeddings or get_embeddings()
        
        self._client = None
        self._collection = None
    
    def _init_client(self):
        """Initialize ChromaDB client."""
        if self._client is not None:
            return
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            if self.persist_path:
                self.persist_path.mkdir(parents=True, exist_ok=True)
                
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_path),
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                self._client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(
                f"Vector store initialized: {self.collection_name} "
                f"({self._collection.count()} documents)"
            )
            
        except ImportError:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb"
            )
    
    def _generate_id(self, text: str) -> str:
        """Generate a deterministic ID for a document."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to the vector store.
        
        Args:
            texts: List of document texts
            metadatas: Optional list of metadata dicts
            ids: Optional list of document IDs
            
        Returns:
            List of document IDs
        """
        self._init_client()
        
        if not texts:
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [self._generate_id(text) for text in texts]
        
        # Generate embeddings
        embeddings = self.embeddings.encode(texts).tolist()
        
        # Prepare metadatas
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        # Add to collection
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.debug(f"Added {len(texts)} documents to vector store")
        
        return ids
    
    def add_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """Add a single document.
        
        Args:
            text: Document text
            metadata: Optional metadata
            doc_id: Optional document ID
            
        Returns:
            Document ID
        """
        ids = self.add_documents(
            [text],
            [metadata] if metadata else None,
            [doc_id] if doc_id else None
        )
        return ids[0]
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            where: Optional metadata filter
            where_document: Optional document content filter
            
        Returns:
            List of result dicts with 'id', 'text', 'metadata', 'score'
        """
        self._init_client()
        
        # Generate query embedding
        query_embedding = self.embeddings.encode_query(query).tolist()
        
        # Search
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted = []
        
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0
                })
        
        return formatted
    
    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get documents by ID or filter.
        
        Args:
            ids: Optional list of document IDs
            where: Optional metadata filter
            limit: Maximum number of results
            
        Returns:
            List of document dicts
        """
        self._init_client()
        
        results = self._collection.get(
            ids=ids,
            where=where,
            limit=limit,
            include=["documents", "metadatas"]
        )
        
        formatted = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                formatted.append({
                    "id": doc_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
        
        return formatted
    
    def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None
    ):
        """Delete documents.
        
        Args:
            ids: Optional list of document IDs to delete
            where: Optional metadata filter
        """
        self._init_client()
        
        self._collection.delete(ids=ids, where=where)
        logger.debug(f"Deleted documents from vector store")
    
    def count(self) -> int:
        """Get the number of documents in the store."""
        self._init_client()
        return self._collection.count()
    
    def clear(self):
        """Clear all documents from the store."""
        self._init_client()
        
        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info("Vector store cleared")


# =============================================================================
# Brain/Obsidian Indexer
# =============================================================================

class BrainIndexer:
    """Index Obsidian vault (brain folder) into vector store."""
    
    def __init__(
        self,
        brain_path: Path,
        vector_store: Optional[VectorStore] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """Initialize the brain indexer.
        
        Args:
            brain_path: Path to the Obsidian vault
            vector_store: Vector store to use
            chunk_size: Chunk size for splitting documents
            chunk_overlap: Overlap between chunks
        """
        self.brain_path = Path(brain_path)
        self.vector_store = vector_store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def _get_vector_store(self) -> VectorStore:
        """Get or create vector store."""
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        return self.vector_store
    
    def index_file(self, file_path: Path) -> int:
        """Index a single markdown file.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            Number of chunks indexed
        """
        from .embeddings import chunk_markdown
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0
        
        # Read file
        content = file_path.read_text(encoding="utf-8")
        
        # Get relative path for metadata
        try:
            rel_path = file_path.relative_to(self.brain_path)
        except ValueError:
            rel_path = file_path.name
        
        # Chunk the content
        chunks = chunk_markdown(content, self.chunk_size, self.chunk_overlap)
        
        if not chunks:
            return 0
        
        # Prepare for indexing
        texts = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{rel_path}:{i}"
            
            texts.append(chunk["text"])
            metadatas.append({
                "source": str(rel_path),
                "chunk_index": i,
                **chunk.get("metadata", {})
            })
            ids.append(hashlib.md5(chunk_id.encode()).hexdigest())
        
        # Add to vector store
        store = self._get_vector_store()
        store.add_documents(texts, metadatas, ids)
        
        return len(chunks)
    
    def index_all(
        self,
        extensions: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> Dict[str, int]:
        """Index all files in the brain folder.
        
        Args:
            extensions: File extensions to index (default: ['.md'])
            exclude_patterns: Patterns to exclude
            
        Returns:
            Dict with indexing statistics
        """
        if extensions is None:
            extensions = [".md"]
        
        if exclude_patterns is None:
            exclude_patterns = [".obsidian", ".trash", ".git"]
        
        stats = {
            "files_indexed": 0,
            "chunks_created": 0,
            "files_skipped": 0
        }
        
        for ext in extensions:
            for file_path in self.brain_path.rglob(f"*{ext}"):
                # Check exclusions
                skip = False
                for pattern in exclude_patterns:
                    if pattern in str(file_path):
                        skip = True
                        break
                
                if skip:
                    stats["files_skipped"] += 1
                    continue
                
                try:
                    chunks = self.index_file(file_path)
                    if chunks > 0:
                        stats["files_indexed"] += 1
                        stats["chunks_created"] += chunks
                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    stats["files_skipped"] += 1
        
        logger.info(
            f"Brain indexing complete: {stats['files_indexed']} files, "
            f"{stats['chunks_created']} chunks"
        )
        
        return stats


# =============================================================================
# Global Instance
# =============================================================================

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance.
    
    Returns:
        VectorStore instance
    """
    global _vector_store
    
    if _vector_store is None:
        config = get_config()
        _vector_store = VectorStore(
            collection_name="friday_brain",
            persist_path=Path(config.memory.chroma_path)
        )
    
    return _vector_store
