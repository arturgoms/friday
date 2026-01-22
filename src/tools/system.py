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

# Friday PM2 service names
PM2_SERVICES = ["friday-telegram", "friday-awareness"]

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
    """Get Friday service logs from PM2.

    Args:
        service: Service name (friday-telegram, friday-awareness, or 'all')
        lines: Number of log lines to return (default: 50, max: 200)

    Returns:
        Recent log entries from the specified service(s)
    """
    import json

    # Cap lines at 200 to avoid huge outputs
    lines = min(lines, 200)

    try:
        if service == "all":
            services_to_check = PM2_SERVICES
        elif service in PM2_SERVICES:
            services_to_check = [service]
        else:
            return f"Unknown service: {service}. Valid options: {', '.join(PM2_SERVICES)} or 'all'"

        all_logs = []
        for svc_name in services_to_check:
            try:
                result = subprocess.run(
                    ["pm2", "logs", svc_name, "--lines", str(lines), "--nostream"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                logs = result.stdout + result.stderr
                all_logs.append(f"=== {svc_name} ===\n{logs.strip()}")
            except subprocess.TimeoutExpired:
                all_logs.append(f"=== {svc_name} ===\nTimeout getting logs")
            except Exception as e:
                all_logs.append(f"=== {svc_name} ===\nError: {e}")

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

    Checks PM2 processes for telegram/awareness and vLLM remote endpoint.

    Returns:
        Dict with status information for all Friday services
    """
    import httpx
    import json

    services_status = []

    # Check PM2 processes
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            pm2_list = json.loads(result.stdout)
        else:
            pm2_list = []
    except Exception:
        pm2_list = []

    for svc_name in PM2_SERVICES:
        found = False
        for proc in pm2_list:
            if proc.get("name") == svc_name:
                found = True
                status = proc.get("pm2_env", {}).get("status", "unknown")
                pid = proc.get("pid", 0)
                memory = proc.get("monit", {}).get("memory", 0)
                restarts = proc.get("pm2_env", {}).get("restart_time", 0)
                services_status.append({
                    "service": svc_name,
                    "type": "pm2",
                    "state": status,
                    "pid": pid,
                    "memory_mb": round(memory / 1024 / 1024, 1) if memory else 0,
                    "restarts": restarts,
                    "running": status == "online"
                })
                break
        if not found:
            services_status.append({
                "service": svc_name,
                "type": "pm2",
                "state": "stopped",
                "running": False
            })

    # Check vLLM remote endpoint
    try:
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


