"""
Knowledge Indexer - Populate Vector Store for RAG

Indexes content into vector store for semantic search:
- Vault notes: Chunked by ## headers (800 tokens, 100 overlap)
- Person notes: Each frontmatter field + content as separate chunks
- Conversation history: User messages from last 90 days

Tools:
    - index_vault_notes(): Index all vault notes
    - index_person_notes(): Index all person profile notes
    - index_conversation_history(): Index recent conversations
    - rebuild_knowledge_index(): Rebuild entire index
    - get_index_stats(): Get indexing statistics
"""

import sys
from pathlib import Path

# Add parent directory to path
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

import yaml

from src.core.agent import agent
from src.core.database import Database
from src.core.vector_store import get_vector_store, Document

logger = logging.getLogger(__name__)


@agent.tool_plain
def index_vault_notes(force: bool = False) -> Dict[str, Any]:
    """
    Index vault notes into vector store for semantic search.
    
    Chunks notes by ## headers with overlap. Skips:
    - Dataview code blocks
    - Person notes (indexed separately)
    - Template files
    
    Args:
        force: If True, re-index even if already indexed (default: False)
        
    Returns:
        Dict with:
            - indexed_count: Number of chunks indexed
            - skipped_count: Number of files skipped
            - error: Error message if failed
    """
    try:
        vector_store = get_vector_store()
        vault_path = settings.PATHS["brain"]
        
        if not vault_path.exists():
            return {"error": f"Vault path not found: {vault_path}"}
        
        # Configuration
        chunk_size = settings.KNOWLEDGE["sources"]["vault"]["chunk_size"]
        chunk_overlap = settings.KNOWLEDGE["sources"]["vault"]["chunk_overlap"]
        
        indexed_count = 0
        skipped_count = 0
        
        # Find all markdown files
        for note_path in vault_path.rglob("*.md"):
            # Skip person notes (indexed separately)
            if note_path.parent.name == "1. Notes":
                # Person notes have format: "First Last.md"
                if _is_person_note(note_path.stem):
                    skipped_count += 1
                    continue
            
            # Skip templates
            if "template" in note_path.name.lower():
                skipped_count += 1
                continue
            
            try:
                # Read note
                content = note_path.read_text(encoding="utf-8")
                
                # Parse frontmatter and content
                frontmatter, body = _extract_frontmatter(content)
                
                # Chunk by ## headers
                chunks = _chunk_by_headers(body, chunk_size, chunk_overlap)
                
                if not chunks:
                    skipped_count += 1
                    continue
                
                # Prepare documents for indexing
                documents = []
                
                for i, chunk in enumerate(chunks):
                    doc_id = f"vault_{note_path.stem}_{i}".replace(" ", "_")
                    
                    doc = Document(
                        content=chunk,
                        metadata={
                            "source": f"Vault: {note_path.relative_to(vault_path)}",
                            "file_path": str(note_path),
                            "chunk_index": i,
                            "type": "vault_note"
                        },
                        doc_id=doc_id
                    )
                    documents.append(doc)
                
                # Add to vector store
                vector_store.add_documents(documents=documents)
                
                indexed_count += len(chunks)
                logger.debug(f"Indexed {len(chunks)} chunks from {note_path.name}")
                
            except Exception as e:
                logger.warning(f"Failed to index {note_path.name}: {e}")
                skipped_count += 1
                continue
        
        return {
            "indexed_count": indexed_count,
            "skipped_count": skipped_count,
            "message": f"Indexed {indexed_count} chunks from vault notes"
        }
        
    except Exception as e:
        logger.error(f"Failed to index vault notes: {e}", exc_info=True)
        return {"error": str(e)}


