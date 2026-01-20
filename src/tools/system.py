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

# Friday Docker container names
FRIDAY_CONTAINERS = ["friday-telegram", "friday-awareness"]

# vLLM remote endpoint (from settings)
VLLM_ENDPOINT = settings.LLM.get("base_url", "http://192.168.1.18:8000/v1")


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
    """Get Friday service logs from Docker containers.

    Args:
        service: Container name (friday-telegram, friday-awareness, or 'all')
        lines: Number of log lines to return (default: 50, max: 200)

    Returns:
        Recent log entries from the specified container(s)
    """
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        return f"Error: Cannot connect to Docker: {e}"

    # Cap lines at 200 to avoid huge outputs
    lines = min(lines, 200)

    try:
        if service == "all":
            containers_to_check = FRIDAY_CONTAINERS
        elif service in FRIDAY_CONTAINERS:
            containers_to_check = [service]
        else:
            return f"Unknown service: {service}. Valid options: {', '.join(FRIDAY_CONTAINERS)} or 'all'"

        all_logs = []
        for container_name in containers_to_check:
            try:
                container = client.containers.get(container_name)
                logs = container.logs(tail=lines, timestamps=True).decode("utf-8")
                all_logs.append(f"=== {container_name} ===\n{logs}")
            except docker.errors.NotFound:
                all_logs.append(f"=== {container_name} ===\nContainer not found")

        return "\n\n".join(all_logs) if all_logs else "No logs found."

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

    Checks Docker containers for telegram/awareness and vLLM remote endpoint.

    Returns:
        Dict with status information for all Friday services
    """
    import httpx

    services_status = []

    # Check Docker containers via socket
    try:
        import docker
        client = docker.from_env()

        for container_name in FRIDAY_CONTAINERS:
            try:
                container = client.containers.get(container_name)
                services_status.append({
                    "service": container_name,
                    "type": "docker",
                    "state": container.status,
                    "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "n/a"),
                    "running": container.status == "running"
                })
            except docker.errors.NotFound:
                services_status.append({
                    "service": container_name,
                    "type": "docker",
                    "state": "not_found",
                    "running": False
                })
    except Exception as e:
        # Docker not available - likely running inside container without socket
        for container_name in FRIDAY_CONTAINERS:
            services_status.append({
                "service": container_name,
                "type": "docker",
                "state": "unknown",
                "error": f"Cannot check Docker: {str(e)}"
            })

    # Check vLLM remote endpoint
    try:
        # Hit the models endpoint to check if vLLM is responding
        vllm_url = VLLM_ENDPOINT.rstrip("/")
        response = httpx.get(f"{vllm_url}/models", timeout=5.0)

        if response.status_code == 200:
            models_data = response.json()
            model_names = [m.get("id", "unknown") for m in models_data.get("data", [])]
            services_status.append({
                "service": "friday-vllm",
                "type": "remote",
                "endpoint": vllm_url,
                "state": "running",
                "running": True,
                "models": model_names
            })
        else:
            services_status.append({
                "service": "friday-vllm",
                "type": "remote",
                "endpoint": vllm_url,
                "state": "error",
                "running": False,
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        services_status.append({
            "service": "friday-vllm",
            "type": "remote",
            "endpoint": VLLM_ENDPOINT,
            "state": "unreachable",
            "running": False,
            "error": str(e)
        })

    return {
        "services": services_status,
        "total_services": len(services_status),
        "timestamp": datetime.now(settings.TIMEZONE).isoformat()
    }


