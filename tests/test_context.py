"""
Tests for Friday 3.0 Context and RAG System

Tests the context builder, vector store, and embeddings.
"""

import pytest
from pathlib import Path
import tempfile
import shutil


class TestContextBuilder:
    """Tests for the context builder."""
    
    def test_context_builder_initialization(self):
        """Test context builder can be initialized."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        
        assert builder is not None
        assert builder.top_k == 5  # Default
    
    def test_build_with_time(self):
        """Test context includes current time."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        context = builder.build(
            user_id="test",
            query="test query",
            include_profile=False,
            include_rag=False,
            include_time=True
        )
        
        assert "Current time:" in context
        assert "Day of week:" in context
    
    def test_build_without_time(self):
        """Test context can exclude time."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        context = builder.build(
            user_id="test",
            query="test query",
            include_profile=False,
            include_rag=False,
            include_time=False
        )
        
        assert "Current time:" not in context
    
    def test_format_user_profile(self):
        """Test user profile formatting."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        profile = "Name: Test User\nBirthday: 2000-01-01"
        
        formatted = builder.format_user_profile(profile)
        
        assert "## User Profile" in formatted
        assert "Name: Test User" in formatted
    
    def test_format_user_profile_truncation(self):
        """Test long profiles are truncated."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        profile = "x" * 3000  # Very long profile
        
        formatted = builder.format_user_profile(profile)
        
        assert len(formatted) < 3000
        assert "[truncated]" in formatted
    
    def test_format_rag_context(self):
        """Test RAG context formatting."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        results = [
            {"text": "Test content 1", "metadata": {"source": "test1.md"}, "score": 0.8},
            {"text": "Test content 2", "metadata": {"source": "test2.md"}, "score": 0.6},
        ]
        
        formatted = builder.format_rag_context(results)
        
        assert "## Relevant Knowledge" in formatted
        assert "test1.md" in formatted
        assert "Test content 1" in formatted
    
    def test_format_rag_context_filters_low_scores(self):
        """Test low-scoring results are filtered."""
        from src.core.context import ContextBuilder
        
        builder = ContextBuilder()
        results = [
            {"text": "High score", "metadata": {"source": "high.md"}, "score": 0.8},
            {"text": "Low score", "metadata": {"source": "low.md"}, "score": 0.1},
        ]
        
        formatted = builder.format_rag_context(results)
        
        assert "high.md" in formatted
        assert "low.md" not in formatted


class TestVectorStore:
    """Tests for the vector store."""
    
    @pytest.fixture
    def temp_store(self):
        """Create a temporary vector store."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_vector_store_initialization(self, temp_store):
        """Test vector store can be initialized."""
        from src.core.vector_store import VectorStore
        
        store = VectorStore(
            collection_name="test",
            persist_path=temp_store
        )
        
        assert store is not None
        assert store.count() == 0
    
    def test_add_and_search_documents(self, temp_store):
        """Test adding and searching documents."""
        from src.core.vector_store import VectorStore
        
        store = VectorStore(
            collection_name="test",
            persist_path=temp_store
        )
        
        # Add documents
        store.add_documents(
            texts=["Python is a programming language", "The sky is blue"],
            metadatas=[{"source": "doc1"}, {"source": "doc2"}]
        )
        
        assert store.count() == 2
        
        # Search
        results = store.search("programming", top_k=1)
        
        assert len(results) == 1
        assert "Python" in results[0]["text"]
    
    def test_delete_documents(self, temp_store):
        """Test deleting documents."""
        from src.core.vector_store import VectorStore
        
        store = VectorStore(
            collection_name="test",
            persist_path=temp_store
        )
        
        # Add documents
        ids = store.add_documents(
            texts=["Document to delete"],
            metadatas=[{"source": "temp"}]
        )
        
        assert store.count() == 1
        
        # Delete
        store.delete(ids=ids)
        
        assert store.count() == 0
    
    def test_clear_store(self, temp_store):
        """Test clearing all documents."""
        from src.core.vector_store import VectorStore
        
        store = VectorStore(
            collection_name="test",
            persist_path=temp_store
        )
        
        # Add documents
        store.add_documents(
            texts=["Doc 1", "Doc 2", "Doc 3"],
            metadatas=[{"source": "a"}, {"source": "b"}, {"source": "c"}]
        )
        
        assert store.count() == 3
        
        # Clear
        store.clear()
        
        assert store.count() == 0


class TestEmbeddings:
    """Tests for the embeddings model."""
    
    def test_embeddings_initialization(self):
        """Test embeddings model can be initialized."""
        from src.core.embeddings import EmbeddingsModel
        
        model = EmbeddingsModel()
        
        assert model is not None
    
    def test_encode_single_text(self):
        """Test encoding a single text."""
        from src.core.embeddings import EmbeddingsModel
        
        model = EmbeddingsModel()
        embedding = model.encode_query("Hello world")
        
        assert embedding is not None
        assert len(embedding) > 0
    
    def test_encode_multiple_texts(self):
        """Test encoding multiple texts."""
        from src.core.embeddings import EmbeddingsModel
        
        model = EmbeddingsModel()
        embeddings = model.encode(["Hello", "World"])
        
        assert embeddings is not None
        assert len(embeddings) == 2
    
    def test_chunk_text(self):
        """Test text chunking utility."""
        from src.core.embeddings import chunk_text
        
        text = "This is a test. " * 100  # Long text
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        
        assert len(chunks) > 1
        # Check overlap by verifying content continuity
        for chunk in chunks:
            assert len(chunk) <= 150  # Allow some flexibility
