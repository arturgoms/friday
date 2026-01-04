"""
Personal Knowledge Graph Tools - Vault Integration

Provides tools for storing and retrieving personal facts using Obsidian vault
as the single source of truth.

Hybrid Storage Strategy:
- Simple user attributes → Artur Gomes.md frontmatter (favorite_color, favorite_team, etc.)
- Facts about other people → Their person notes frontmatter (birthdays, contact info)
- Complex observations → Friday.md sections (behavioral patterns, preferences)

Facts DB serves as an index/cache with embeddings for semantic search, but the
vault is always the authoritative source.

Architecture:
1. save_fact() routes to appropriate vault location
2. get_fact() reads from vault (fresh data)
3. Facts DB indexes vault references for fast semantic search
4. Vector search enables finding facts by meaning, not just keywords
"""

import logging
import os
import sqlite3
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pathlib import Path

from src.core.constants import BRT
from src.core.embeddings import get_embeddings
from src.core.vault import (
    is_user_attribute,
    is_person_fact,
    extract_person_name,
    update_frontmatter_field,
    get_frontmatter_field,
    update_section_item,
    find_person_note,
    create_person_note,
    USER_NOTE,
    FRIDAY_NOTE,
)

logger = logging.getLogger(__name__)


def _get_facts_db_path() -> str:
    """Get the path to the facts database."""
    return os.path.expanduser("~/friday_facts.db")


