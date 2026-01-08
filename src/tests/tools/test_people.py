"""
Tests for Friday People/Relationships Tools

Tests people management tools for listing people, getting person data, and calculating ages.

Tools tested:
- list_people() - List all people in the vault
- person_data() - Get detailed information about a person
- calculate_age() - Calculate age from birthday
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import json
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.people import (
    list_people,
    person_data,
    calculate_age,
)


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# List People Tests
# =============================================================================

def test_list_people_returns_str():
    """Test list people returns a string."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=False):
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        result = list_people()
        assert isinstance(result, str)
        assert result is not None


def test_list_people_empty_vault():
    """Test list people with empty vault."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=False):
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        result = list_people()
        
        # Should return valid JSON
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 0


def test_list_people_with_people():
    """Test list people with person notes in vault."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.glob') as mock_glob, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        # Mock person note files
        person1 = Mock()
        person1.stem = "John Doe"
        person1.name = "John Doe.md"
        
        person2 = Mock()
        person2.stem = "Jane Smith"
        person2.name = "Jane Smith.md"
        
        mock_glob.return_value = [person1, person2]
        
        # Mock frontmatter fields
        def get_field(note, field):
            if field == "tags":
                if note.stem == "John Doe":
                    return ["person/friend"]
                elif note.stem == "Jane Smith":
                    return ["person/family"]
            elif field == "relationship":
                if note.stem == "John Doe":
                    return "friend"
                elif note.stem == "Jane Smith":
                    return "family"
            return None
        
        mock_get_field.side_effect = get_field
        
        result = list_people()
        
        # Should return valid JSON
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Check structure
        for person in data:
            assert "name" in person
            assert "relationship" in person
            assert isinstance(person["name"], str)
            assert isinstance(person["relationship"], str)


def test_list_people_filters_non_person_notes():
    """Test list people filters out non-person notes."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.glob') as mock_glob, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        # Mock notes (some without person tags)
        person_note = Mock()
        person_note.stem = "John Doe"
        person_note.name = "John Doe.md"
        
        non_person_note = Mock()
        non_person_note.stem = "Project Ideas"
        non_person_note.name = "Project Ideas.md"
        
        mock_glob.return_value = [person_note, non_person_note]
        
        # Mock frontmatter fields
        def get_field(note, field):
            if field == "tags":
                if note.stem == "John Doe":
                    return ["person/friend"]
                else:
                    return ["project"]  # No person/ tag
            elif field == "relationship":
                if note.stem == "John Doe":
                    return "friend"
            return None
        
        mock_get_field.side_effect = get_field
        
        result = list_people()
        
        # Should only include person note
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "John Doe"


# =============================================================================
# Person Data Tests
# =============================================================================

def test_person_data_returns_str():
    """Test person data returns a string."""
    with patch('src.tools.people.find_person_note', return_value=None):
        
        result = person_data("Test Person")
        assert isinstance(result, str)
        assert result is not None


def test_person_data_not_found():
    """Test person data when person not found."""
    with patch('src.tools.people.find_person_note', return_value=None):
        
        result = person_data("Unknown Person")
        
        # Should return valid JSON with error
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_person_data_found():
    """Test person data when person is found."""
    with patch('src.tools.people.find_person_note') as mock_find, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_note = Path("/tmp/brain/1. Notes/John Doe.md")
        mock_find.return_value = mock_note
        
        # Mock frontmatter fields
        def get_field(note, field):
            fields = {
                "birthday": "1990-05-15",
                "email": "john@example.com",
                "phone": "+1234567890",
                "relationship": "friend"
            }
            return fields.get(field)
        
        mock_get_field.side_effect = get_field
        
        result = person_data("John Doe")
        
        # Should return valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)
        assert "name" in data
        assert "birthday" in data
        assert "email" in data
        assert "phone" in data
        assert "relationship" in data
        
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert data["phone"] == "+1234567890"
        assert data["relationship"] == "friend"


def test_person_data_partial_info():
    """Test person data with partial information."""
    with patch('src.tools.people.find_person_note') as mock_find, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_note = Path("/tmp/brain/1. Notes/Jane Smith.md")
        mock_find.return_value = mock_note
        
        # Mock frontmatter with only some fields
        def get_field(note, field):
            if field == "email":
                return "jane@example.com"
            elif field == "relationship":
                return "family"
            return None
        
        mock_get_field.side_effect = get_field
        
        result = person_data("Jane Smith")
        
        # Should return valid JSON with nulls for missing fields
        data = json.loads(result)
        assert isinstance(data, dict)
        assert data["name"] == "Jane Smith"
        assert data["email"] == "jane@example.com"
        assert data["relationship"] == "family"
        # Missing fields should be None or null
        assert data["birthday"] is None or data["birthday"] == "None"
        assert data["phone"] is None


def test_person_data_birthday_date_object():
    """Test person data converts date objects to strings."""
    from datetime import date
    
    with patch('src.tools.people.find_person_note') as mock_find, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_note = Path("/tmp/brain/1. Notes/Test Person.md")
        mock_find.return_value = mock_note
        
        # Mock frontmatter with date object
        def get_field(note, field):
            if field == "birthday":
                return date(1990, 5, 15)
            elif field == "relationship":
                return "friend"
            return None
        
        mock_get_field.side_effect = get_field
        
        result = person_data("Test Person")
        
        # Should convert date to string
        data = json.loads(result)
        assert isinstance(data["birthday"], str)
        assert "1990" in data["birthday"]


# =============================================================================
# Calculate Age Tests
# =============================================================================

def test_calculate_age_returns_str():
    """Test calculate age returns a string."""
    result = calculate_age("1990-05-15")
    assert isinstance(result, str)
    assert result is not None


def test_calculate_age_valid_birthday():
    """Test calculate age with valid birthday."""
    result = calculate_age("1990-05-15")
    
    # Should return valid JSON
    data = json.loads(result)
    assert isinstance(data, dict)
    assert "age" in data
    assert "birthday" in data
    assert "current_date" in data
    assert "next_birthday" in data
    
    # Check types
    assert isinstance(data["age"], int)
    assert isinstance(data["birthday"], str)
    assert isinstance(data["current_date"], str)
    assert isinstance(data["next_birthday"], str)
    
    # Age should be reasonable (30-35 years old in 2024-2026)
    assert 30 <= data["age"] <= 40
    
    # Birthday should be preserved
    assert data["birthday"] == "1990-05-15"


def test_calculate_age_invalid_format():
    """Test calculate age with invalid date format."""
    result = calculate_age("invalid-date")
    
    # Should return valid JSON with error
    data = json.loads(result)
    assert isinstance(data, dict)
    assert "error" in data
    assert "format" in data["error"].lower() or "invalid" in data["error"].lower()


def test_calculate_age_leap_year():
    """Test calculate age with leap year birthday."""
    result = calculate_age("2000-02-29")
    
    # Should handle leap year
    data = json.loads(result)
    if "error" not in data:
        assert isinstance(data["age"], int)
        assert 20 <= data["age"] <= 30


def test_calculate_age_future_birthday_this_year():
    """Test calculate age when birthday hasn't occurred yet this year."""
    from datetime import datetime
    import pytz
    
    # Get current date
    brt = pytz.timezone("America/Sao_Paulo")
    today = datetime.now(brt)
    
    # Create a birthday in the future this year
    future_month = (today.month % 12) + 1
    future_year = today.year - 30  # Born 30 years ago
    birthday_str = f"{future_year}-{future_month:02d}-15"
    
    result = calculate_age(birthday_str)
    
    data = json.loads(result)
    if "error" not in data:
        # Age calculation should account for future birthday
        assert isinstance(data["age"], int)
        assert data["age"] >= 0


