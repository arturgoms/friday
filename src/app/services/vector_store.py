"""Vector store service."""
import uuid
from typing import List, Optional, Tuple
import chromadb
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import RetrievedChunk, MemoryItem
from app.services.embeddings import embedding_service


class VectorStore:
    """Service for vector storage and retrieval."""
    
    _initialized = False
    
    def __init__(self):
        """Initialize ChromaDB collections."""
        # Prevent duplicate initialization logging
        if VectorStore._initialized:
            return
            
        try:
            self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
            logger.info("ChromaDB client initialized")
            
            self.obsidian_collection = self.client.get_or_create_collection(
                name="obsidian_docs",
                metadata={"hnsw:space": "cosine"},
            )
            
            self.memory_collection = self.client.get_or_create_collection(
                name="friday_memory",
                metadata={"hnsw:space": "cosine"},
            )
            
            logger.info("Vector store collections ready")
            VectorStore._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: List[dict],
        embeddings: List[List[float]],
    ):
        """Add documents to Obsidian collection."""
        ids = [str(uuid.uuid4()) for _ in documents]
        self.obsidian_collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
    
    def add_memory(
        self,
        text: str,
        label: Optional[str] = None,
    ):
        """Add memory entry."""
        try:
            embeddings = embedding_service.embed_texts([text])
            self.memory_collection.add(
                ids=[str(uuid.uuid4())],
                documents=[text],
                metadatas=[{"label": label}],
                embeddings=embeddings,
            )
            logger.info(f"Added memory entry with label: {label}")
        except Exception as e:
            logger.error(f"Failed to add memory entry: {e}")
            raise
    
    def query_obsidian(
        self,
        query: str,
        k: int = None,
    ) -> Tuple[str, List[RetrievedChunk]]:
        """Query Obsidian collection with neighbor expansion."""
        k = k or settings.top_k_obsidian
        
        if self.obsidian_collection.count() == 0:
            return "", []
        
        q_embed = embedding_service.embed_query(query)
        results = self.obsidian_collection.query(
            query_embeddings=[q_embed],
            n_results=k,
            include=["documents", "metadatas"],
        )
        
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
        
        if not docs:
            return "", []
        
        chunks_by_key: dict = {}
        
        for text, meta in zip(docs, metas):
            path = meta.get("path")
            idx = meta.get("chunk_idx")
            key = (path or "", idx or 0)
            
            if key not in chunks_by_key:
                chunks_by_key[key] = RetrievedChunk(
                    text=text,
                    path=path,
                    chunk_idx=idx,
                )
            
            if path is not None and idx is not None:
                for offset in range(-settings.neighbor_range, settings.neighbor_range + 1):
                    n_idx = idx + offset
                    n_key = (path, n_idx)
                    if n_key in chunks_by_key:
                        continue
                    neighbor = self._get_chunk_by_path_and_index(path, n_idx)
                    if neighbor is not None:
                        chunks_by_key[n_key] = neighbor
        
        sorted_keys = sorted(chunks_by_key.keys(), key=lambda x: (x[0], x[1]))
        retrieved_chunks = [chunks_by_key[k] for k in sorted_keys]
        
        parts = []
        for c in retrieved_chunks:
            header = f"[{c.path} | chunk {c.chunk_idx}]"
            parts.append(f"{header}\n{c.text}")
        
        ctx_str = "\n\n--- NOTE ---\n\n".join(parts)
        return ctx_str, retrieved_chunks
    
    def _get_chunk_by_path_and_index(
        self,
        path: str,
        chunk_idx: int,
    ) -> Optional[RetrievedChunk]:
        """Fetch a single chunk by path and index."""
        if chunk_idx < 0:
            return None
        
        res = self.obsidian_collection.get(
            where={
                "$and": [
                    {"path": path},
                    {"chunk_idx": chunk_idx},
                ]
            },
            include=["documents", "metadatas"],
        )
        
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        
        if not docs:
            return None
        
        text = docs[0]
        meta = metas[0] if metas else {}
        
        return RetrievedChunk(
            text=text,
            path=meta.get("path"),
            chunk_idx=meta.get("chunk_idx"),
        )
    
    def query_memory(
        self,
        query: str,
        k: int = None,
    ) -> Tuple[str, List[MemoryItem]]:
        """Query memory collection."""
        k = k or settings.top_k_memory
        
        if self.memory_collection.count() == 0:
            return "", []
        
        q_embed = embedding_service.embed_query(query)
        results = self.memory_collection.query(
            query_embeddings=[q_embed],
            n_results=k,
            include=["documents", "metadatas"],
        )
        
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
        
        if not docs:
            return "", []
        
        items = []
        for text, meta in zip(docs, metas):
            items.append(
                MemoryItem(
                    text=text,
                    label=meta.get("label") if meta else None,
                )
            )
        
        ctx_str = "\n\n--- MEMORY ---\n\n".join(docs)
        return ctx_str, items
    
    def rebuild_index(self) -> int:
        """Rebuild Obsidian index from scratch."""
        from app.services.obsidian import obsidian_service
        
        try:
            self.client.delete_collection(name="obsidian_docs")
        except Exception:
            pass
        
        self.obsidian_collection = self.client.get_or_create_collection(
            name="obsidian_docs",
            metadata={"hnsw:space": "cosine"},
        )
        
        docs = obsidian_service.load_all_documents()
        total_chunks = 0
        
        for doc in docs:
            chunks = obsidian_service.chunk_text(doc["text"])
            if not chunks:
                continue
            
            embeddings = embedding_service.embed_texts(chunks)
            metadatas = [
                {"path": doc["path"], "chunk_idx": i}
                for i in range(len(chunks))
            ]
            
            self.add_documents(chunks, metadatas, embeddings)
            total_chunks += len(chunks)
        
        logger.info(f"Rebuilt index with {total_chunks} chunks")
        return total_chunks
    
    def remove_file(self, filepath: str):
        """Remove all chunks from a specific file."""
        try:
            # Get all chunks for this file
            results = self.obsidian_collection.get(
                where={"path": filepath},
                include=["metadatas"]
            )
            
            ids = results.get("ids", [])
            if ids:
                self.obsidian_collection.delete(ids=ids)
                logger.info(f"Removed {len(ids)} chunks for {filepath}")
        except Exception as e:
            logger.error(f"Failed to remove file from index: {e}")
            raise
    
    def update_file(self, filepath: str, chunks: List[str], embeddings: List[List[float]]):
        """Update chunks for a specific file (remove old, add new)."""
        # Remove old chunks
        self.remove_file(filepath)
        
        # Add new chunks
        if chunks:
            metadatas = [{"path": filepath, "chunk_idx": i} for i in range(len(chunks))]
            self.add_documents(chunks, metadatas, embeddings)
            logger.info(f"Updated {filepath}: {len(chunks)} chunks")
    
    def get_stats(self) -> dict:
        """Get vector store statistics."""
        return {
            "obsidian_chunks": self.obsidian_collection.count(),
            "memory_entries": self.memory_collection.count(),
        }
    
    def list_memories(self, limit: int = 100, label: str = "explicit_memory") -> List[dict]:
        """List memories with their IDs, filtered by label."""
        try:
            # Query with filter for explicit memories only
            results = self.memory_collection.get(
                where={"label": label} if label else None,
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            memories = []
            ids = results.get("ids", [])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            
            for memory_id, doc, meta in zip(ids, docs, metas):
                memories.append({
                    "id": memory_id,
                    "content": doc[:200] + "..." if len(doc) > 200 else doc,
                    "full_content": doc,
                    "label": meta.get("label") if meta else None,
                })
            
            return memories
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            raise
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID."""
        try:
            self.memory_collection.delete(ids=[memory_id])
            logger.info(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            raise
    
    def clear_explicit_memories(self) -> int:
        """Clear only explicit memories (label='explicit_memory')."""
        try:
            # Get all explicit memory IDs
            results = self.memory_collection.get(
                where={"label": "explicit_memory"},
                include=["metadatas"]
            )
            
            ids = results.get("ids", [])
            if ids:
                self.memory_collection.delete(ids=ids)
                logger.info(f"Cleared {len(ids)} explicit memories")
                return len(ids)
            return 0
        except Exception as e:
            logger.error(f"Failed to clear explicit memories: {e}")
            raise
    
    def clear_all_memories(self) -> int:
        """Clear all memories from the collection (nuclear option)."""
        try:
            count = self.memory_collection.count()
            self.client.delete_collection(name="memory")
            self.memory_collection = self.client.get_or_create_collection(
                name="memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Cleared {count} memories")
            return count
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            raise


# Singleton instance
vector_store = VectorStore()
