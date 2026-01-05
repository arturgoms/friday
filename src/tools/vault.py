"""
Friday 3.0 Vault Tools

Tools for managing the Obsidian vault (brain folder).
Provides read/write/search operations on markdown notes.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent
from settings import settings

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


logger = logging.getLogger(__name__)

# Get vault path from settings
VAULT_PATH = settings.VAULT_PATH


def _get_vault_path() -> Path:
    """Get the vault path, ensuring it exists."""
    if not VAULT_PATH.exists():
        raise ValueError(f"Vault path does not exist: {VAULT_PATH}")
    return VAULT_PATH


def _safe_path(path: str) -> Path:
    """Validate and return safe path within vault."""
    vault = _get_vault_path()
    
    # Clean the path
    clean_path = path.strip().lstrip("/")
    
    # Resolve to absolute path
    full_path = (vault / clean_path).resolve()
    
    # Ensure it's within the vault (prevent path traversal)
    if not str(full_path).startswith(str(vault.resolve())):
        raise ValueError(f"Path traversal not allowed: {path}")
    
    return full_path


def _parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.
    
    Returns:
        Tuple of (frontmatter dict, content without frontmatter)
    """
    if not content.startswith("---"):
        return {}, content
    
    # Find the closing ---
    end_match = re.search(r'\n---\n', content[3:])
    if not end_match:
        return {}, content
    
    frontmatter_str = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]
    
    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        frontmatter = {}
    
    return frontmatter, body


def _serialize_frontmatter(frontmatter: Dict[str, Any], content: str) -> str:
    """Serialize frontmatter and content to markdown."""
    if not frontmatter:
        return content
    
    fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    return f"---\n{fm_str}---\n{content}"


# =============================================================================
# Vault Tools
# =============================================================================

@agent.tool_plain
def vault_read_note(path: str) -> str:
    """Read a note from the Obsidian vault.
    
    IMPORTANT: Use vault_search_notes first to find the exact path, then use that 
    full path here. Paths include folder prefixes like "1. Notes/filename.md".
    
    Args:
        path: Full relative path to the note (e.g., "1. Notes/my-note.md")
    
    Returns:
        Note content with frontmatter info
    """
    try:
        file_path = _safe_path(path)
        
        if not file_path.exists():
            return f"Note not found: {path}"
        
        if not file_path.suffix.lower() in ('.md', '.markdown', '.txt'):
            return f"Not a supported file type: {path}"
        
        content = file_path.read_text(encoding='utf-8')
        frontmatter, body = _parse_frontmatter(content)
        
        result = []
        if frontmatter:
            result.append("Frontmatter:")
            for key, value in frontmatter.items():
                result.append(f"  {key}: {value}")
            result.append("")
        
        result.append("Content:")
        result.append(body.strip())
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error reading note: {e}"


@agent.tool_plain
def vault_write_note(
    path: str,
    content: str,
    frontmatter: Optional[Dict[str, Any]] = None,
    mode: str = "overwrite"
) -> str:
    """Write or update a note in the Obsidian vault.
    
    Args:
        path: Relative path to the note
        content: Note content (without frontmatter)
        frontmatter: Optional frontmatter dict (title, tags, date, etc.)
        mode: "overwrite" (replace), "append", or "prepend"
    
    Returns:
        Success or error message
    """
    try:
        file_path = _safe_path(path)
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if mode == "overwrite":
            final_content = _serialize_frontmatter(frontmatter or {}, content)
        elif mode == "append":
            if file_path.exists():
                existing = file_path.read_text(encoding='utf-8')
                final_content = existing + "\n" + content
            else:
                final_content = _serialize_frontmatter(frontmatter or {}, content)
        elif mode == "prepend":
            if file_path.exists():
                existing = file_path.read_text(encoding='utf-8')
                fm, body = _parse_frontmatter(existing)
                final_content = _serialize_frontmatter(fm, content + "\n" + body)
            else:
                final_content = _serialize_frontmatter(frontmatter or {}, content)
        else:
            return f"Invalid mode: {mode}. Use 'overwrite', 'append', or 'prepend'"
        
        file_path.write_text(final_content, encoding='utf-8')
        return f"Successfully wrote note: {path} (mode: {mode})"
        
    except Exception as e:
        return f"Error writing note: {e}"


