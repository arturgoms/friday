"""
Friday 3.0 System Tools

Tools for system administration and monitoring.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
import shutil
import subprocess
from datetime import datetime, timezone, timedelta

from settings import settings

logger = logging.getLogger(__name__)

# Friday service names
FRIDAY_SERVICES = ["friday-vllm", "friday-core", "friday-awareness", "friday-telegram"]


@agent.tool_plain
def get_friday_disk_usage(path: str = "/") -> dict:
    """Get Friday server disk usage.
    
    Atomic data tool that returns structured disk usage data for the Friday server.
    
    Args:
        path: Path to check disk usage for (default: root)
    
    Returns:
        Dict with disk usage information
    """
    try:
        total, used, free = shutil.disk_usage(path)
        
        # Convert to GB
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        percent = (used / total) * 100
        
        return {
            "path": path,
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "used_percent": round(percent, 1),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def get_friday_system_info() -> dict:
    """Get Friday server system information.
    
    Atomic data tool that returns structured system information for the Friday server.
    
    Returns:
        Dict with system information including OS, hostname, Python version
    """
    import platform
    import sys
    
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "python_version": sys.version,
        "python_version_short": platform.python_version(),
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


@agent.tool_plain
def get_friday_uptime() -> dict:
    """Get Friday server uptime.
    
    Atomic data tool that returns structured uptime data for the Friday server.
    
    Returns:
        Dict with uptime information
    """
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        return {
            "uptime_seconds": int(uptime_seconds),
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def get_friday_memory_usage() -> dict:
    """Get Friday server memory usage.
    
    Atomic data tool that returns structured memory usage data for the Friday server.
    
    Returns:
        Dict with memory usage information
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
        
        return {
            "total_gb": round(total, 2),
            "used_gb": round(used, 2),
            "available_gb": round(available, 2),
            "used_percent": round(percent, 1),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
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


@agent.tool_plain
def get_homelab_status() -> str:
    """Get comprehensive homelab infrastructure status.
    
    Returns:
        Comprehensive status report including:
        - All server hardware metrics (CPU, memory, disk)
        - Web service health checks
        - External service monitoring
    """
    from src.tools.sensors import get_all_homelab_stats
    return get_all_homelab_stats()


@agent.tool_plain
def get_friday_status() -> dict:
    """Get status of all Friday services.
    
    Atomic data tool that returns structured Friday service status data.
    
    Returns:
        Dict with status information for all Friday services
    """
    try:
        services_status = []
        
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
            
            # Handle MainPID
            pid_str = status.get("MainPID", "0")
            pid = int(pid_str) if pid_str.isdigit() else 0
            
            # Handle MemoryCurrent (can be "[not set]")
            mem_str = status.get("MemoryCurrent", "0")
            memory_bytes = int(mem_str) if mem_str.isdigit() else 0
            
            services_status.append({
                "service": service,
                "state": state,
                "substate": substate,
                "pid": pid if pid != 0 else None,
                "memory_bytes": memory_bytes,
                "memory_mb": round(memory_bytes / (1024**2), 1) if memory_bytes > 0 else 0
            })
        
        return {
            "services": services_status,
            "total_services": len(FRIDAY_SERVICES),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