@agent.tool_plain
def index_person_notes(force: bool = False) -> Dict[str, Any]:
    """
    Index person profile notes into vector store.
    
    Each frontmatter field and content section becomes a separate chunk
    for fine-grained retrieval of person information.
    
    Args:
        force: If True, re-index even if already indexed (default: False)
        
    Returns:
        Dict with:
            - indexed_count: Number of chunks indexed
            - persons_count: Number of person notes processed
            - error: Error message if failed
    """
    try:
        vector_store = get_vector_store()
        notes_dir = settings.PATHS["brain"] / "1. Notes"
        
        if not notes_dir.exists():
            return {"error": f"Notes directory not found: {notes_dir}"}
        
        indexed_count = 0
        persons_count = 0
        
        # Find all person notes
        for note_path in notes_dir.glob("*.md"):
            # Check if it's a person note (First Last.md pattern)
            if not _is_person_note(note_path.stem):
                continue
            
            # Skip Artur Gomes (that's the user profile, not a person note)
            if note_path.stem == "Artur Gomes":
                continue
            
            try:
                # Read note
                content = note_path.read_text(encoding="utf-8")
                
                # Parse frontmatter and content
                frontmatter, body = _extract_frontmatter(content)
                
                documents = []
                metadatas = []
                ids = []
                
                person_name = note_path.stem
                
                # Index each frontmatter field separately
                if frontmatter:
                    for field, value in frontmatter.items():
                        if value and field not in ["tags", "created", "modified"]:
                            doc_id = f"person_{person_name}_{field}".replace(" ", "_")
                            
                            # Format as readable text
                            if isinstance(value, list):
                                text = f"{person_name} - {field}: {', '.join(str(v) for v in value)}"
                            elif isinstance(value, dict):
                                text = f"{person_name} - {field}: {', '.join(f'{k}: {v}' for k, v in value.items())}"
                            else:
                                text = f"{person_name} - {field}: {value}"
                            
                            doc = Document(
                                content=text,
                                metadata={
                                    "source": f"Person: {person_name}",
                                    "file_path": str(note_path),
                                    "field": field,
                                    "type": "person_field"
                                },
                                doc_id=doc_id
                            )
                            documents.append(doc)
                
                # Index content if present
                if body.strip():
                    doc_id = f"person_{person_name}_content".replace(" ", "_")
                    
                    doc = Document(
                        content=f"{person_name} - Notes: {body.strip()}",
                        metadata={
                            "source": f"Person: {person_name}",
                            "file_path": str(note_path),
                            "field": "content",
                            "type": "person_content"
                        },
                        doc_id=doc_id
                    )
                    documents.append(doc)
                
                # Add to vector store
                if documents:
                    vector_store.add_documents(documents=documents)
                    
                    indexed_count += len(documents)
                    persons_count += 1
                    logger.debug(f"Indexed {len(documents)} chunks from {person_name}")
                
            except Exception as e:
                logger.warning(f"Failed to index {note_path.name}: {e}")
                continue
        
        return {
            "indexed_count": indexed_count,
            "persons_count": persons_count,
            "message": f"Indexed {indexed_count} chunks from {persons_count} person notes"
        }
        
    except Exception as e:
        logger.error(f"Failed to index person notes: {e}", exc_info=True)
        return {"error": str(e)}


@agent.tool_plain
def index_conversation_history(days: int = 90) -> Dict[str, Any]:
    """
    Index conversation history into vector store.
    
    Only indexes user messages (not assistant responses) from the
    specified time period. This allows RAG to find similar past queries.
    
    Args:
        days: Number of days to look back (default: 90)
        
    Returns:
        Dict with:
            - indexed_count: Number of messages indexed
            - error: Error message if failed
    """
    try:
        vector_store = get_vector_store()
        db = Database()
        
        # Calculate cutoff date
        cutoff = datetime.now(settings.TIMEZONE) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        # Configuration
        user_only = settings.KNOWLEDGE["sources"]["conversation_history"]["index_user_only"]
        
        # Query conversation history
        if user_only:
            query = """
                SELECT timestamp, role, content 
                FROM conversation_history 
                WHERE timestamp >= :cutoff AND role = 'user'
                ORDER BY timestamp ASC
            """
        else:
            query = """
                SELECT timestamp, role, content 
                FROM conversation_history 
                WHERE timestamp >= :cutoff
                ORDER BY timestamp ASC
            """
        
        results = db.fetchall(query, {"cutoff": cutoff_str})
        
        if not results:
            return {"indexed_count": 0, "message": "No conversation history found"}
        
        documents = []
        metadatas = []
        ids = []
        
        for row in results:
            row_dict = row._mapping
            timestamp = row_dict["timestamp"]
            role = row_dict["role"]
            content = row_dict["content"]
            
            # Skip empty messages
            if not content.strip():
                continue
            
            # Create document ID
            doc_id = f"conv_{timestamp.replace(':', '_').replace('.', '_')}"
            
            # Format for indexing
            doc = Document(
                content=content,
                metadata={
                    "source": f"Conversation: {timestamp[:10]}",
                    "timestamp": timestamp,
                    "role": role,
                    "type": "conversation"
                },
                doc_id=doc_id
            )
            documents.append(doc)
        
        # Add to vector store
        if documents:
            vector_store.add_documents(documents=documents)
        
        return {
            "indexed_count": len(documents),
            "message": f"Indexed {len(documents)} conversation messages from last {days} days"
        }
        
    except Exception as e:
        logger.error(f"Failed to index conversation history: {e}", exc_info=True)
        return {"error": str(e)}


