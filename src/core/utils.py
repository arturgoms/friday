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