def _init_facts_db():
    """Initialize the facts database as vault index/cache."""
    db_path = _get_facts_db_path()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create facts table (now stores vault references)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            value TEXT NOT NULL,
            category TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'user_told',
            notes TEXT,
            vault_path TEXT,
            vault_field TEXT,
            vault_section TEXT,
            last_synced TIMESTAMP
        )
    """)
    
    # Create index on topic for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_topic ON facts(topic)
    """)
    
    # Create index on category
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)
    """)
    
    # Add embedding column if it doesn't exist (migration)
    cursor.execute("PRAGMA table_info(facts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'embedding' not in columns:
        logger.info("[STORE] Adding embedding column to facts table...")
        cursor.execute("""
            ALTER TABLE facts ADD COLUMN embedding BLOB
        """)
        logger.info("[STORE] Embedding column added successfully")
    
    # Add vault reference columns if they don't exist
    for col_name in ['vault_path', 'vault_field', 'vault_section', 'last_synced']:
        if col_name not in columns:
            logger.info(f"[STORE] Adding {col_name} column to facts table...")
            cursor.execute(f"""
                ALTER TABLE facts ADD COLUMN {col_name} TEXT
            """)
    
    conn.commit()
    conn.close()


def _generate_fact_embedding(topic: str, value: str) -> Optional[np.ndarray]:
    """Generate embedding for a fact.
    
    Args:
        topic: Fact topic
        value: Fact value
        
    Returns:
        Embedding vector as numpy array
    """
    try:
        # Combine topic and value for richer semantic representation
        text = f"{topic}: {value}"
        
        embeddings_model = get_embeddings()
        embedding = embeddings_model.encode(text, normalize=True)
        
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding for fact '{topic}': {e}")
        return None


def _embedding_to_blob(embedding: np.ndarray) -> bytes:
    """Convert numpy embedding to blob for storage."""
    if embedding is None:
        return None
    return embedding.tobytes()


def _blob_to_embedding(blob: bytes) -> np.ndarray:
    """Convert blob back to numpy embedding."""
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(similarity)  # Convert to Python float


def _vector_search_facts(query: str, limit: int = 5, min_similarity: float = 0.3) -> List[Tuple[str, str, str, float]]:
    """Search facts using vector similarity.
    
    Args:
        query: Search query
        limit: Maximum number of results
        min_similarity: Minimum similarity threshold (0-1)
        
    Returns:
        List of (topic, value, category, similarity_score) tuples
    """
    try:
        _init_facts_db()
        
        # Generate query embedding
        embeddings_model = get_embeddings()
        query_embedding = embeddings_model.encode(query, normalize=True)
        
        # Get all facts with embeddings
        conn = sqlite3.connect(_get_facts_db_path())
        cursor = conn.cursor()
        
        # Get latest version of each fact that has an embedding
        cursor.execute("""
            SELECT f1.topic, f1.value, f1.category, f1.embedding
            FROM facts f1
            INNER JOIN (
                SELECT topic, MAX(created_at) as max_date
                FROM facts
                WHERE embedding IS NOT NULL
                GROUP BY topic
            ) f2 ON f1.topic = f2.topic AND f1.created_at = f2.max_date
        """)
        
        results = []
        for row in cursor.fetchall():
            topic, value, category, embedding_blob = row
            
            if embedding_blob:
                fact_embedding = _blob_to_embedding(embedding_blob)
                similarity = _cosine_similarity(query_embedding, fact_embedding)
                
                if similarity >= min_similarity:
                    results.append((topic, value, category or 'none', similarity))
        
        conn.close()
        
        # Sort by similarity (descending) and limit
        results.sort(key=lambda x: x[3], reverse=True)
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        return []


def save_fact(
    topic: str,
    value: str,
    category: Optional[str] = None,
    confidence: float = 1.0,
    notes: Optional[str] = None
) -> str:
    """Save a new fact using vault as source of truth.
    
    Routes facts to appropriate vault locations:
    - Simple user attributes → Artur Gomes.md frontmatter
    - Facts about people → Person notes
    - Complex observations → Friday.md sections
    
    Use this when the user tells you information that should be remembered long-term.
    
    Examples:
    - User: "My favorite color is blue" → save_fact(topic="favorite_color", value="blue", category="preferences")
    - User: "My wife's name is Sarah" → save_fact(topic="wife_name", value="Sarah", category="family")
    - User: "I prefer morning workouts" → save_fact(topic="workout_preference", value="morning workouts on weekdays", category="health")
    
    DO NOT use for:
    - Temporary information (today's weather, current meeting)
    - Information already in calendar/health data
    - Conversation context (use memory tools instead)
    
    Args:
        topic: Short identifier (e.g., "favorite_color", "wife_birthday")
        value: The actual information
        category: Category (e.g., "preferences", "family", "work")
        confidence: How confident we are (0.0 to 1.0)
        notes: Additional context
        
    Returns:
        Confirmation message
    """
    try:
        _init_facts_db()
        
        vault_path = None
        vault_field = None
        vault_section = None
        success = False
        
        # Route 1: Simple user attributes → User note frontmatter
        if is_user_attribute(topic):
            vault_path = str(USER_NOTE)
            vault_field = topic
            success = update_frontmatter_field(USER_NOTE, topic, value)
            if success:
                logger.info(f"[VAULT] Updated user attribute: {topic} = {value}")
        
        # Route 2: Person-related facts
        elif is_person_fact(topic, category or ''):
            person_name = extract_person_name(topic, value)
            
            if person_name:
                # Find or create person note
                person_note = find_person_note(person_name)
                
                if not person_note:
                    # Determine relationship from category
                    relationship = 'friend'
                    if category and category.lower() in ['family', 'colleagues', 'clients']:
                        relationship = category.lower().rstrip('s')  # Remove plural 's'
                    
                    # Extract field name from topic
                    field_name = topic.replace(f"{person_name.lower().replace(' ', '_')}_", '')
                    if not field_name or field_name == topic:
                        # Try common prefixes
                        for prefix in ['wife', 'husband', 'mother', 'father', 'sister', 'brother', 'friend']:
                            if topic.startswith(prefix):
                                field_name = topic.replace(f"{prefix}_", '')
                                break
                    
                    # Create note with initial data
                    extra_fields = {}
                    if field_name and field_name != 'name':
                        extra_fields[field_name] = value
                    
                    person_note = create_person_note(person_name, relationship, **extra_fields)
                    
                    if person_note:
                        vault_path = str(person_note)
                        vault_field = field_name if field_name != 'name' else 'aliases'
                        success = True
                        logger.info(f"[VAULT] Created person note: {person_name}")
                else:
                    # Update existing person note
                    field_name = topic.split('_')[-1]  # Last part usually is the field (e.g., birthday, email)
                    vault_path = str(person_note)
                    vault_field = field_name
                    success = update_frontmatter_field(person_note, field_name, value)
                    logger.info(f"[VAULT] Updated person field: {person_name}.{field_name} = {value}")
            else:
                # Can't determine person, save as observation in Friday.md
                vault_path = str(FRIDAY_NOTE)
                vault_section = f"Learned Memories/{category.title() if category else 'Other'}"
                
                # Format the item key nicely
                item_key = topic.replace('_', ' ').title()
                success = update_section_item(
                    FRIDAY_NOTE,
                    ['Learned Memories', category.title() if category else 'Other'],
                    item_key,
                    value
                )
                logger.info(f"[VAULT] Saved as observation: {topic}")
        
        # Route 3: Complex observations → Friday.md sections
        else:
            vault_path = str(FRIDAY_NOTE)
            vault_section = f"Learned Memories/{category.title() if category else 'Other'}"
            
            item_key = topic.replace('_', ' ').title()
            success = update_section_item(
                FRIDAY_NOTE,
                ['Learned Memories', category.title() if category else 'Other'],
                item_key,
                value
            )
            logger.info(f"[VAULT] Saved observation: {topic}")
        
        if not success:
            return f"❌ Failed to save fact to vault: {topic}"
        
        # Index in Facts DB for semantic search
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Generate embedding
        embedding = _generate_fact_embedding(topic, value)
        embedding_blob = _embedding_to_blob(embedding) if embedding is not None else None
        
        # Insert index entry
        cursor.execute("""
            INSERT INTO facts (
                topic, value, category, confidence, notes, embedding,
                vault_path, vault_field, vault_section, last_synced
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            topic, value, category, confidence, notes, embedding_blob,
            vault_path, vault_field, vault_section, datetime.now(BRT).isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        location = vault_field or vault_section or 'vault'
        return f"✅ Saved to vault: {topic} = {value} (location: {location})"
        
    except Exception as e:
        logger.error(f"[TOOL] Error saving fact: {e}", exc_info=True)
        return f"❌ Error saving fact: {str(e)}"


def get_fact(topic: str) -> str:
    """Get a fact value from vault (authoritative source).
    
    Smart fallback: If the exact fact isn't found, automatically searches for related facts
    that might help answer the question. The model then uses those facts to infer the answer.
    
    Examples:
    - User asks: "What's my favorite color?" → Returns color directly
    - User asks: "How old is my wife?" → Returns wife_name + birthday facts, model calculates age
    - User asks: "When is my team playing?" → Returns team name, model searches web
    
    Args:
        topic: The fact topic to retrieve
        
    Returns:
        The fact value, or related facts the model can use to infer the answer
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get vault reference from index
        cursor.execute("""
            SELECT value, category, vault_path, vault_field, vault_section, created_at
            FROM facts
            WHERE topic = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (topic,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            # Auto-fallback: Search for related facts
            logger.info(f"[TOOL] Fact '{topic}' not found, searching for related info...")
            
            vector_results = _vector_search_facts(topic, limit=5, min_similarity=0.25)
            
            if vector_results:
                logger.info(f"[TOOL] Found {len(vector_results)} related facts")
                
                result = [f"❌ No direct fact for '{topic}', but found related information:"]
                result.append("=" * 50)
                
                for topic_found, value, cat, similarity in vector_results:
                    entry = f"📝 {topic_found}: {value}"
                    if cat:
                        entry += f" ({cat})"
                    result.append(entry)
                
                result.append("=" * 50)
                result.append("💡 Use these facts to calculate/infer the answer you need.")
                result.append("💡 For example: if you need age, look for birthday and calculate from birth year.")
                
                return "\n".join(result)
            
            return f"❌ I don't have any information about '{topic}'."
        
        # Direct fact found - return it
        cached_value, category, vault_path, vault_field, vault_section, created_at = row
        
        # Try to read from vault if we have a reference
        vault_value = None
        
        if vault_path and vault_field:
            try:
                vault_file = Path(vault_path)
                vault_value = get_frontmatter_field(vault_file, vault_field)
                if vault_value:
                    logger.info(f"[VAULT] Read {topic} from {vault_file.name}:{vault_field}")
            except Exception as e:
                logger.warning(f"[VAULT] Failed to read from vault: {e}")
        
        # Use vault value if found, otherwise cached value
        value = vault_value if vault_value is not None else cached_value
        
        result = f"📝 {topic}: {value}"
        if category:
            result += f" (category: {category})"
        
        if vault_value:
            result += f"\n📍 Source: vault ({Path(vault_path).name})"
        else:
            result += f"\n💾 Source: cached (updated: {created_at})"
        
        return result
        
    except Exception as e:
        logger.error(f"[TOOL] Error getting fact: {e}", exc_info=True)
        return f"❌ Error retrieving fact: {str(e)}"


def search_facts(
    query: str,
    category: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search for facts matching a query.
    
    Use this when you need to find facts but don't know the exact topic name,
    or when the user asks an open-ended question about what you know.
    
    Examples:
    - User: "What do you know about my preferences?" → search_facts(query="", category="preferences")
    - User: "Tell me what you know about me" → search_facts(query="")
    - Looking for color-related facts → search_facts(query="color")
    
    Args:
        query: Search term (searches in topic, value, and notes)
        category: Optional category filter
        limit: Maximum number of results (default 10)
        
    Returns:
        List of matching facts
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Build query
        if category:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE category = ?
                  AND (topic LIKE ? OR value LIKE ? OR notes LIKE ?)
                ORDER BY created_at DESC
            """
            params = (category, f"%{query}%", f"%{query}%", f"%{query}%")
        else:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE topic LIKE ? OR value LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (f"%{query}%", f"%{query}%", f"%{query}%", limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Get latest value for each topic
        unique_topics = {}
        for topic, value, cat, created_at, notes in rows:
            if topic not in unique_topics:
                unique_topics[topic] = (value, cat, created_at, notes)
        
        conn.close()
        
        # If no keyword results, try semantic search
        if not unique_topics and not category:  # Only use semantic search when no category filter
            vector_results = _vector_search_facts(query, limit=limit, min_similarity=0.20)
            if vector_results:
                result = [f"🔮 Found {len(vector_results)} semantically similar facts:"]
                result.append("=" * 50)
                for topic, value, cat, similarity in vector_results:
                    entry = f"\n📝 {topic}: {value}"
                    if cat:
                        entry += f" ({cat})"
                    entry += f"\n   Similarity: {similarity:.2f}"
                    result.append(entry)
                return "\n".join(result)
            else:
                return f"❌ No facts found matching '{query}'"
        
        if not unique_topics:
            return f"❌ No facts found matching '{query}'" + (f" in category '{category}'" if category else "")
        
        # Format results
        result = [f"📚 Found {len(unique_topics)} facts:"]
        result.append("=" * 50)
        
        for topic, (value, cat, created_at, notes) in unique_topics.items():
            entry = f"\n📝 {topic}: {value}"
            if cat:
                entry += f" ({cat})"
            if notes:
                entry += f"\n   Notes: {notes}"
            entry += f"\n   Updated: {created_at}"
            result.append(entry)
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error searching facts: {e}")
        return f"Error searching facts: {str(e)}"


def search_knowledge(query: str, limit: int = 5) -> str:
    """Search across ALL knowledge sources: facts database AND Obsidian vault.
    
    This is the "search everywhere" tool. Use this when you need to find information
    but don't know where it might be stored.
    
    Use this when:
    - User asks about information you don't immediately know
    - You need to find something but don't know if it's in notes or facts
    - User asks "Do you know anything about X?"
    
    Examples:
    - User: "What's my favorite color?" → search_knowledge(query="favorite color")
    - User: "Tell me about my running goals" → search_knowledge(query="running goals")
    - User: "What do you know about my family?" → search_knowledge(query="family")
    
    Args:
        query: What to search for
        limit: Maximum results from each source
        
    Returns:
        Combined results from facts and vault
    """
    try:
        results = []
        results.append(f"🔍 Searching all knowledge for: '{query}'")
        results.append("=" * 60)
        
        # Search facts database (keyword search)
        facts_result = search_facts(query, limit=limit)
        
        # Also do vector search for semantic matching
        vector_results = _vector_search_facts(query, limit=limit, min_similarity=0.20)
        
        # Combine and deduplicate results
        facts_found = "No facts found" not in facts_result
        vector_found = len(vector_results) > 0
        
        if facts_found or vector_found:
            results.append("\n📊 FACTS DATABASE:")
            
            if facts_found:
                results.append(facts_result)
            
            # Add semantic matches if they're not already in keyword results
            if vector_found:
                results.append("\n🔮 Related facts (semantic search):")
                for topic, value, category, similarity in vector_results[:3]:  # Top 3
                    # Simple check to avoid exact duplicates from keyword search
                    if topic not in facts_result:
                        results.append(f"  • {topic}: {value} (category: {category}, similarity: {similarity:.2f})")
        
        
        # Search vault
        try:
            from src.tools.vault import vault_search_notes
            vault_result = vault_search_notes(
                query=query,
                search_content=True,
                search_filenames=True,
                limit=limit
            )
            
            if vault_result and "No results found" not in vault_result:
                results.append("\n\n📓 OBSIDIAN VAULT:")
                results.append(vault_result)
        except Exception as vault_error:
            logger.warning(f"Vault search failed: {vault_error}")
        
        if len(results) <= 2:  # Only header, no actual results
            return f"❌ No information found about '{query}' in facts or vault.\n\n💡 If you know this information, please tell me so I can remember it!"
        
        return "\n".join(results)
        
    except Exception as e:
        logger.error(f"Error in search_knowledge: {e}")
        return f"Error searching knowledge: {str(e)}"


def find_related_info(question: str, max_results: int = 5) -> str:
    """Search for information that might help answer a question.
    
    Use this tool when you don't have direct information but might be able to INFER the answer
    from related facts. This tool searches broadly and returns anything that might be relevant.
    
    This is the "Can I figure this out?" tool - call it when:
    - Direct get_fact() returns not found
    - User asks about something derived (age, time until event, relationship info)
    - You need to piece together information from multiple facts
    
    Examples:
    - Question: "How old is my wife?" 
      → This searches for: wife name, wife birthday, wife age, birth date, etc.
      → Might find: wife_name=Camila, camila_santos_birthday=1995-12-12
      → Then YOU calculate: 2026 - 1995 = 30 years old
    
    - Question: "When is my team playing next?"
      → Searches for: team, favorite team, sports
      → Finds: favorite_soccer_team=Cruzeiro
      → Then YOU search web for match schedule
    
    - Question: "What's my sister's email?"
      → Searches for: sister, sibling, family, email
      → Finds: giulia_menezes_email=xxx
      → You infer Giulia is the sister
    
    Args:
        question: The question you're trying to answer (natural language)
        max_results: Maximum facts to return (default 5)
    
    Returns:
        Related facts that might help answer the question
    """
    try:
        _init_facts_db()
        
        logger.info(f"[TOOL] Finding related info for: '{question}'")
        
        # Use vector search for semantic matching
        vector_results = _vector_search_facts(question, limit=max_results, min_similarity=0.25)
        
        if not vector_results:
            return f"❌ Could not find any related information for: '{question}'\n\n💡 You may need to ask the user for this information."
        
        # Format results with context
        result = [f"🔍 Found {len(vector_results)} potentially relevant facts for: '{question}'"]
        result.append("=" * 60)
        result.append("\n💡 Use these facts to infer the answer:")
        
        for topic, value, category, similarity in vector_results:
            entry = f"\n📝 {topic}: {value}"
            if category:
                entry += f" (category: {category})"
            entry += f"\n   Relevance: {similarity:.2f}"
            result.append(entry)
        
        result.append("\n" + "=" * 60)
        result.append("✅ Now use this information to answer the question.")
        result.append("   Calculate/infer what you need (age, dates, relationships, etc.)")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"[TOOL] Error finding related info: {e}", exc_info=True)
        return f"❌ Error searching for related information: {str(e)}"


def list_fact_categories() -> str:
    """List all fact categories with counts.
    
    Useful for understanding what types of information we have stored.
    
    Returns:
        List of categories and how many facts in each
    """
    try:
        _init_facts_db()
        
        db_path = _get_facts_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, COUNT(DISTINCT topic) as count
            FROM facts
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "📚 No categorized facts yet."
        
        result = ["📚 Fact Categories:"]
        result.append("=" * 40)
        for category, count in rows:
            result.append(f"  {category}: {count} facts")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"Error: {str(e)}"