@agent.tool_plain
def rebuild_knowledge_index() -> Dict[str, Any]:
    """
    Rebuild entire knowledge index from scratch.
    
    Clears vector store and re-indexes:
    - Vault notes
    - Person notes
    - Conversation history
    
    Returns:
        Dict with:
            - vault_indexed: Number of vault chunks indexed
            - persons_indexed: Number of person chunks indexed
            - conversations_indexed: Number of conversation messages indexed
            - total_indexed: Total chunks indexed
            - error: Error message if failed
    """
    try:
        vector_store = get_vector_store()
        
        # Clear existing index
        logger.info("Clearing existing knowledge index...")
        vector_store.clear_all()
        
        # Index vault notes
        logger.info("Indexing vault notes...")
        vault_result = index_vault_notes(force=True)
        
        if "error" in vault_result:
            return {"error": f"Vault indexing failed: {vault_result['error']}"}
        
        # Index person notes
        logger.info("Indexing person notes...")
        person_result = index_person_notes(force=True)
        
        if "error" in person_result:
            return {"error": f"Person indexing failed: {person_result['error']}"}
        
        # Index conversation history
        logger.info("Indexing conversation history...")
        conv_result = index_conversation_history()
        
        if "error" in conv_result:
            return {"error": f"Conversation indexing failed: {conv_result['error']}"}
        
        # Calculate totals
        vault_indexed = vault_result.get("indexed_count", 0)
        persons_indexed = person_result.get("indexed_count", 0)
        conversations_indexed = conv_result.get("indexed_count", 0)
        total_indexed = vault_indexed + persons_indexed + conversations_indexed
        
        return {
            "vault_indexed": vault_indexed,
            "persons_indexed": persons_indexed,
            "conversations_indexed": conversations_indexed,
            "total_indexed": total_indexed,
            "message": f"Rebuilt knowledge index: {total_indexed} total chunks indexed"
        }
        
    except Exception as e:
        logger.error(f"Failed to rebuild knowledge index: {e}", exc_info=True)
        return {"error": str(e)}


@agent.tool_plain
def get_index_stats() -> Dict[str, Any]:
    """
    Get statistics about the knowledge index.
    
    Returns:
        Dict with collection stats:
            - vault_notes: Number of vault chunks
            - person_notes: Number of person chunks
            - conversation_history: Number of conversation messages
            - total: Total chunks indexed
            - error: Error message if failed
    """
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()
        
        # Extract counts by type
        by_type = stats.get("by_type", {})
        total = stats.get("total_docs", 0)
        
        return {
            "vault_notes": by_type.get("vault_note", 0),
            "person_notes": by_type.get("person_field", 0) + by_type.get("person_content", 0),
            "conversation_history": by_type.get("conversation", 0),
            "total": total,
            "message": f"Knowledge index contains {total} total chunks"
        }
        
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}", exc_info=True)
        return {"error": str(e)}


# Helper functions

def _is_person_note(filename: str) -> bool:
    """
    Check if filename matches person note pattern (First Last).
    
    Args:
        filename: Note filename (without .md extension)
        
    Returns:
        True if it's a person note pattern
    """
    # Simple heuristic: contains space and has 2+ parts
    parts = filename.split()
    return len(parts) >= 2 and not any(char.isdigit() for char in filename)


def _extract_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter from markdown content.
    
    Args:
        content: Raw markdown content
        
    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    frontmatter = {}
    body = content
    
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2]
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
    
    return frontmatter, body


def _chunk_by_headers(
    content: str,
    chunk_size_tokens: int,
    overlap_tokens: int
) -> List[str]:
    """
    Chunk markdown content by ## headers with overlap.
    
    Skips:
    - Dataview code blocks
    - Empty sections
    
    Args:
        content: Markdown content (after frontmatter)
        chunk_size_tokens: Target chunk size in tokens (~4 chars per token)
        overlap_tokens: Overlap between chunks in tokens
        
    Returns:
        List of content chunks
    """
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    # Convert token limits to character limits (rough: 4 chars per token)
    chunk_size_chars = chunk_size_tokens * 4
    overlap_chars = overlap_tokens * 4
    
    in_dataview = False
    
    for line in content.split("\n"):
        # Skip dataview blocks
        if line.strip().startswith("```dataview"):
            in_dataview = True
            continue
        if in_dataview and line.strip() == "```":
            in_dataview = False
            continue
        if in_dataview:
            continue
        
        # Check if line is a ## header
        is_header = line.startswith("## ")
        
        # Estimate tokens for this line
        line_chars = len(line)
        
        # If adding this line would exceed chunk size and we have content
        if current_tokens + line_chars > chunk_size_chars and current_chunk:
            # Save current chunk
            chunk_text = "\n".join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
            
            # Start new chunk with overlap
            # Keep last N characters for overlap
            overlap_text = "\n".join(current_chunk)[-overlap_chars:]
            current_chunk = [overlap_text] if overlap_text else []
            current_tokens = len(overlap_text)
        
        # Add line to current chunk
        current_chunk.append(line)
        current_tokens += line_chars
    
    # Add final chunk
    if current_chunk:
        chunk_text = "\n".join(current_chunk).strip()
        if chunk_text:
            chunks.append(chunk_text)
    
    return chunks
