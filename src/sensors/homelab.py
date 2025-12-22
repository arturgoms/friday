"""
Friday 3.0 Homelab Sensors

Monitors:
- External services (web apps, APIs) to detect outages
- Remote server hardware via Glances API

Services are configured in config/external_services.json
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from src.core.registry import friday_sensor

# =============================================================================
# Configuration
# =============================================================================

# Glances API endpoints for remote server monitoring
GLANCES_SERVERS = [
    {
        "name": "friday-server",
        "url": "http://localhost:61208",
        "display_name": "Friday Server (local)"
    },
    {
        "name": "portainer-server",
        "url": "http://192.168.1.16:61208",
        "display_name": "Portainer Server (192.168.1.16)"
    },
    {
        "name": "truenas",
        "url": "http://192.168.1.17:61208",
        "display_name": "TrueNAS (192.168.1.17)"
    }
]

# Cache for service config
_services_config: Optional[List[Dict]] = None
_config_mtime: float = 0


def _load_services_config() -> List[Dict]:
    """Load services configuration from JSON file.
    
    Caches the config and reloads if file changes.
    """
    global _services_config, _config_mtime
    
    config_path = Path("config/external_services.json")
    if not config_path.exists():
        return []
    
    current_mtime = config_path.stat().st_mtime
    if _services_config is not None and current_mtime == _config_mtime:
        return _services_config
    
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        _services_config = data.get("services", [])
        _config_mtime = current_mtime
        return _services_config
    except Exception as e:
        return []


def _check_service(service: Dict) -> Dict[str, Any]:
    """Check a single service's health.
    
    Args:
        service: Service configuration dict
        
    Returns:
        Dict with service status
    """
    name = service.get("name", "Unknown")
    url = service.get("url", "")
    timeout = service.get("timeout", 10)
    verify_ssl = service.get("verify_ssl", True)
    health_endpoint = service.get("health_endpoint", "")
    accept_codes = service.get("accept_codes", None)  # Custom acceptable status codes
    
    # Build full URL with optional health endpoint
    check_url = url.rstrip("/") + health_endpoint if health_endpoint else url
    
    start_time = time.time()
    
    try:
        with httpx.Client(timeout=timeout, verify=verify_ssl, follow_redirects=True) as client:
            response = client.get(check_url)
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Check if response code is acceptable
            if accept_codes:
                is_healthy = response.status_code in accept_codes
            else:
                # Default: 2xx and 3xx as success
                is_healthy = response.status_code < 400
            
            return {
                "name": name,
                "url": url,
                "status": "up" if is_healthy else "degraded",
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
                "error": None
            }
    except httpx.ConnectError as e:
        return {
            "name": name,
            "url": url,
            "status": "down",
            "status_code": None,
            "response_time_ms": None,
            "error": "Connection refused"
        }
    except httpx.TimeoutException:
        return {
            "name": name,
            "url": url,
            "status": "down",
            "status_code": None,
            "response_time_ms": None,
            "error": f"Timeout after {timeout}s"
        }
    except httpx.SSLError as e:
        return {
            "name": name,
            "url": url,
            "status": "down",
            "status_code": None,
            "response_time_ms": None,
            "error": "SSL/TLS error"
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "status": "down",
            "status_code": None,
            "response_time_ms": None,
            "error": str(e)
        }


@friday_sensor(name="homelab_services", interval_seconds=120)
def check_homelab_services() -> Dict[str, Any]:
    """Check all configured homelab services.
    
    Checks are done in parallel for efficiency.
    
    Returns:
        Dictionary with overall status and per-service details
    """
    services = _load_services_config()
    
    if not services:
        return {
            "sensor": "homelab_services",
            "error": "No services configured",
            "services": []
        }
    
    results = []
    
    # Check services in parallel using threads
    with ThreadPoolExecutor(max_workers=min(len(services), 10)) as executor:
        future_to_service = {
            executor.submit(_check_service, svc): svc 
            for svc in services
        }
        
        for future in as_completed(future_to_service):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                svc = future_to_service[future]
                results.append({
                    "name": svc.get("name", "Unknown"),
                    "url": svc.get("url", ""),
                    "status": "error",
                    "error": str(e)
                })
    
    # Calculate summary stats
    total = len(results)
    up_count = sum(1 for r in results if r["status"] == "up")
    down_count = sum(1 for r in results if r["status"] == "down")
    degraded_count = sum(1 for r in results if r["status"] == "degraded")
    
    # Determine overall status
    if down_count > 0:
        overall_status = "critical" if down_count > 1 else "warning"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    # List down services for easy access
    down_services = [r["name"] for r in results if r["status"] == "down"]
    
    return {
        "sensor": "homelab_services",
        "overall_status": overall_status,
        "total_services": total,
        "up": up_count,
        "down": down_count,
        "degraded": degraded_count,
        "down_services": down_services,
        "services": results
    }


# =============================================================================
# Remote Server Hardware Monitoring (via Glances API)
# =============================================================================

def _fetch_glances_data(server: Dict) -> Dict[str, Any]:
    """Fetch hardware metrics from a Glances API server.
    
    Auto-detects API version (v3 or v4).
    
    Args:
        server: Server config with name, url, display_name
        
    Returns:
        Dict with hardware metrics
    """
    url = server["url"]
    name = server["name"]
    display_name = server.get("display_name", name)
    
    try:
        with httpx.Client(timeout=10) as client:
            # Auto-detect API version (try v4 first, fall back to v3)
            api_version = "4"
            test_resp = client.get(f"{url}/api/4/status")
            if test_resp.status_code == 404:
                api_version = "3"
            
            # Fetch all metrics
            cpu_resp = client.get(f"{url}/api/{api_version}/cpu")
            mem_resp = client.get(f"{url}/api/{api_version}/mem")
            fs_resp = client.get(f"{url}/api/{api_version}/fs")
            load_resp = client.get(f"{url}/api/{api_version}/load")
            
            cpu = cpu_resp.json() if cpu_resp.status_code == 200 else {}
            mem = mem_resp.json() if mem_resp.status_code == 200 else {}
            fs_list = fs_resp.json() if fs_resp.status_code == 200 else []
            load = load_resp.json() if load_resp.status_code == 200 else {}
            
            # Get primary disk (usually the largest or root)
            # Filter out docker overlay mounts and small partitions
            real_disks = [
                d for d in fs_list 
                if d.get("fs_type") in ("ext4", "xfs", "btrfs", "zfs")
                and not d.get("mnt_point", "").startswith("/etc")
                and not d.get("mnt_point", "").startswith("/var/lib/docker")
            ]
            
            # If no real disks found, try to get unique disks by device
            if not real_disks and fs_list:
                seen_devices = set()
                for d in fs_list:
                    device = d.get("device_name", "")
                    if device and device not in seen_devices:
                        real_disks.append(d)
                        seen_devices.add(device)
                        break  # Just get the first one
            
            disk = real_disks[0] if real_disks else {}
            
            return {
                "server": name,
                "display_name": display_name,
                "status": "ok",
                "cpu_percent": cpu.get("total", 0),
                "cpu_cores": cpu.get("cpucore", 0),
                "memory_percent": mem.get("percent", 0),
                "memory_used_gb": round(mem.get("used", 0) / (1024**3), 1),
                "memory_total_gb": round(mem.get("total", 0) / (1024**3), 1),
                "disk_percent": disk.get("percent", 0),
                "disk_used_gb": round(disk.get("used", 0) / (1024**3), 1),
                "disk_total_gb": round(disk.get("size", 0) / (1024**3), 1),
                "disk_mount": disk.get("mnt_point", "unknown"),
                "load_1min": load.get("min1", 0),
                "load_5min": load.get("min5", 0),
                "load_15min": load.get("min15", 0),
            }
            
    except httpx.ConnectError:
        return {
            "server": name,
            "display_name": display_name,
            "status": "unreachable",
            "error": "Connection refused"
        }
    except httpx.TimeoutException:
        return {
            "server": name,
            "display_name": display_name,
            "status": "unreachable",
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "server": name,
            "display_name": display_name,
            "status": "error",
            "error": str(e)
        }


@friday_sensor(name="remote_server_hardware", interval_seconds=120)
def check_remote_server_hardware() -> Dict[str, Any]:
    """Check hardware metrics of remote servers via Glances API.
    
    Monitors CPU, memory, disk usage and load average.
    
    Returns:
        Dictionary with hardware metrics for all configured servers
    """
    results = []
    
    for server in GLANCES_SERVERS:
        data = _fetch_glances_data(server)
        results.append(data)
    
    # Check for any servers with issues
    servers_down = [r["server"] for r in results if r.get("status") != "ok"]
    servers_high_cpu = [r["server"] for r in results if r.get("cpu_percent", 0) > 80]
    servers_high_mem = [r["server"] for r in results if r.get("memory_percent", 0) > 90]
    servers_high_disk = [r["server"] for r in results if r.get("disk_percent", 0) > 90]
    
    # Determine overall status
    if servers_down:
        overall_status = "error"
    elif servers_high_disk or servers_high_mem:
        overall_status = "critical"
    elif servers_high_cpu:
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return {
        "sensor": "remote_server_hardware",
        "overall_status": overall_status,
        "servers_down": servers_down,
        "servers_high_cpu": servers_high_cpu,
        "servers_high_mem": servers_high_mem,
        "servers_high_disk": servers_high_disk,
        "servers": results
    }
