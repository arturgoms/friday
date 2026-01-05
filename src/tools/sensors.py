"""
Friday Sensor Tools

On-demand access to system sensors and monitoring data.
Converted from old passive sensors to active tools.
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
import time
from typing import Dict, Any

import httpx

from settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Hardware Sensors
# =============================================================================

@agent.tool_plain
def get_detailed_disk_usage(path: str = "/") -> str:
    """Get detailed disk usage information for a path.
    
    Use this for detailed disk space analysis beyond basic system info.
    
    Args:
        path: Path to check (default: root /)
        
    Returns:
        Formatted disk usage information
    """
    try:
        total, used, free = shutil.disk_usage(path)
        
        total_gb = round(total / (1024 ** 3), 2)
        used_gb = round(used / (1024 ** 3), 2)
        free_gb = round(free / (1024 ** 3), 2)
        percent_used = round((used / total) * 100, 1)
        
        result = [
            f"💾 Disk Usage for {path}:",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"Total:  {total_gb} GB",
            f"Used:   {used_gb} GB ({percent_used}%)",
            f"Free:   {free_gb} GB",
        ]
        
        # Add warning if usage is high
        if percent_used > 90:
            result.append("\n⚠️ WARNING: Disk usage is critically high!")
        elif percent_used > 80:
            result.append("\n⚠️ Disk usage is high")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error checking disk usage: {e}")
        return f"❌ Error checking disk usage: {str(e)}"


@agent.tool_plain
def get_detailed_memory_usage() -> str:
    """Get detailed system memory usage.
    
    Use this for detailed memory analysis beyond basic system info.
    
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
                value = parts[1].strip().split()[0]
                meminfo[key] = int(value)
        
        total_mb = meminfo.get("MemTotal", 0) / 1024
        available_mb = meminfo.get("MemAvailable", 0) / 1024
        used_mb = total_mb - available_mb
        percent_used = (used_mb / total_mb) * 100 if total_mb > 0 else 0
        
        # Get swap info
        swap_total_mb = meminfo.get("SwapTotal", 0) / 1024
        swap_free_mb = meminfo.get("SwapFree", 0) / 1024
        swap_used_mb = swap_total_mb - swap_free_mb
        swap_percent = (swap_used_mb / swap_total_mb) * 100 if swap_total_mb > 0 else 0
        
        result = [
            "🧠 Memory Usage:",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Total:     {round(total_mb, 2)} MB",
            f"Used:      {round(used_mb, 2)} MB ({round(percent_used, 1)}%)",
            f"Available: {round(available_mb, 2)} MB",
        ]
        
        if swap_total_mb > 0:
            result.append(f"\nSwap:      {round(swap_used_mb, 2)} MB / {round(swap_total_mb, 2)} MB ({round(swap_percent, 1)}%)")
        
        # Add warning if usage is high
        if percent_used > 90:
            result.append("\n⚠️ WARNING: Memory usage is critically high!")
        elif percent_used > 80:
            result.append("\n⚠️ Memory usage is high")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}")
        return f"❌ Error checking memory usage: {str(e)}"


@agent.tool_plain
def get_cpu_load() -> str:
    """Get CPU load averages.
    
    Returns 1, 5, and 15 minute load averages.
    
    Returns:
        Formatted CPU load information
    """
    try:
        with open("/proc/loadavg", "r") as f:
            load_data = f.read().strip().split()
        
        load_1 = float(load_data[0])
        load_5 = float(load_data[1])
        load_15 = float(load_data[2])
        
        result = [
            "⚙️ CPU Load Averages:",
            "━━━━━━━━━━━━━━━━━━━━",
            f"1 min:  {load_1}",
            f"5 min:  {load_5}",
            f"15 min: {load_15}",
        ]
        
        # Get CPU core count for context
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpu_cores = len([line for line in f if "processor" in line])
            result.append(f"\nCPU cores: {cpu_cores}")
            
            # Warn if load is high relative to cores
            if load_1 > cpu_cores * 0.8:
                result.append("\n⚠️ High CPU load detected")
        except:
            pass
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error checking CPU load: {e}")
        return f"❌ Error checking CPU load: {str(e)}"