@agent.tool_plain
def vault_list_directory(path: str = "") -> str:
    """List files and folders in a vault directory.
    
    Args:
        path: Relative path to directory (empty for root)
    
    Returns:
        List of files and directories
    """
    try:
        dir_path = _safe_path(path) if path else _get_vault_path()
        
        if not dir_path.exists():
            return f"Directory not found: {path}"
        
        if not dir_path.is_dir():
            return f"Not a directory: {path}"
        
        dirs = []
        files = []
        
        for item in sorted(dir_path.iterdir()):
            # Skip hidden files and .obsidian
            if item.name.startswith('.'):
                continue
            
            if item.is_dir():
                dirs.append(f"📁 {item.name}/")
            elif item.suffix.lower() in ('.md', '.markdown', '.txt'):
                files.append(f"📄 {item.name}")
        
        result = [f"Directory: {path or '/'}"]
        result.append("=" * 40)
        
        if dirs:
            result.append("\nFolders:")
            result.extend(f"  {d}" for d in dirs)
        
        if files:
            result.append("\nFiles:")
            result.extend(f"  {f}" for f in files)
        
        if not dirs and not files:
            result.append("\n(empty)")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error listing directory: {e}"


@agent.tool_plain
def vault_search_notes(
    query: str,
    search_content: bool = True,
    search_filenames: bool = True,
    limit: int = 10
) -> str:
    """Search for notes in the vault by content or filename.
    
    Use this FIRST to find notes before reading them. Returns full paths 
    that can be used directly with vault_read_note.
    
    Args:
        query: Search query (case-insensitive)
        search_content: Search within file contents
        search_filenames: Search in filenames
        limit: Maximum results to return
    
    Returns:
        List of matching notes with full paths and excerpts
    """
    try:
        vault = _get_vault_path()
        # Split query into words for multi-word matching
        query_words = [w.lower() for w in query.split() if len(w) >= 2]
        results = []
        
        for file_path in vault.rglob("*.md"):
            # Skip hidden files and .obsidian
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            rel_path = file_path.relative_to(vault)
            match_type = None
            excerpt = ""
            match_score = 0
            
            filename_lower = file_path.name.lower()
            
            # Search filename - check if ALL words are in filename
            if search_filenames:
                filename_matches = sum(1 for w in query_words if w in filename_lower)
                if filename_matches == len(query_words):
                    match_type = "filename"
                    # Filename matches get high score (100 + match count)
                    match_score = 100 + filename_matches
            
            # Search content - check if ALL words are in content
            if search_content:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    content_lower = content.lower()
                    
                    content_matches = sum(1 for w in query_words if w in content_lower)
                    if content_matches == len(query_words):
                        if not match_type:
                            match_type = "content"
                            # Content-only matches get lower score
                            match_score = content_matches
                        
                        # Extract excerpt around first matching word
                        for w in query_words:
                            idx = content_lower.find(w)
                            if idx >= 0:
                                start = max(0, idx - 50)
                                end = min(len(content), idx + 100)
                                excerpt = content[start:end].replace('\n', ' ').strip()
                                if start > 0:
                                    excerpt = "..." + excerpt
                                if end < len(content):
                                    excerpt = excerpt + "..."
                                break
                except (OSError, UnicodeDecodeError) as e:
                    logger.debug(f"Failed to read file {file_path} for search: {e}")
            
            if match_type:
                results.append({
                    "path": str(rel_path),
                    "match": match_type,
                    "excerpt": excerpt,
                    "score": match_score
                })
            
            if len(results) >= limit * 3:  # Get extra to sort by score
                break
        
        # Sort by score (filename matches first, then content matches)
        results.sort(key=lambda x: -x.get("score", 0))
        
        if not results:
            return f"No notes found matching: {query}"
        
        # Limit to requested amount after sorting
        results = results[:limit]
        
        lines = [f"Search results for '{query}':"]
        
        # Highlight the best match
        if results:
            best = results[0]
            lines.append(f"\nBEST MATCH: {best['path']}")
            lines.append(f"(Use this path with vault_read_note)")
        
        lines.append("\nAll results:")
        for i, r in enumerate(results, 1):
            match_indicator = "***" if r['match'] == "filename" else ""
            lines.append(f"{i}. {r['path']} ({r['match']}) {match_indicator}")
            if r['excerpt']:
                lines.append(f"   {r['excerpt'][:100]}...")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error searching: {e}"


