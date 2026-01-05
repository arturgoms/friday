"""
People/Relationships Tools

Tools for managing information about people and their relationships to the user.
Reads data from Obsidian vault person notes.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import json
import logging
from pathlib import Path

from src.core.vault import get_frontmatter_field, find_person_note
from settings import settings

logger = logging.getLogger(__name__)


@agent.tool_plain
def list_people() -> str:
    """List all people in the vault with their names and relationship to the user.
    
    Use this to discover who people are before calling person_data.
    Scans the vault for person notes (notes with person/* tags).
    
    Returns:
        JSON string with list of people (name and relationship)
    """
    try:
        notes_dir = settings.PATHS["brain"] / "1. Notes"
        
        if not notes_dir.exists():
            logger.warning(f"[PEOPLE] Notes directory not found: {notes_dir}")
            return json.dumps([])
        
        people_list = []
        
        # Scan all markdown files in notes directory
        for note_file in notes_dir.glob("*.md"):
            # Skip non-person notes
            if note_file.stem in ["Friday", "Artur Gomes", "Virtual Memory"]:
                continue
            
            try:
                # Get relationship from frontmatter
                tags = get_frontmatter_field(note_file, "tags")
                
                # Check if it's a person note (has person/* tag)
                is_person = False
                if tags:
                    if isinstance(tags, list):
                        is_person = any(tag.startswith("person/") for tag in tags)
                    elif isinstance(tags, str):
                        is_person = "person/" in tags
                
                if is_person:
                    # Get relationship from frontmatter field (preferred) or tag fallback
                    relationship = get_frontmatter_field(note_file, "relationship")
                    
                    if not relationship:
                        # Fallback to tag (e.g., person/family -> family)
                        relationship = "unknown"
                        if isinstance(tags, list):
                            for tag in tags:
                                if tag.startswith("person/"):
                                    relationship = tag.replace("person/", "")
                                    break
                    
                    # Use filename as name (can be overridden by frontmatter if exists)
                    name = note_file.stem
                    
                    people_list.append({
                        "name": name,
                        "relationship": relationship
                    })
                    
            except Exception as e:
                logger.warning(f"[PEOPLE] Error reading {note_file.name}: {e}")
                continue
        
        logger.info(f"[PEOPLE] Listed {len(people_list)} people from vault")
        return json.dumps(people_list)
        
    except Exception as e:
        logger.error(f"[PEOPLE] Error listing people: {e}")
        return json.dumps({"error": str(e)})


@agent.tool_plain
def person_data(name: str) -> str:
    """Get detailed information about a specific person by name.
    
    Returns their email, birthday, phone, and relationship to the user from their vault note.
    
    Args:
        name: The person's name (e.g., 'Camila Santos', 'Sofia Menezes')
    
    Returns:
        JSON string with person details or error if not found
    """
    try:
        # Find the person's note in the vault
        person_note = find_person_note(name)
        
        if not person_note:
            logger.warning(f"[PEOPLE] Person not found: {name}")
            return json.dumps({"error": f"Person '{name}' not found in vault"})
        
        # Read frontmatter fields
        birthday = get_frontmatter_field(person_note, "birthday")
        
        # Convert date object to string if needed
        if birthday and hasattr(birthday, 'isoformat'):
            birthday = birthday.isoformat()
        
        person_info = {
            "name": name,
            "birthday": str(birthday) if birthday else None,
            "email": get_frontmatter_field(person_note, "email"),
            "phone": get_frontmatter_field(person_note, "phone"),
            "relationship": get_frontmatter_field(person_note, "relationship")
        }
        
        # Fallback to tags if no relationship field
        if not person_info["relationship"]:
            tags = get_frontmatter_field(person_note, "tags")
            if tags:
                if isinstance(tags, list):
                    for tag in tags:
                        if tag.startswith("person/"):
                            person_info["relationship"] = tag.replace("person/", "")
                            break
                elif isinstance(tags, str) and "person/" in tags:
                    person_info["relationship"] = tags.split("person/")[1].split()[0]
        
        logger.info(f"[PEOPLE] Retrieved data for: {name}")
        return json.dumps(person_info)
        
    except Exception as e:
        logger.error(f"[PEOPLE] Error getting person data: {e}")
        return json.dumps({"error": str(e)})


@agent.tool_plain
def calculate_age(birthday: str) -> str:
    """Calculate someone's current age from their birthday.
    
    Handles leap years and returns exact age with next birthday date.
    
    Args:
        birthday: Birthday in YYYY-MM-DD format (e.g., '1995-12-12')
    
    Returns:
        JSON string with age, birthday, current_date, and next_birthday
    """
    try:
        from datetime import datetime
        import pytz
        
        # Parse birthday
        birthday_date = datetime.strptime(birthday, "%Y-%m-%d")
        
        # Get current date in BRT timezone
        brt = pytz.timezone("America/Sao_Paulo")
        today = datetime.now(brt)
        
        # Calculate age
        age = today.year - birthday_date.year
        
        # Adjust if birthday hasn't occurred yet this year
        if (today.month, today.day) < (birthday_date.month, birthday_date.day):
            age -= 1
        
        # Calculate next birthday
        next_birthday_year = today.year if (today.month, today.day) < (birthday_date.month, birthday_date.day) else today.year + 1
        next_birthday = f"{next_birthday_year}-{birthday_date.month:02d}-{birthday_date.day:02d}"
        
        result = {
            "age": age,
            "birthday": birthday,
            "current_date": today.strftime("%Y-%m-%d"),
            "next_birthday": next_birthday
        }
        
        logger.info(f"[PEOPLE] Calculated age from {birthday}: {age} years old")
        return json.dumps(result)
        
    except ValueError as e:
        error_msg = f"Invalid birthday format. Use YYYY-MM-DD. Error: {str(e)}"
        logger.error(f"[PEOPLE] {error_msg}")
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error calculating age: {str(e)}"
        logger.error(f"[PEOPLE] {error_msg}")
        return json.dumps({"error": error_msg})