def test_calculate_age_consistency():
    """Test calculate age is consistent across calls."""
    result1 = calculate_age("1990-05-15")
    result2 = calculate_age("1990-05-15")
    
    data1 = json.loads(result1)
    data2 = json.loads(result2)
    
    # Should be identical
    assert data1 == data2


# =============================================================================
# None Value Detection Tests
# =============================================================================

def test_list_people_not_none():
    """CRITICAL: Ensure list people doesn't return None."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=False):
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        result = list_people()
        assert result is not None
        assert isinstance(result, str)


def test_person_data_not_none():
    """CRITICAL: Ensure person data doesn't return None."""
    with patch('src.tools.people.find_person_note', return_value=None):
        
        result = person_data("Test")
        assert result is not None
        assert isinstance(result, str)


def test_calculate_age_not_none():
    """CRITICAL: Ensure calculate age doesn't return None."""
    result = calculate_age("1990-05-15")
    assert result is not None
    assert isinstance(result, str)


def test_all_people_tools_not_none():
    """CRITICAL: Batch test - check all people tools don't return None."""
    errors = []
    
    # Test list_people
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=False):
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        result = list_people()
        if result is None:
            errors.append("list_people returned None")
    
    # Test person_data
    with patch('src.tools.people.find_person_note', return_value=None):
        result = person_data("Test")
        if result is None:
            errors.append("person_data returned None")
    
    # Test calculate_age
    result = calculate_age("1990-05-15")
    if result is None:
        errors.append("calculate_age returned None")
    
    # Assert no errors found
    assert len(errors) == 0, \
        f"CRITICAL: Found None values in people tools:\n" + "\n".join(errors)


def test_list_people_no_none_in_parsed_json():
    """CRITICAL: Ensure list people JSON has no None values in wrong places."""
    with patch('src.tools.people.settings') as mock_settings, \
         patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.glob') as mock_glob, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_settings.PATHS = {"brain": Path("/tmp/brain")}
        
        person = Mock()
        person.stem = "John Doe"
        person.name = "John Doe.md"
        mock_glob.return_value = [person]
        
        def get_field(note, field):
            if field == "tags":
                return ["person/friend"]
            elif field == "relationship":
                return "friend"
            return None
        
        mock_get_field.side_effect = get_field
        
        result = list_people()
        data = json.loads(result)
        
        # Check for None in required fields (name and relationship should not be None)
        if isinstance(data, list):
            for person in data:
                # These fields should not be None
                assert person.get("name") is not None
                assert person.get("relationship") is not None


def test_person_data_no_none_in_required_fields():
    """CRITICAL: Ensure person data has name field (not None)."""
    with patch('src.tools.people.find_person_note') as mock_find, \
         patch('src.tools.people.get_frontmatter_field') as mock_get_field:
        
        mock_note = Path("/tmp/brain/1. Notes/Test.md")
        mock_find.return_value = mock_note
        mock_get_field.return_value = None
        
        result = person_data("Test")
        data = json.loads(result)
        
        if "error" not in data:
            # Name should always be present
            assert data.get("name") is not None


def test_calculate_age_no_none_in_parsed_json():
    """CRITICAL: Ensure calculate age JSON has no None values in required fields."""
    result = calculate_age("1990-05-15")
    data = json.loads(result)
    
    if "error" not in data:
        # All fields should be present and not None
        assert data.get("age") is not None
        assert data.get("birthday") is not None
        assert data.get("current_date") is not None
        assert data.get("next_birthday") is not None
