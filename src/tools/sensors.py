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

import logging
import shutil
import time
from typing import Any, Dict, List

import httpx

from settings import EXTERNAL_SERVICES
from src.core.agent import agent

logger = logging.getLogger(__name__)


# =============================================================================
# Hardware Sensors - Atomic Data Tools
# =============================================================================

@agent.tool_plain
def get_detailed_disk_usage(path: str = "/") -> Dict[str, Any]:
    """Get detailed disk usage information for a path.

    Use this for detailed disk space analysis beyond basic system info.

    Args:
        path: Path to check (default: root /)

    Returns:
        Dict with disk usage metrics and status
    """
    try:
        total, used, free = shutil.disk_usage(path)

        total_gb = round(total / (1024**3), 2)
        used_gb = round(used / (1024**3), 2)
        free_gb = round(free / (1024**3), 2)
        percent_used = round((used / total) * 100, 1)

        # Determine status
        status = "normal"
        if percent_used > 90:
            status = "critical"
        elif percent_used > 80:
            status = "warning"

        return {
            "path": path,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent_used": percent_used,
            "status": status,
        }

    except Exception as e:
        logger.error(f"Error checking disk usage: {e}")
        return {"error": str(e), "path": path}


@agent.tool_plain
def get_detailed_memory_usage() -> Dict[str, Any]:
    """Get detailed system memory usage.

    Use this for detailed memory analysis beyond basic system info.

    Returns:
        Dict with memory usage metrics and status
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

        # Determine status
        status = "normal"
        if percent_used > 90:
            status = "critical"
        elif percent_used > 80:
            status = "warning"

        return {
            "total_mb": round(total_mb, 2),
            "used_mb": round(used_mb, 2),
            "available_mb": round(available_mb, 2),
            "percent_used": round(percent_used, 1),
            "swap_total_mb": round(swap_total_mb, 2),
            "swap_used_mb": round(swap_used_mb, 2),
            "swap_percent": round(swap_percent, 1),
            "status": status,
        }

    except Exception as e:
        logger.error(f"Error checking memory usage: {e}")
        return {"error": str(e)}


@agent.tool_plain
def get_cpu_load() -> Dict[str, Any]:
    """Get CPU load averages.

    Returns 1, 5, and 15 minute load averages.

    Returns:
        Dict with CPU load metrics and status
    """
    try:
        with open("/proc/loadavg", "r") as f:
            load_data = f.read().strip().split()

        load_1 = float(load_data[0])
        load_5 = float(load_data[1])
        load_15 = float(load_data[2])

        # Get CPU core count for context
        cpu_cores = 1
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpu_cores = len([line for line in f if "processor" in line])
        except:
            pass

        # Determine status based on load relative to cores
        status = "normal"
        if load_1 > cpu_cores * 0.8:
            status = "high"

        return {
            "load_1min": load_1,
            "load_5min": load_5,
            "load_15min": load_15,
            "cpu_cores": cpu_cores,
            "status": status,
        }

    except Exception as e:
        logger.error(f"Error checking CPU load: {e}")
        return {"error": str(e)}


# =============================================================================
# Homelab Service Monitoring - Atomic Data Tools
# =============================================================================


@agent.tool_plain
def check_external_service(url: str, timeout: int = 10) -> Dict[str, Any]:
    """Check if an external service/URL is accessible.

    Use this to monitor specific web services, APIs, or homelab applications.

    Args:
        url: URL to check (e.g., "http://192.168.1.16:8080")
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with service status and response metrics
    """
    try:
        start_time = time.time()

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 405 Method Not Allowed means service is up, just doesn't accept GET
            if response.status_code < 400 or response.status_code == 405:
                status = "up"
            elif response.status_code >= 500 or response.status_code == 404:
                status = "down"  # 5xx or 404 = down
            else:
                status = "degraded"  # Other 4xx = degraded

            return {
                "url": url,
                "status": status,
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
            }

    except httpx.TimeoutException:
        return {
            "url": url,
            "status": "timeout",
            "error": f"Service did not respond within {timeout}s",
        }
    except httpx.ConnectError:
        return {
            "url": url,
            "status": "down",
            "error": "Could not connect to service",
        }
    except Exception as e:
        return {
            "url": url,
            "status": "error",
            "error": str(e),
        }


@agent.tool_plain
def get_glances_server_stats(server_url: str = "http://192.168.1.16:61208") -> Dict[str, Any]:
    """Get hardware stats from a remote server running Glances.

    Use this to monitor remote server hardware (CPU, memory, disk).

    Args:
        server_url: Glances API URL (default: homelab server)

    Returns:
        Dict with server hardware statistics
    """
    try:
        with httpx.Client(timeout=5) as client:
            # Get status
            status_resp = client.get(f"{server_url}/api/4/status")
            if status_resp.status_code != 200:
                return {
                    "server_url": server_url,
                    "error": "Cannot reach Glances API",
                    "status": "unreachable",
                }

            # Get CPU
            cpu_resp = client.get(f"{server_url}/api/4/cpu")
            cpu_data = cpu_resp.json()
            cpu_percent = cpu_data.get("total", 0)

            # Get memory
            mem_resp = client.get(f"{server_url}/api/4/mem")
            mem_data = mem_resp.json()
            mem_percent = mem_data.get("percent", 0)
            mem_used_gb = mem_data.get("used", 0) / (1024**3)
            mem_total_gb = mem_data.get("total", 0) / (1024**3)
            
            # Get load
            load_resp = client.get(f"{server_url}/api/4/load")
            load_data = load_resp.json()
            load_1 = load_data.get("min1", 0)

            # Determine overall status
            status = "normal"
            warnings = []
            if cpu_percent > 80:
                status = "warning"
                warnings.append("high_cpu")
            if mem_percent > 80:
                status = "warning"
                warnings.append("high_memory")

            return {
                "server_url": server_url,
                "status": status,
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(mem_percent, 1),
                "memory_used_gb": round(mem_used_gb, 1),
                "memory_total_gb": round(mem_total_gb, 1),
                "load_1min": round(load_1, 2),
                "warnings": warnings,
            }

    except httpx.ConnectError:
        return {
            "server_url": server_url,
            "status": "unreachable",
            "error": "Cannot connect to Glances",
        }
    except Exception as e:
        logger.error(f"Error getting Glances stats: {e}")
        return {
            "server_url": server_url,
            "status": "error",
            "error": str(e),
        }


@agent.tool_plain
def get_all_homelab_servers() -> Dict[str, Any]:
    """Get hardware stats from all configured homelab servers.

    Checks all Glances servers (Portainer, TrueNAS, Friday).

    Returns:
        Dict with stats from all servers
    """
    servers = [
        {"name": "Portainer Server", "url": "http://192.168.1.16:61208"},
        {"name": "TrueNAS", "url": "http://192.168.1.17:61208"},
        {"name": "Friday", "url": "http://192.168.1.18:61208"},
    ]

    results = []
    total_warnings = 0

    for server_info in servers:
        name = server_info["name"]
        url = server_info["url"]
        
        stats = get_glances_server_stats(url)
        stats["server_name"] = name
        
        if stats.get("warnings"):
            total_warnings += len(stats["warnings"])
        
        results.append(stats)

    # Determine overall status
    all_up = all(s.get("status") not in ["unreachable", "error"] for s in results)
    has_warnings = any(s.get("status") == "warning" for s in results)
    
    overall_status = "normal"
    if not all_up:
        overall_status = "degraded"
    elif has_warnings:
        overall_status = "warning"

    return {
        "overall_status": overall_status,
        "total_servers": len(servers),
        "total_warnings": total_warnings,
        "servers": results,
    }


@agent.tool_plain
def get_all_external_services() -> Dict[str, Any]:
    """Check status of all configured external services.
    
    Checks all homelab services configured in EXTERNAL_SERVICES.
    Returns a summary showing which services are up, down, or having issues.
    
    Returns:
        Dict with status of all external services
    """
    try:
        if not EXTERNAL_SERVICES:
            return {"error": "No external services configured"}
        
        results = []
        up_count = 0
        down_count = 0
        degraded_count = 0
        
        for service in EXTERNAL_SERVICES:
            name = service.get("name", "Unknown")
            url = service.get("url", "")
            timeout = service.get("timeout", 5)
            
            if not url:
                continue
            
            try:
                start_time = time.time()
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    response = client.get(url)
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    # 405 Method Not Allowed means service is up, just doesn't accept GET
                    if response.status_code < 400 or response.status_code == 405:
                        status = "up"
                        up_count += 1
                    elif response.status_code >= 500 or response.status_code == 404:
                        status = "down"  # 5xx or 404 = down
                        down_count += 1
                    else:
                        status = "degraded"  # Other 4xx = degraded
                        degraded_count += 1
                    
                    results.append({
                        "name": name,
                        "url": url,
                        "status": status,
                        "status_code": response.status_code,
                        "response_time_ms": response_time_ms,
                    })
            except httpx.TimeoutException:
                results.append({
                    "name": name,
                    "url": url,
                    "status": "timeout",
                    "error": "Request timed out",
                })
                down_count += 1
            except httpx.ConnectError:
                results.append({
                    "name": name,
                    "url": url,
                    "status": "down",
                    "error": "Connection failed",
                })
                down_count += 1
            except Exception as e:
                results.append({
                    "name": name,
                    "url": url,
                    "status": "error",
                    "error": str(e),
                })
                down_count += 1
        
        # Determine overall status
        total = len(results)
        if down_count > 0:
            overall_status = "degraded"
        elif degraded_count > 0:
            overall_status = "warning"
        else:
            overall_status = "normal"
        
        return {
            "overall_status": overall_status,
            "total_services": total,
            "up_count": up_count,
            "down_count": down_count,
            "degraded_count": degraded_count,
            "services": results,
        }
        
    except Exception as e:
        logger.error(f"Error checking external services: {e}")
        return {"error": str(e)}


# =============================================================================
# Composite Reports - Report Tools (return str, no snapshots)
# =============================================================================


@agent.tool_plain
def report_homelab_status() -> str:
    """Generate a comprehensive homelab status report.
    
    Combines server hardware stats and external service checks into a single report.
    Use this for a quick overview of the entire homelab infrastructure.
    
    Returns:
        Formatted status report
    """
    output = ["🏠 Homelab Status Report", "═" * 50, ""]
    
    # Server stats
    output.append("📊 SERVER HARDWARE:")
    output.append("─" * 50)
    servers_data = get_all_homelab_servers()
    
    for server in servers_data.get("servers", []):
        name = server.get("server_name", "Unknown")
        status_icon = "✅" if server.get("status") == "normal" else "⚠️" if server.get("status") == "warning" else "❌"
        
        output.append(f"\n{status_icon} {name}:")
        
        if server.get("error"):
            output.append(f"  Error: {server['error']}")
        else:
            output.append(f"  CPU: {server.get('cpu_percent', 0)}%")
            output.append(f"  Memory: {server.get('memory_percent', 0)}% ({server.get('memory_used_gb', 0)}/{server.get('memory_total_gb', 0)} GB)")
            output.append(f"  Load: {server.get('load_1min', 0)}")
            
            if server.get("warnings"):
                output.append(f"  ⚠️ Warnings: {', '.join(server['warnings'])}")
    
    output.append("\n")
    
    # External services
    output.append("🌐 EXTERNAL SERVICES:")
    output.append("─" * 50)
    services_data = get_all_external_services()
    
    total = services_data.get("total_services", 0)
    up = services_data.get("up_count", 0)
    down = services_data.get("down_count", 0)
    degraded = services_data.get("degraded_count", 0)
    
    output.append(f"Total: {total} | Up: {up} | Down: {down}" + (f" | Degraded: {degraded}" if degraded > 0 else ""))
    output.append("")
    
    # Group by status
    services = services_data.get("services", [])
    down_services = [s for s in services if s["status"] in ["down", "timeout", "error"]]
    degraded_services = [s for s in services if s["status"] == "degraded"]
    up_services = [s for s in services if s["status"] == "up"]
    
    # Show down/degraded services first (most important)
    if down_services:
        output.append("❌ DOWN/ERROR:")
        for s in down_services:
            error_msg = f" - {s.get('error', 'Unknown error')}" if s.get("error") else ""
            output.append(f"  • {s['name']}: {s['url']}{error_msg}")
        output.append("")
    
    if degraded_services:
        output.append("⚠️ DEGRADED:")
        for s in degraded_services:
            output.append(f"  • {s['name']}: {s['url']} - HTTP {s.get('status_code')} ({s.get('response_time_ms')}ms)")
        output.append("")
    
    if up_services:
        output.append("✅ UP:")
        for s in up_services:
            time_str = f" ({s['response_time_ms']}ms)" if s.get('response_time_ms') is not None else ""
            output.append(f"  • {s['name']}{time_str}")
    
    return "\n".join(output)