# =============================================================================
# Homelab Service Monitoring
# =============================================================================

@agent.tool_plain
def check_external_service(url: str, timeout: int = 10) -> str:
    """Check if an external service/URL is accessible.
    
    Use this to monitor specific web services, APIs, or homelab applications.
    
    Args:
        url: URL to check (e.g., "http://192.168.1.16:8080")
        timeout: Request timeout in seconds (default: 10)
        
    Returns:
        Service status information
    """
    try:
        start_time = time.time()
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response_time_ms = int((time.time() - start_time) * 1000)
            
            status = "✅ UP" if response.status_code < 400 else "⚠️ DEGRADED"
            if response.status_code >= 500:
                status = "❌ DOWN"
            
            result = [
                f"{status} - {url}",
                f"━━━━━━━━━━━━━━━━━━━━",
                f"Status: {response.status_code}",
                f"Response time: {response_time_ms}ms",
            ]
            
            return "\n".join(result)
            
    except httpx.TimeoutException:
        return f"❌ TIMEOUT - {url}\nService did not respond within {timeout}s"
    except httpx.ConnectError:
        return f"❌ DOWN - {url}\nCould not connect to service"
    except Exception as e:
        return f"❌ ERROR - {url}\n{str(e)}"


@agent.tool_plain
def get_glances_server_stats(server_url: str = "http://192.168.1.16:61208") -> str:
    """Get hardware stats from a remote server running Glances.
    
    Use this to monitor remote server hardware (CPU, memory, disk).
    
    Args:
        server_url: Glances API URL (default: homelab server)
        
    Returns:
        Server hardware statistics
    """
    try:
        with httpx.Client(timeout=5) as client:
            # Get status
            status_resp = client.get(f"{server_url}/api/4/status")
            if status_resp.status_code != 200:
                return f"❌ Cannot reach Glances API at {server_url}"
            
            # Get CPU
            cpu_resp = client.get(f"{server_url}/api/4/cpu")
            cpu_data = cpu_resp.json()
            cpu_percent = cpu_data.get("total", 0)
            
            # Get memory
            mem_resp = client.get(f"{server_url}/api/4/mem")
            mem_data = mem_resp.json()
            mem_percent = mem_data.get("percent", 0)
            mem_used_gb = mem_data.get("used", 0) / (1024 ** 3)
            mem_total_gb = mem_data.get("total", 0) / (1024 ** 3)
            
            # Get load
            load_resp = client.get(f"{server_url}/api/4/load")
            load_data = load_resp.json()
            load_1 = load_data.get("min1", 0)
            
            result = [
                f"🖥️ Server Stats: {server_url}",
                "━━━━━━━━━━━━━━━━━━━━",
                f"CPU:    {cpu_percent}%",
                f"Memory: {mem_percent}% ({round(mem_used_gb, 1)}/{round(mem_total_gb, 1)} GB)",
                f"Load:   {load_1} (1min avg)",
            ]
            
            # Add warnings
            if cpu_percent > 80:
                result.append("\n⚠️ High CPU usage")
            if mem_percent > 80:
                result.append("⚠️ High memory usage")
            
            return "\n".join(result)
            
    except httpx.ConnectError:
        return f"❌ Cannot connect to Glances at {server_url}"
    except Exception as e:
        logger.error(f"Error getting Glances stats: {e}")
        return f"❌ Error: {str(e)}"


@agent.tool_plain
def get_all_homelab_stats() -> str:
    """Get hardware stats from all configured homelab servers.
    
    Checks all Glances servers configured in settings.
    
    Returns:
        Combined hardware statistics from all servers
    """
    servers = [
        ("Portainer Server", "http://192.168.1.16:61208"),
        ("TrueNAS", "http://192.168.1.17:61208"),
    ]
    
    results = ["🏠 Homelab Server Stats", "═" * 40]
    
    for name, url in servers:
        results.append(f"\n📊 {name}:")
        stats = get_glances_server_stats(url)
        # Remove the header from individual stats
        stats_lines = stats.split("\n")[2:]  # Skip first 2 lines (header)
        results.extend(stats_lines)
    
    return "\n".join(results)
