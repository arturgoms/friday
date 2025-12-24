"""
Friday 3.0 Utilities

Shared utility functions used across the codebase.
"""

from typing import Optional


def format_duration(seconds: Optional[float]) -> str:
    """Format seconds to human-readable duration.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "2h 30m", "45m", or "0m"
        
    Examples:
        >>> format_duration(3600)
        '1h 0m'
        >>> format_duration(5400)
        '1h 30m'
        >>> format_duration(1800)
        '30m'
        >>> format_duration(0)
        '0m'
        >>> format_duration(None)
        '0m'
    """
    if seconds is None or seconds == 0:
        return "0m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_pace(speed_ms: Optional[float]) -> str:
    """Convert speed (m/s) to running pace (min:sec/km).
    
    Args:
        speed_ms: Speed in meters per second
        
    Returns:
        Formatted pace string like "5:30/km" or "N/A"
        
    Examples:
        >>> format_pace(3.0)  # ~5:33/km
        '5:33/km'
        >>> format_pace(0)
        'N/A'
    """
    if speed_ms is None or speed_ms <= 0:
        return "N/A"
    pace_min_km = 1000 / (speed_ms * 60)
    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/km"


def format_distance(meters: Optional[float], unit: str = "km") -> str:
    """Format distance in meters to human-readable format.
    
    Args:
        meters: Distance in meters
        unit: Output unit ("km" or "mi")
        
    Returns:
        Formatted distance string
        
    Examples:
        >>> format_distance(5000)
        '5.0 km'
        >>> format_distance(10500)
        '10.5 km'
    """
    if meters is None or meters == 0:
        return "0 km"
    if unit == "mi":
        miles = meters / 1609.344
        return f"{miles:.1f} mi"
    km = meters / 1000
    return f"{km:.1f} km"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_get(data: dict, *keys, default=None):
    """Safely get nested dictionary values.
    
    Args:
        data: Dictionary to search
        *keys: Keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at nested key path or default
        
    Examples:
        >>> safe_get({"a": {"b": 1}}, "a", "b")
        1
        >>> safe_get({"a": {"b": 1}}, "a", "c", default=0)
        0
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    return result