@agent.tool_plain
def vault_get_frontmatter(path: str) -> str:
    """Get only the frontmatter from a note.
    
    Args:
        path: Relative path to the note
    
    Returns:
        Frontmatter as formatted text
    """
    try:
        file_path = _safe_path(path)
        
        if not file_path.exists():
            return f"Note not found: {path}"
        
        content = file_path.read_text(encoding='utf-8')
        frontmatter, _ = _parse_frontmatter(content)
        
        if not frontmatter:
            return f"No frontmatter in: {path}"
        
        lines = [f"Frontmatter for: {path}", "=" * 40]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error reading frontmatter: {e}"


@agent.tool_plain
def vault_update_frontmatter(
    path: str,
    updates: Dict[str, Any],
    merge: bool = True
) -> str:
    """Update frontmatter of a note without changing content.
    
    Args:
        path: Relative path to the note
        updates: Dict of frontmatter fields to update
        merge: If True, merge with existing; if False, replace entirely
    
    Returns:
        Success or error message
    """
    try:
        file_path = _safe_path(path)
        
        if not file_path.exists():
            return f"Note not found: {path}"
        
        content = file_path.read_text(encoding='utf-8')
        frontmatter, body = _parse_frontmatter(content)
        
        if merge:
            frontmatter.update(updates)
        else:
            frontmatter = updates
        
        new_content = _serialize_frontmatter(frontmatter, body)
        file_path.write_text(new_content, encoding='utf-8')
        
        return f"Successfully updated frontmatter for: {path}"
        
    except Exception as e:
        return f"Error updating frontmatter: {e}"


@agent.tool_plain
def vault_manage_tags(
    path: str,
    operation: str = "list",
    tags: Optional[List[str]] = None
) -> str:
    """Manage tags in a note's frontmatter.
    
    Args:
        path: Relative path to the note
        operation: "list", "add", or "remove"
        tags: List of tags for add/remove operations
    
    Returns:
        Result of the operation
    """
    try:
        file_path = _safe_path(path)
        
        if not file_path.exists():
            return f"Note not found: {path}"
        
        content = file_path.read_text(encoding='utf-8')
        frontmatter, body = _parse_frontmatter(content)
        
        current_tags = frontmatter.get("tags", [])
        if isinstance(current_tags, str):
            current_tags = [current_tags]
        current_tags = list(current_tags)
        
        if operation == "list":
            if not current_tags:
                return f"No tags in: {path}"
            return f"Tags in {path}:\n" + "\n".join(f"  - {t}" for t in current_tags)
        
        elif operation == "add":
            if not tags:
                return "No tags provided to add"
            for tag in tags:
                if tag not in current_tags:
                    current_tags.append(tag)
            frontmatter["tags"] = current_tags
            
        elif operation == "remove":
            if not tags:
                return "No tags provided to remove"
            current_tags = [t for t in current_tags if t not in tags]
            frontmatter["tags"] = current_tags
            
        else:
            return f"Invalid operation: {operation}. Use 'list', 'add', or 'remove'"
        
        new_content = _serialize_frontmatter(frontmatter, body)
        file_path.write_text(new_content, encoding='utf-8')
        
        return f"Tags updated for {path}:\n" + "\n".join(f"  - {t}" for t in current_tags)
        
    except Exception as e:
        return f"Error managing tags: {e}"


@agent.tool_plain
def vault_create_daily_note(
    content: str = "",
    folder: str = "2. Time/Daily"
) -> str:
    """Create or append to today's daily note.
    
    Args:
        content: Content to add to the daily note
        folder: Folder for daily notes (default: 2. Time/Daily)
    
    Returns:
        Success message with path
    """
    try:
        today = datetime.now()
        filename = today.strftime("%Y-%m-%d.md")
        path = f"{folder}/{filename}"
        
        file_path = _safe_path(path)
        
        if file_path.exists():
            # Append to existing
            existing = file_path.read_text(encoding='utf-8')
            timestamp = today.strftime("%H:%M")
            new_content = existing + f"\n\n## {timestamp}\n{content}"
            file_path.write_text(new_content, encoding='utf-8')
            return f"Appended to daily note: {path}"
        else:
            # Create new
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            frontmatter = {
                "date": today.strftime("%Y-%m-%d"),
                "tags": ["daily", "journal"]
            }
            
            title = f"# {today.strftime('%A, %B %d, %Y')}\n\n"
            full_content = title + content
            
            final_content = _serialize_frontmatter(frontmatter, full_content)
            file_path.write_text(final_content, encoding='utf-8')
            
            return f"Created daily note: {path}"
        
    except Exception as e:
        return f"Error creating daily note: {e}"


