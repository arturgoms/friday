"""
Context Engine - Auto-Context RAG System

Provides intelligent context injection for LLM interactions:
- Tier 1 (Background): Always-on user profile context
- Tier 2 (RAG): Conditional semantic search context
- Intent detection: Hybrid approach to determine when to use RAG

Architecture:
    - should_retrieve_context(): Decide if RAG is needed
    - get_background_context(): Load user profile (Artur Gomes.md)
    - get_rag_context(): Semantic search for relevant information
    - build_enhanced_prompt(): Combine contexts into prompt
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
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import yaml

from src.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def should_retrieve_context(message: str) -> bool:
    """
    Determine if RAG context should be retrieved for this message.
    
    Uses hybrid detection logic:
    1. Skip patterns (greetings) → False
    2. Tool keywords (real-time data) → False (prefer tools)
    3. Activate keywords (knowledge queries) → True (use RAG)
    4. Default: True if message contains "?"
    
    Args:
        message: User's input message
        
    Returns:
        True if RAG context should be retrieved, False otherwise
    """
    message_lower = message.lower().strip()
    
    # Check skip patterns (greetings, simple responses)
    skip_patterns = settings.KNOWLEDGE["detection"]["skip_patterns"]
    for pattern in skip_patterns:
        if re.search(pattern, message_lower):
            logger.debug(f"Skipping RAG - matched skip pattern: {pattern}")
            return False
    
    # Check tool keywords (prefer using tools for real-time data)
    tool_keywords = settings.KNOWLEDGE["detection"]["tool_keywords"]
    for keyword in tool_keywords:
        if keyword in message_lower:
            logger.debug(f"Skipping RAG - matched tool keyword: {keyword}")
            return False
    
    # Check activate keywords (knowledge queries)
    activate_keywords = settings.KNOWLEDGE["detection"]["activate_keywords"]
    for keyword in activate_keywords:
        if keyword in message_lower:
            logger.debug(f"Activating RAG - matched activate keyword: {keyword}")
            return True
    
    # Default: activate if message contains question mark
    if "?" in message:
        logger.debug("Activating RAG - message contains question mark")
        return True
    
    logger.debug("Skipping RAG - no activation triggers found")
    return False


def get_background_context() -> str:
    """
    Get Tier 1 background context from Artur Gomes.md.
    
    Loads user profile information including:
    - Frontmatter fields (birthday, emails, phone, preferences)
    - Biography section
    - Links section
    - Notes section
    - Inferred relationships from person notes
    
    Returns:
        Formatted background context string (~250-300 tokens)
        Empty string if file not found or error occurs
    """
    try:
        # Load the main user profile note
        user_note_path = settings.PATHS["brain"] / "1. Notes" / "Artur Gomes.md"
        
        if not user_note_path.exists():
            logger.warning(f"User profile note not found: {user_note_path}")
            return ""
        
        # Read the file
        content = user_note_path.read_text(encoding="utf-8")
        
        # Parse frontmatter and content sections
        frontmatter, content_sections = _parse_note_with_frontmatter(content)
        
        # Build context string
        context_parts = []
        
        # Add current date/time for reference
        now = datetime.now(settings.TIMEZONE)
        context_parts.append(f"Current Date/Time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}")
        context_parts.append("")
        
        # Add frontmatter fields
        if frontmatter:
            context_parts.append("USER PROFILE:")
            
            # Basic info
            if "birthday" in frontmatter:
                context_parts.append(f"- Birthday: {frontmatter['birthday']}")
            if "emails" in frontmatter:
                emails = frontmatter["emails"]
                if isinstance(emails, list):
                    context_parts.append(f"- Emails: {', '.join(emails)}")
                else:
                    context_parts.append(f"- Emails: {emails}")
            if "phone" in frontmatter:
                context_parts.append(f"- Phone: {frontmatter['phone']}")
            
            # Relationships (inferred from person notes)
            relationships = _infer_relationships()
            if relationships:
                context_parts.append(f"- Relationships: {', '.join(relationships)}")
            
            # Preferences
            if "preferences" in frontmatter:
                prefs = frontmatter["preferences"]
                if isinstance(prefs, dict):
                    context_parts.append("- Preferences:")
                    for key, value in prefs.items():
                        context_parts.append(f"  - {key}: {value}")
                else:
                    context_parts.append(f"- Preferences: {prefs}")
            
            context_parts.append("")
        
        # Add content sections (Biography, Links, Notes - skip Meetings)
        for section_name in ["Biography", "Links", "Notes"]:
            if section_name in content_sections and content_sections[section_name].strip():
                context_parts.append(f"{section_name.upper()}:")
                context_parts.append(content_sections[section_name].strip())
                context_parts.append("")
        
        result = "\n".join(context_parts).strip()
        
        # Log token estimate (rough: ~4 chars per token)
        estimated_tokens = len(result) // 4
        logger.debug(f"Background context generated: ~{estimated_tokens} tokens")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get background context: {e}", exc_info=True)
        return ""


def get_rag_context(query: str) -> Optional[str]:
    """
    Get Tier 2 RAG context via semantic search.
    
    Searches vector store for relevant chunks from:
    - Vault notes
    - Person notes
    - Conversation history
    
    Args:
        query: Search query (typically the user's message)
        
    Returns:
        Formatted context string with sources, or None if no results
    """
    try:
        vector_store = get_vector_store()
        
        # Get configuration
        top_k = settings.KNOWLEDGE["rag_context"]["top_k"]
        threshold = settings.KNOWLEDGE["rag_context"]["similarity_threshold"]
        
        # Search vector store
        results = vector_store.search(
            query=query,
            top_k=top_k,
            threshold=threshold,
            filter_metadata=None  # Search all types
        )
        
        # Results already filtered by threshold in vector_store
        filtered_results = results
        
        if not filtered_results:
            logger.debug(f"No RAG results above threshold {threshold}")
            return None
        
        # Format results with sources
        context_parts = []
        
        for i, result in enumerate(filtered_results, 1):
            source = result.metadata.get("source", "Unknown")
            content = result.content
            similarity = result.similarity
            
            # Format source citation
            context_parts.append(f"[{i}] {source} (relevance: {similarity:.2f})")
            context_parts.append(content)
            context_parts.append("")
        
        result_text = "\n".join(context_parts).strip()
        
        # Log token estimate
        estimated_tokens = len(result_text) // 4
        logger.debug(f"RAG context generated: {len(filtered_results)} chunks, ~{estimated_tokens} tokens")
        
        return result_text
        
    except Exception as e:
        logger.error(f"Failed to get RAG context: {e}", exc_info=True)
        return None


def build_enhanced_prompt(
    original_prompt: str,
    background_context: Optional[str] = None,
    rag_context: Optional[str] = None
) -> str:
    """
    Combine original system prompt with context layers.
    
    Format:
        {original_prompt}
        
        [BACKGROUND CONTEXT]
        {background_context}
        
        [RELEVANT CONTEXT]
        {rag_context}
    
    Args:
        original_prompt: Base system prompt
        background_context: Tier 1 background context (optional)
        rag_context: Tier 2 RAG context (optional)
        
    Returns:
        Enhanced prompt with injected context
    """
    parts = [original_prompt]
    
    if background_context:
        parts.append("\n\n--- BACKGROUND CONTEXT ---")
        parts.append(background_context)
    
    if rag_context:
        parts.append("\n\n--- RELEVANT CONTEXT ---")
        parts.append(rag_context)
    
    return "\n".join(parts)


def _parse_note_with_frontmatter(content: str) -> Tuple[Dict, Dict[str, str]]:
    """
    Parse markdown note with YAML frontmatter and content sections.
    
    Args:
        content: Raw markdown content with frontmatter
        
    Returns:
        Tuple of (frontmatter_dict, sections_dict)
        - frontmatter_dict: Parsed YAML frontmatter
        - sections_dict: Dict mapping section names to content
    """
    frontmatter = {}
    sections = {}
    
    # Extract frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
            content = parts[2]
    
    # Parse content sections by ## headers
    sections = _parse_content_sections(content)
    
    return frontmatter, sections


def _parse_content_sections(content: str) -> Dict[str, str]:
    """
    Parse markdown content into sections by ## headers.
    
    Skips:
    - Dataview code blocks (```dataview ... ```)
    - Meetings section
    
    Args:
        content: Markdown content (after frontmatter)
        
    Returns:
        Dict mapping section names to content
    """
    sections = {}
    current_section = None
    current_lines = []
    in_dataview = False
    
    for line in content.split("\n"):
        # Toggle dataview block state
        if line.strip().startswith("```dataview"):
            in_dataview = True
            continue
        if in_dataview and line.strip() == "```":
            in_dataview = False
            continue
        if in_dataview:
            continue
        
        # Check for ## header
        if line.startswith("## "):
            # Save previous section
            if current_section and current_section != "Meetings":
                sections[current_section] = "\n".join(current_lines).strip()
            
            # Start new section
            current_section = line[3:].strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)
    
    # Save last section
    if current_section and current_section != "Meetings":
        sections[current_section] = "\n".join(current_lines).strip()
    
    return sections


def _infer_relationships() -> List[str]:
    """
    Infer relationships by reading person notes with relationship field.
    
    Reads all notes in brain/1. Notes/ matching person pattern (name + last name).
    Looks for 'relationship' field in frontmatter.
    
    Returns:
        List of relationship strings (e.g., ["Camila Santos (wife)", "John Doe (friend)"])
    """
    relationships = []
    
    try:
        notes_dir = settings.PATHS["brain"] / "1. Notes"
        
        if not notes_dir.exists():
            return relationships
        
        # Find all markdown files
        for note_path in notes_dir.glob("*.md"):
            # Skip Artur Gomes.md itself
            if note_path.name == "Artur Gomes.md":
                continue
            
            # Read note
            try:
                content = note_path.read_text(encoding="utf-8")
                
                # Parse frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            frontmatter = yaml.safe_load(parts[1]) or {}
                            
                            # Check for relationship field
                            if "relationship" in frontmatter:
                                person_name = note_path.stem
                                relationship = frontmatter["relationship"]
                                relationships.append(f"{person_name} ({relationship})")
                        except yaml.YAMLError:
                            continue
            except Exception as e:
                logger.warning(f"Failed to read person note {note_path.name}: {e}")
                continue
        
        logger.debug(f"Inferred {len(relationships)} relationships")
        
    except Exception as e:
        logger.error(f"Failed to infer relationships: {e}", exc_info=True)
    
    return relationships
