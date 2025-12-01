"""
Markdown-based Memory Store for Friday AI.
Stores memories as editable markdown files in the brain folder.
"""
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from app.core.config import settings
from app.core.logging import logger


class MemoryStore:
    """
    Markdown-based memory storage.
    
    Memories are stored as individual .md files that can be:
    - Viewed and edited in Obsidian
    - Synced via Syncthing across devices
    - Searched using simple text matching
    """
    
    def __init__(self):
        """Initialize memory store."""
        self.memories_path = settings.memories_path
        
        # Ensure directory exists
        if not self.memories_path.exists():
            self.memories_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created memories directory: {self.memories_path}")
        
        logger.info(f"Memory store initialized: {self.memories_path}")
    
    def _generate_id(self) -> str:
        """Generate unique memory ID."""
        return str(uuid.uuid4())[:8]
    
    def _sanitize_filename(self, text: str) -> str:
        """Convert text to valid filename."""
        # Take first 50 chars, remove special characters
        text = text[:50]
        text = re.sub(r'[<>:"/\\|?*\n\r]', '', text)
        text = text.strip()
        text = re.sub(r'\s+', '_', text)
        return text if text else "memory"
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}, content
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        
        try:
            metadata = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return metadata, body
        except yaml.YAMLError:
            return {}, content
    
    def _format_memory(
        self,
        memory_id: str,
        content: str,
        label: str = "memory",
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
    ) -> str:
        """
        Format memory as markdown following the Obsidian Operating Manual format.
        Uses the Friday Memory template structure.
        """
        created_at = created_at or datetime.now()
        
        # Build tags list following the tagging system
        all_tags = ["area/friday", "extra/memory"]
        if tags:
            all_tags.extend(tags)
        
        # Format tags with proper YAML indentation
        tags_yaml = "\n".join([f"  - {tag}" for tag in all_tags])
        
        # Build frontmatter manually for correct formatting
        # Content goes directly under the frontmatter - no duplicate header
        note = f"""---
tags:
{tags_yaml}
aliases:
  - 
related: []
id: "{memory_id}"
created: "{created_at.strftime("%Y-%m-%d")}"
memory_type: "{label}"
---

{content}
"""
        return note
    
    def find_conflicting_memories(self, content: str) -> List[Dict[str, Any]]:
        """
        Find memories that might conflict with new content.
        
        Looks for memories with similar keywords (birthday, phone, favorite, etc.)
        
        Args:
            content: New memory content to check
            
        Returns:
            List of potentially conflicting memories
        """
        # Keywords that indicate personal facts that shouldn't have duplicates
        conflict_keywords = [
            'birthday', 'born', 'age',
            'phone', 'device', 'mobile',
            'favorite', 'favourite', 'prefer',
            'wife', 'husband', 'married', 'spouse',
            'work', 'job', 'company', 'employer',
            'live', 'address', 'home', 'house',
            'allergic', 'allergy',
            'email', 'contact',
        ]
        
        content_lower = content.lower()
        
        # Find which keywords are in the new content
        matching_keywords = [kw for kw in conflict_keywords if kw in content_lower]
        
        if not matching_keywords:
            return []
        
        # Search existing memories for these keywords
        conflicts = []
        for filepath in self.memories_path.glob("*.md"):
            try:
                file_content = filepath.read_text(encoding="utf-8").lower()
                
                # Check if any matching keywords are in this memory
                for kw in matching_keywords:
                    if kw in file_content:
                        metadata, body = self._parse_frontmatter(filepath.read_text(encoding="utf-8"))
                        conflicts.append({
                            "id": metadata.get("id", filepath.stem[:8]),
                            "content": body.strip(),
                            "filepath": str(filepath),
                            "keyword": kw,
                        })
                        break  # Only add once per file
                        
            except Exception as e:
                logger.error(f"Error checking {filepath}: {e}")
                continue
        
        return conflicts
    
    def add_memory(
        self,
        content: str,
        label: str = "memory",
        tags: Optional[List[str]] = None,
        force: bool = False,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Add a new memory, checking for conflicts first.
        
        Args:
            content: Memory content (markdown)
            label: Memory label/type (e.g., "explicit_memory", "chat_memory")
            tags: Optional tags for categorization
            force: If True, skip conflict checking
            
        Returns:
            Tuple of (memory_id, list of conflicts)
            - If conflicts exist and force=False, memory is NOT saved
            - If no conflicts or force=True, memory is saved
        """
        # Check for conflicts unless forced
        conflicts = []
        if not force:
            conflicts = self.find_conflicting_memories(content)
            if conflicts:
                logger.info(f"Found {len(conflicts)} potential conflicts for new memory")
                return (None, conflicts)
        
        memory_id = self._generate_id()
        filename = f"{memory_id}.md"
        filepath = self.memories_path / filename
        
        formatted = self._format_memory(
            memory_id=memory_id,
            content=content,
            label=label,
            tags=tags,
        )
        
        try:
            filepath.write_text(formatted, encoding="utf-8")
            logger.info(f"Added memory: {memory_id} - {filename}")
            return (memory_id, [])
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            raise
    
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        for filepath in self.memories_path.glob("*.md"):
            if filepath.name.startswith(memory_id):
                try:
                    content = filepath.read_text(encoding="utf-8")
                    metadata, body = self._parse_frontmatter(content)
                    return {
                        "id": metadata.get("id", memory_id),
                        "content": body,
                        "label": metadata.get("label"),
                        "tags": metadata.get("tags", []),
                        "created": metadata.get("created"),
                        "filepath": str(filepath),
                    }
                except Exception as e:
                    logger.error(f"Error reading memory {memory_id}: {e}")
                    return None
        return None
    
    def update_memory(self, memory_id: str, new_content: str) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory ID to update
            new_content: New content (replaces existing)
            
        Returns:
            True if successful
        """
        for filepath in self.memories_path.glob("*.md"):
            if filepath.name.startswith(memory_id):
                try:
                    # Read existing metadata
                    existing = filepath.read_text(encoding="utf-8")
                    metadata, _ = self._parse_frontmatter(existing)
                    
                    # Update with new content, preserve metadata
                    formatted = self._format_memory(
                        memory_id=metadata.get("id", memory_id),
                        content=new_content,
                        label=metadata.get("memory_type", "memory"),
                        tags=metadata.get("tags"),
                        created_at=datetime.fromisoformat(metadata["created"]) if metadata.get("created") else None,
                    )
                    
                    filepath.write_text(formatted, encoding="utf-8")
                    logger.info(f"Updated memory: {memory_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to update memory {memory_id}: {e}")
                    raise
        
        logger.warning(f"Memory not found: {memory_id}")
        return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        for filepath in self.memories_path.glob("*.md"):
            if filepath.name.startswith(memory_id):
                try:
                    filepath.unlink()
                    logger.info(f"Deleted memory: {memory_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete memory {memory_id}: {e}")
                    raise
        
        logger.warning(f"Memory not found: {memory_id}")
        return False
    
    def list_memories(
        self,
        label: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List all memories.
        
        Args:
            label: Filter by label (optional)
            limit: Maximum number of results
            
        Returns:
            List of memory dicts
        """
        memories = []
        
        for filepath in sorted(self.memories_path.glob("*.md"), 
                               key=lambda p: p.stat().st_mtime, 
                               reverse=True):
            try:
                content = filepath.read_text(encoding="utf-8")
                metadata, body = self._parse_frontmatter(content)
                
                # Filter by label if specified
                if label and metadata.get("label") != label:
                    continue
                
                memories.append({
                    "id": metadata.get("id", filepath.stem[:8]),
                    "content": body[:200] + "..." if len(body) > 200 else body,
                    "full_content": body,
                    "label": metadata.get("label"),
                    "tags": metadata.get("tags", []),
                    "created": metadata.get("created"),
                    "filepath": str(filepath),
                })
                
                if len(memories) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")
                continue
        
        return memories
    
    def search_memories(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search memories by content.
        
        Searches for ANY word from the query (OR search).
        Scores results by number of matching words.
        
        Args:
            query: Search query (words are OR'd together)
            limit: Maximum number of results
            
        Returns:
            List of matching memories, sorted by relevance
        """
        # Split query into words and lowercase
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        if not query_words:
            query_words = [query.lower()]
        
        scored_matches = []
        
        for filepath in self.memories_path.glob("*.md"):
            try:
                content = filepath.read_text(encoding="utf-8")
                content_lower = content.lower()
                
                # Count how many query words match
                match_count = sum(1 for word in query_words if word in content_lower)
                
                if match_count > 0:
                    metadata, body = self._parse_frontmatter(content)
                    scored_matches.append({
                        "score": match_count,
                        "data": {
                            "id": metadata.get("id", filepath.stem[:8]),
                            "content": body[:200] + "..." if len(body) > 200 else body,
                            "full_content": body,
                            "label": metadata.get("label"),
                            "tags": metadata.get("tags", []),
                            "created": metadata.get("created"),
                            "filepath": str(filepath),
                        }
                    })
                        
            except Exception as e:
                logger.error(f"Error searching {filepath}: {e}")
                continue
        
        # Sort by score (most matches first) and return top results
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        return [m["data"] for m in scored_matches[:limit]]
    
    def get_context_string(self, query: str, limit: int = 5) -> str:
        """
        Get memories as context string for LLM.
        
        Args:
            query: Search query
            limit: Maximum memories to include
            
        Returns:
            Formatted string with memories
        """
        memories = self.search_memories(query, limit)
        
        if not memories:
            return ""
        
        parts = []
        for mem in memories:
            parts.append(f"[Memory {mem['id']}]\n{mem['full_content']}")
        
        return "\n\n--- MEMORY ---\n\n".join(parts)
    
    def count(self) -> int:
        """Get total number of memories."""
        return len(list(self.memories_path.glob("*.md")))
    
    def clear_all(self) -> int:
        """Clear all memories (use with caution!)."""
        count = 0
        for filepath in self.memories_path.glob("*.md"):
            try:
                filepath.unlink()
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {filepath}: {e}")
        
        logger.info(f"Cleared {count} memories")
        return count


# Singleton instance
memory_store = MemoryStore()
