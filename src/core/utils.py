"""
Core utility functions for Friday.
"""


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "2h 30m" or "45m"
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours}h"
    
    return f"{hours}h {remaining_minutes}m"


def format_pace(seconds_per_km: float) -> str:
    """Format pace in min/km.
    
    Args:
        seconds_per_km: Pace in seconds per kilometer
        
    Returns:
        Formatted string like "5:30 min/km"
    """
    if seconds_per_km <= 0:
        return "N/A"
    
    minutes = int(seconds_per_km // 60)
    seconds = int(seconds_per_km % 60)
    
    return f"{minutes}:{seconds:02d} min/km"
