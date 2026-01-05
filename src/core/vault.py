"""
Vault utilities for reading/writing Obsidian markdown files.

All paths are configured via settings.py (PATHS["brain"]).
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Add parent directory to path to import settings
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings


def get_notes_dir() -> Path:
    """Get the notes directory from settings.
    
    Returns:
        Path to notes directory (brain/1. Notes)
    """
    return settings.PATHS["brain"] / "1. Notes"


# Common note paths
def get_user_note() -> Path:
    """Get user note path (configured user profile)."""
    notes_dir = get_notes_dir()
    return notes_dir / f"{settings.USER['name']}.md"


def get_friday_note() -> Path:
    """Get Friday note path."""
    return get_notes_dir() / "Friday.md"


# Backwards compatibility constants
USER_NOTE = get_user_note()
FRIDAY_NOTE = get_friday_note()


def read_vault_file(file_path: Path) -> str:
    """Read a vault file.
    
    Args:
        file_path: Path to file
        
    Returns:
        File content as string
    """
    return file_path.read_text(encoding="utf-8")


def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse frontmatter from markdown content.
    
    Args:
        content: Markdown file content
        
    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}
    
    body = parts[2].strip()
    
    return frontmatter, body


def get_frontmatter_field(file_path: Path, field: str) -> Any:
    """Get a field from a file's frontmatter.
    
    Args:
        file_path: Path to file
        field: Field name
        
    Returns:
        Field value or None if not found
    """
    content = read_vault_file(file_path)
    frontmatter, _ = parse_frontmatter(content)
    return frontmatter.get(field)


def find_person_note(name: str) -> Optional[Path]:
    """Find a person note by name.
    
    Searches for notes with person/* tags.
    
    Args:
        name: Person name (e.g., "Camila Santos")
        
    Returns:
        Path to person note or None if not found
    """
    notes_dir = get_notes_dir()
    
    if not notes_dir.exists():
        return None
    
    # Try exact match first
    exact_match = notes_dir / f"{name}.md"
    if exact_match.exists():
        return exact_match
    
    # Try case-insensitive search
    name_lower = name.lower()
    for note_file in notes_dir.glob("*.md"):
        if note_file.stem.lower() == name_lower:
            # Verify it's a person note
            tags = get_frontmatter_field(note_file, "tags")
            if tags:
                if isinstance(tags, list):
                    if any("person/" in str(tag) for tag in tags):
                        return note_file
                elif isinstance(tags, str) and "person/" in tags:
                    return note_file
    
    return None


def update_frontmatter_field(file_path: Path, field: str, value: Any) -> bool:
    """Update a field in a file's frontmatter.
    
    Args:
        file_path: Path to file
        field: Field name
        value: New value
        
    Returns:
        True if updated successfully
    """
    content = read_vault_file(file_path)
    frontmatter, body = parse_frontmatter(content)
    
    # Update field
    frontmatter[field] = value
    
    # Write back
    new_content = "---\n"
    new_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    new_content += "---\n"
    new_content += body
    
    file_path.write_text(new_content, encoding="utf-8")
    return True


def update_section_item(file_path: Path, section: str, item: str) -> bool:
    """Update or add an item to a markdown section.
    
    Args:
        file_path: Path to file
        section: Section name (e.g., "## Notes")
        item: Item to add (markdown list item)
        
    Returns:
        True if updated successfully
    """
    content = read_vault_file(file_path)
    
    # Find or create section
    if section in content:
        # Append to existing section
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == section:
                # Insert after section header
                lines.insert(i + 1, item)
                break
    else:
        # Add section at end
        content += f"\n\n{section}\n{item}"
        lines = content.split("\n")
    
    new_content = "\n".join(lines)
    file_path.write_text(new_content, encoding="utf-8")
    return True


def create_person_note(name: str, relationship: str = "contact") -> Path:
    """Create a new person note.
    
    Args:
        name: Person name
        relationship: Relationship type (default: contact)
        
    Returns:
        Path to created note
    """
    notes_dir = get_notes_dir()
    note_path = notes_dir / f"{name}.md"
    
    if note_path.exists():
        return note_path
    
    # Create minimal person note
    content = f"""---
tags:
  - person/{relationship}
---

## Biography


## Links


## Notes
"""
    
    note_path.write_text(content, encoding="utf-8")
    return note_path


def is_user_attribute(field: str) -> bool:
    """Check if a field is a user attribute.
    
    Args:
        field: Field name
        
    Returns:
        True if it's a user attribute
    """
    user_fields = ["name", "email", "phone", "birthday", "location", "timezone"]
    return field.lower() in user_fields or field.startswith("favorite_")


def is_person_fact(topic: str) -> bool:
    """Check if a topic is about a person.
    
    Args:
        topic: Fact topic
        
    Returns:
        True if it's a person fact
    """
    person_fields = ["birthday", "email", "phone", "relationship", "location"]
    return any(field in topic.lower() for field in person_fields)


def extract_person_name(topic: str) -> Optional[str]:
    """Extract person name from a topic.
    
    Args:
        topic: Topic string (e.g., "camila_santos_birthday")
        
    Returns:
        Person name or None
    """
    # Simple heuristic: split by underscore and take first parts
    parts = topic.split("_")
    if len(parts) >= 2:
        # Assume first 2 parts are name
        return " ".join(parts[:2]).title()
    return None