@agent.tool_plain
def vault_rename_note(old_path: str, new_name: str) -> str:
    """Rename a note in the Obsidian vault.
    
    The note stays in the same folder, only the filename changes.
    Use vault_search_notes first to find the exact current path.
    
    Args:
        old_path: Current full path to the note (e.g., "0. Overview/My Note.md")
        new_name: New filename (e.g., "New Name.md" - will be placed in same folder)
    
    Returns:
        Success message with old and new paths, or error message
    """
    try:
        old_file = _safe_path(old_path)
        
        if not old_file.exists():
            return f"Note not found: {old_path}"
        
        if not old_file.suffix.lower() in ('.md', '.markdown', '.txt'):
            return f"Not a supported file type: {old_path}"
        
        # Ensure new_name has .md extension
        if not new_name.lower().endswith(('.md', '.markdown', '.txt')):
            new_name = new_name + '.md'
        
        # New path is in the same directory
        new_file = old_file.parent / new_name
        
        # Check if target already exists
        if new_file.exists():
            return f"A note already exists at: {new_file.relative_to(_get_vault_path())}"
        
        # Validate new path is still within vault
        new_file = _safe_path(str(new_file.relative_to(_get_vault_path())))
        
        # Perform rename
        old_file.rename(new_file)
        
        new_rel_path = new_file.relative_to(_get_vault_path())
        return f"Successfully renamed:\n  From: {old_path}\n  To: {new_rel_path}"
        
    except Exception as e:
        return f"Error renaming note: {e}"


@agent.tool_plain
def vault_move_note(old_path: str, new_folder: str) -> str:
    """Move a note to a different folder in the Obsidian vault.
    
    Use vault_search_notes first to find the exact current path.
    Use vault_list_directory to see available folders.
    
    Args:
        old_path: Current full path to the note (e.g., "0. Overview/My Note.md")
        new_folder: Destination folder (e.g., "1. Notes" or "4. Archive")
    
    Returns:
        Success message with old and new paths, or error message
    """
    try:
        old_file = _safe_path(old_path)
        
        if not old_file.exists():
            return f"Note not found: {old_path}"
        
        # Get the destination folder
        dest_folder = _safe_path(new_folder)
        
        if not dest_folder.exists():
            return f"Destination folder not found: {new_folder}"
        
        if not dest_folder.is_dir():
            return f"Destination is not a folder: {new_folder}"
        
        # New path keeps the same filename
        new_file = dest_folder / old_file.name
        
        # Check if target already exists
        if new_file.exists():
            return f"A note with this name already exists in {new_folder}"
        
        # Perform move
        old_file.rename(new_file)
        
        new_rel_path = new_file.relative_to(_get_vault_path())
        return f"Successfully moved:\n  From: {old_path}\n  To: {new_rel_path}"
        
    except Exception as e:
        return f"Error moving note: {e}"


@agent.tool_plain
def vault_delete_note(path: str, confirm: bool = False) -> str:
    """Delete a note from the Obsidian vault.
    
    CAUTION: This permanently deletes the note. Use vault_search_notes first 
    to find the exact path. Set confirm=True to actually delete.
    
    Args:
        path: Full path to the note to delete (e.g., "0. Overview/My Note.md")
        confirm: Must be True to actually delete (safety measure)
    
    Returns:
        Success message or error message
    """
    try:
        if not confirm:
            return f"Delete not confirmed. To delete '{path}', call vault_delete_note with confirm=True"
        
        file_path = _safe_path(path)
        
        if not file_path.exists():
            return f"Note not found: {path}"
        
        if not file_path.is_file():
            return f"Cannot delete: {path} is not a file"
        
        if not file_path.suffix.lower() in ('.md', '.markdown', '.txt'):
            return f"Cannot delete non-note file: {path}"
        
        # Delete the file
        file_path.unlink()
        
        return f"Successfully deleted: {path}"
        
    except Exception as e:
        return f"Error deleting note: {e}"
