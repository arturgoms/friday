"""
Friday 3.0 System Tools

Example tools for system administration.
"""

import shutil
import subprocess
from datetime import datetime, timezone, timedelta

from src.core.registry import friday_tool

# Friday service names
FRIDAY_SERVICES = ["friday-vllm", "friday-core", "friday-awareness", "friday-telegram"]

# Brazil timezone (UTC-3)
BRT = timezone(timedelta(hours=-3))


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
    """Get the current date and time in local timezone (UTC-3).
    
    Args:
        format: strftime format string
    
    Returns:
        Formatted current time string
    """
    return datetime.now(BRT).strftime(format)


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


@friday_tool(name="get_friday_logs")
def get_friday_logs(service: str = "all", lines: int = 50) -> str:
    """Get Friday service logs from journalctl.
    
    Args:
        service: Service name (friday-core, friday-vllm, friday-awareness, friday-telegram, or 'all')
        lines: Number of log lines to return (default: 50, max: 200)
    
    Returns:
        Recent log entries from the specified service(s)
    """
    try:
        # Cap lines at 200 to avoid huge outputs
        lines = min(lines, 200)
        
        # Build journalctl command
        cmd = ["journalctl", "--user", "-n", str(lines), "--no-pager"]
        
        if service == "all":
            # Add all Friday services
            for svc in FRIDAY_SERVICES:
                cmd.extend(["-u", svc])
        elif service in FRIDAY_SERVICES:
            cmd.extend(["-u", service])
        else:
            return f"Unknown service: {service}. Valid options: {', '.join(FRIDAY_SERVICES)} or 'all'"
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return f"Error getting logs: {result.stderr}"
        
        return result.stdout if result.stdout else "No logs found."
        
    except subprocess.TimeoutExpired:
        return "Error: Log retrieval timed out"
    except Exception as e:
        return f"Error getting logs: {e}"


@friday_tool(name="get_friday_status")
def get_friday_status() -> str:
    """Get status of all Friday services.
    
    Returns:
        Status information for all Friday services including state, PID, and memory usage
    """
    try:
        status_lines = ["Friday Service Status:", "=" * 50]
        
        for service in FRIDAY_SERVICES:
            result = subprocess.run(
                ["systemctl", "--user", "show", service, 
                 "--property=ActiveState,SubState,MainPID,MemoryCurrent"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            status = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    status[key] = value
            
            state = status.get("ActiveState", "unknown")
            substate = status.get("SubState", "unknown")
            pid = status.get("MainPID", "0")
            memory = status.get("MemoryCurrent", "0")
            
            # Format memory
            try:
                mem_bytes = int(memory)
                if mem_bytes > 1024 * 1024 * 1024:
                    mem_str = f"{mem_bytes / (1024**3):.1f} GB"
                elif mem_bytes > 1024 * 1024:
                    mem_str = f"{mem_bytes / (1024**2):.1f} MB"
                else:
                    mem_str = f"{mem_bytes / 1024:.1f} KB"
            except (ValueError, TypeError):
                mem_str = "N/A"
            
            pid_str = pid if pid != "0" else "N/A"
            
            status_lines.append(f"\n{service}:")
            status_lines.append(f"  State: {state} ({substate})")
            status_lines.append(f"  PID: {pid_str}")
            status_lines.append(f"  Memory: {mem_str}")
        
        return "\n".join(status_lines)
        
    except Exception as e:
        return f"Error getting status: {e}"
