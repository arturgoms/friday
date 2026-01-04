"""
Vault integration for Friday knowledge management.

This module handles reading and writing to the Obsidian vault following
the hybrid approach:
- Simple user attributes → Artur Gomes.md frontmatter
- Complex observations → Friday.md sections
- Facts about others → Their person notes
"""

import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import logging

from src.core.constants import BRT

logger = logging.getLogger(__name__)

# Vault base path
VAULT_PATH = Path("/home/artur/friday/brain")

# Key file paths
USER_NOTE = VAULT_PATH / "1. Notes" / "Artur Gomes.md"
FRIDAY_NOTE = VAULT_PATH / "1. Notes" / "Friday.md"
NOTES_DIR = VAULT_PATH / "1. Notes"

# User attributes that go in frontmatter (simple facts)
USER_ATTRIBUTES = {
    'favorite_color', 'favorite_team', 'favorite_food', 'favorite_drink',
    'favorite_restaurant', 'favorite_movie', 'favorite_book', 'favorite_game',
    'occupation', 'location', 'timezone', 'language', 'height', 'weight',
    'blood_type', 'allergies', 'dietary_restrictions'
}

# Categories that indicate person-related facts
PERSON_CATEGORIES = {'family', 'friends', 'colleagues', 'contacts'}

# Patterns for detecting person-related facts
PERSON_PATTERNS = [
    r'(?:wife|husband|spouse|partner)(?:_name)?',
    r'(?:mother|father|parent|mom|dad)(?:_name)?',
    r'(?:sister|brother|sibling)(?:_name)?',
    r'(?:friend|colleague|boss|manager)(?:_name)?',
    r'.*_(?:birthday|phone|email|address)$'
]


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML frontmatter from markdown content.
    
    Returns:
        (frontmatter_dict, body_content)
    """
    if not content.startswith('---'):
        return {}, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2].lstrip('\n')
        return frontmatter, body
    except yaml.YAMLError as e:
        logger.error(f"[VAULT] Failed to parse frontmatter: {e}")
        return {}, content


def serialize_frontmatter(frontmatter: Dict[str, Any], body: str) -> str:
    """
    Serialize frontmatter dict and body back to markdown.
    """
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}"


def read_vault_file(filepath: Path) -> str:
    """Read content from vault file."""
    try:
        return filepath.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"[VAULT] File not found: {filepath}")
        return ""
    except Exception as e:
        logger.error(f"[VAULT] Failed to read {filepath}: {e}")
        return ""


def write_vault_file(filepath: Path, content: str) -> bool:
    """Write content to vault file."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        logger.info(f"[VAULT] Updated: {filepath}")
        return True
    except Exception as e:
        logger.error(f"[VAULT] Failed to write {filepath}: {e}")
        return False


def update_frontmatter_field(filepath: Path, field: str, value: Any) -> bool:
    """
    Update a single field in file's frontmatter.
    
    Args:
        filepath: Path to the markdown file
        field: Field name to update
        value: New value
    
    Returns:
        True if successful
    """
    content = read_vault_file(filepath)
    if not content:
        return False
    
    frontmatter, body = parse_frontmatter(content)
    frontmatter[field] = value
    
    # Update last_updated if it exists
    if 'last_updated' in frontmatter:
        frontmatter['last_updated'] = datetime.now(BRT).strftime('%Y-%m-%d')
    
    new_content = serialize_frontmatter(frontmatter, body)
    return write_vault_file(filepath, new_content)


def get_frontmatter_field(filepath: Path, field: str) -> Optional[Any]:
    """
    Get a single field from file's frontmatter.
    
    Returns:
        Field value or None if not found
    """
    content = read_vault_file(filepath)
    if not content:
        return None
    
    frontmatter, _ = parse_frontmatter(content)
    return frontmatter.get(field)


def parse_section(content: str, section_path: list[str]) -> Optional[str]:
    """
    Parse a specific section from markdown content.
    
    Args:
        content: Markdown content
        section_path: List of section headings (e.g., ['Learned Memories', 'Preferences'])
    
    Returns:
        Section content or None
    """
    lines = content.split('\n')
    current_level = 0
    target_level = len(section_path)
    matched_levels = 0
    section_start = None
    
    for i, line in enumerate(lines):
        # Check if this is a heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if not heading_match:
            continue
        
        level = len(heading_match.group(1))
        heading_text = heading_match.group(2).strip()
        
        # Check if we're in the right section
        if matched_levels < target_level and level == matched_levels + 2:  # +2 because main title is #
            if heading_text == section_path[matched_levels]:
                matched_levels += 1
                if matched_levels == target_level:
                    section_start = i + 1
                    current_level = level
        elif section_start is not None and level <= current_level:
            # Found next section at same or higher level, extract content
            return '\n'.join(lines[section_start:i]).strip()
    
    # If we matched and reached end of file
    if section_start is not None:
        return '\n'.join(lines[section_start:]).strip()
    
    return None


