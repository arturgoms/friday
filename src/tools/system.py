"""
Friday 3.0 System Tools

Example tools for system administration.
"""

import shutil
from datetime import datetime

from src.core.registry import friday_tool


@friday_tool(name="get_disk_usage")
def get_disk_usage(path: str = "/") -> str:
    """Get disk usage for a path.
    
    Args:
        path: Path to check disk usage for (default: root)
    
    Returns:
        Formatted string with disk usage information
    """
    try:
        total, used, free = shutil.disk_usage(path)
        
        # Convert to GB
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        percent = (used / total) * 100
        
        return (
            f"Disk usage for {path}:\n"
            f"  Total: {total_gb:.1f} GB\n"
            f"  Used: {used_gb:.1f} GB ({percent:.1f}%)\n"
            f"  Free: {free_gb:.1f} GB"
        )
    except Exception as e:
        return f"Error getting disk usage: {e}"


@friday_tool(name="get_current_time")
def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get the current date and time.
    
    Args:
        format: strftime format string
    
    Returns:
        Formatted current time string
    """
    return datetime.now().strftime(format)


@friday_tool(name="get_system_info")
def get_system_info() -> str:
    """Get basic system information.
    
    Returns:
        System information including OS, hostname, Python version
    """
    import platform
    import sys
    
    info_lines = [
        f"System: {platform.system()}",
        f"Release: {platform.release()}",
        f"Version: {platform.version()}",
        f"Machine: {platform.machine()}",
        f"Processor: {platform.processor()}",
        f"Hostname: {platform.node()}",
        f"Python: {sys.version}",
    ]
    
    return "\n".join(info_lines)


@friday_tool(name="get_uptime")
def get_uptime() -> str:
    """Get system uptime.
    
    Returns:
        Human-readable uptime string
    """
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        
        return "Uptime: " + ", ".join(parts) if parts else "Uptime: less than a minute"
    except Exception as e:
        return f"Error getting uptime: {e}"


@friday_tool(name="get_memory_usage")
def get_memory_usage() -> str:
    """Get system memory usage.
    
    Returns:
        Formatted memory usage information
    """
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        
        meminfo = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip().split()[0]  # Get numeric part
                meminfo[key] = int(value)
        
        total = meminfo.get("MemTotal", 0) / 1024 / 1024  # Convert to GB
        available = meminfo.get("MemAvailable", 0) / 1024 / 1024
        used = total - available
        percent = (used / total) * 100 if total > 0 else 0
        
        return (
            f"Memory Usage:\n"
            f"  Total: {total:.1f} GB\n"
            f"  Used: {used:.1f} GB ({percent:.1f}%)\n"
            f"  Available: {available:.1f} GB"
        )
    except Exception as e:
        return f"Error getting memory usage: {e}"