def update_section_item(filepath: Path, section_path: list[str], item_key: str, item_value: str) -> bool:
    """
    Update or add an item in a markdown section (bullet list format).
    
    Args:
        filepath: Path to markdown file
        section_path: Section hierarchy (e.g., ['Learned Memories', 'Preferences'])
        item_key: Item identifier (e.g., 'Favorite color')
        item_value: New value
    
    Returns:
        True if successful
    """
    content = read_vault_file(filepath)
    if not content:
        return False
    
    frontmatter, body = parse_frontmatter(content)
    lines = body.split('\n')
    
    # Find the section
    section_level = len(section_path)
    matched_levels = 0
    section_start = None
    section_end = None
    current_level = 0
    
    for i, line in enumerate(lines):
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if not heading_match:
            continue
        
        level = len(heading_match.group(1))
        heading_text = heading_match.group(2).strip()
        
        if matched_levels < section_level and level == matched_levels + 2:
            if heading_text == section_path[matched_levels]:
                matched_levels += 1
                if matched_levels == section_level:
                    section_start = i + 1
                    current_level = level
        elif section_start is not None and level <= current_level:
            section_end = i
            break
    
    if section_start is None:
        logger.error(f"[VAULT] Section not found: {' > '.join(section_path)}")
        return False
    
    if section_end is None:
        section_end = len(lines)
    
    # Find and update the item
    item_pattern = re.compile(rf'^-\s+{re.escape(item_key)}:\s+(.+)$', re.IGNORECASE)
    item_found = False
    
    for i in range(section_start, section_end):
        if item_pattern.match(lines[i]):
            lines[i] = f"- {item_key}: {item_value}"
            item_found = True
            break
    
    # If not found, add it
    if not item_found:
        # Find the last bullet point in the section
        last_bullet = section_start
        for i in range(section_start, section_end):
            if lines[i].strip().startswith('-'):
                last_bullet = i
        
        lines.insert(last_bullet + 1, f"- {item_key}: {item_value}")
    
    # Reconstruct content
    new_body = '\n'.join(lines)
    new_content = serialize_frontmatter(frontmatter, new_body)
    
    return write_vault_file(filepath, new_content)


def find_person_note(name: str) -> Optional[Path]:
    """
    Find a person note by name (supports aliases).
    
    Args:
        name: Person's name to search for
    
    Returns:
        Path to person note or None
    """
    if not NOTES_DIR.exists():
        return None
    
    # Check for exact filename match first
    exact_match = NOTES_DIR / f"{name}.md"
    if exact_match.exists():
        return exact_match
    
    # Search through all person notes
    for note_file in NOTES_DIR.glob("*.md"):
        if note_file.stem in ['Friday', 'Artur Gomes']:  # Skip these
            continue
        
        content = read_vault_file(note_file)
        frontmatter, _ = parse_frontmatter(content)
        
        # Check tags for person
        tags = frontmatter.get('tags', [])
        if not any('person/' in str(tag) for tag in tags):
            continue
        
        # Check aliases
        aliases = frontmatter.get('aliases', [])
        if name.lower() in [a.lower() for a in aliases]:
            return note_file
        
        # Check if name matches filename
        if name.lower() in note_file.stem.lower():
            return note_file
    
    return None


def create_person_note(name: str, relationship: str = 'friend', **kwargs) -> Optional[Path]:
    """
    Create a new person note from template.
    
    Args:
        name: Person's name
        relationship: Relationship type (family, friend, colleague, client)
        **kwargs: Additional frontmatter fields (birthday, email, phone, etc.)
    
    Returns:
        Path to created note or None
    """
    filepath = NOTES_DIR / f"{name}.md"
    
    if filepath.exists():
        logger.warning(f"[VAULT] Person note already exists: {name}")
        return filepath
    
    # Generate unique ID (timestamp-based)
    note_id = datetime.now(BRT).strftime('%Y%m%d%H%M%S')
    
    # Build frontmatter
    frontmatter = {
        'tags': [f'person/{relationship}', 'extra/memory'],
        'id': note_id,
        'created': datetime.now(BRT).strftime('%Y-%m-%d'),
        'created_by': 'friday'
    }
    
    # Add optional fields
    for key, value in kwargs.items():
        if value:
            frontmatter[key] = value
    
    # Build note body
    body = f"""# [[{name}]]

## Biography
<!-- Notes about {name} -->

## Links
<!-- External links, social media, etc. -->

## Notes
<!-- Additional observations and memories -->

## Meetings
<!-- Meeting notes will appear here -->
"""
    
    content = serialize_frontmatter(frontmatter, body)
    
    if write_vault_file(filepath, content):
        logger.info(f"[VAULT] Created person note: {name} (id: {note_id})")
        return filepath
    
    return None


def is_user_attribute(topic: str) -> bool:
    """Check if topic is a simple user attribute."""
    return topic.lower() in USER_ATTRIBUTES


def is_person_fact(topic: str, category: str) -> bool:
    """Check if fact is about a person."""
    if category.lower() in PERSON_CATEGORIES:
        return True
    
    for pattern in PERSON_PATTERNS:
        if re.match(pattern, topic.lower()):
            return True
    
    return False


def extract_person_name(topic: str, value: str) -> Optional[str]:
    """
    Extract person name from topic or value.
    
    Examples:
        wife_name, "Camila Santos" -> "Camila Santos"
        wife_birthday, "12/12" -> None (need context)
        best_friend, "Ron" -> "Ron"
    """
    # Check if value looks like a name (not a date, number, etc.)
    if re.match(r'^\d', value) or '/' in value or value.lower() in ['yes', 'no', 'true', 'false']:
        return None
    
    # If topic ends with _name, value is the name
    if topic.endswith('_name'):
        return value
    
    # If value contains space and capitalized words, likely a name
    if ' ' in value and all(word[0].isupper() for word in value.split() if word):
        return value
    
    # If it's a relationship topic without _name suffix
    relationship_topics = ['wife', 'husband', 'spouse', 'partner', 'mother', 'father', 
                          'sister', 'brother', 'best_friend', 'friend']
    if any(topic.lower().startswith(rel) for rel in relationship_topics):
        return value
    
    return None
