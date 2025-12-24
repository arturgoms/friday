"""
Friday Insights Engine - Homelab Collector

Collects homelab infrastructure data: services and hardware.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.core.constants import BRT
from src.insights.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class HomelabCollector(BaseCollector):
    """
    Collects homelab infrastructure metrics.
    
    Data collected:
    - Service health (20+ services)
    - Server hardware (CPU, memory, disk, load)
    - Local system stats
    """
    
    def __init__(self):
        super().__init__("homelab")
        self._services_config = None
        self._servers_config = None
    
    def initialize(self) -> bool:
        """Load service and server configurations."""
        try:
            # Load services config
            services_path = Path(__file__).parent.parent.parent.parent / "config" / "external_services.json"
            if services_path.exists():
                with open(services_path) as f:
                    self._services_config = json.load(f).get("services", [])
            
            # Server config (hardcoded for now)
            self._servers_config = [
                {"name": "friday", "host": "localhost", "port": 61208, "display_name": "Friday"},
                {"name": "portainer", "host": "192.168.1.16", "port": 61208, "display_name": "Portainer"},
                {"name": "truenas", "host": "192.168.1.17", "port": 61208, "display_name": "TrueNAS"},
            ]
            
            self._initialized = True
            logger.info("HomelabCollector initialized")
            return True
            
        except Exception as e:
            logger.error(f"HomelabCollector init failed: {e}")
            return False
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect homelab metrics."""
        if not self._initialized:
            if not self.initialize():
                return None
        
        now = datetime.now(BRT)
        
        # Run async collection - handle both running and new event loops
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, use nest_asyncio pattern or run sync
            # For simplicity, run sync versions
            services_data = self._check_services_sync()
            hardware_data = self._check_hardware_sync()
        except RuntimeError:
            # No running loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                services_data = loop.run_until_complete(self._check_services())
                hardware_data = loop.run_until_complete(self._check_hardware())
            finally:
                pass  # Don't close, might be reused
        
        local_data = self._get_local_stats()
        
        return {
            "collected_at": now.isoformat(),
            "services": services_data,
            "hardware": hardware_data,
            "local": local_data,
        }
    
    def _check_services_sync(self) -> Dict[str, Any]:
        """Synchronous version of service check using httpx sync client."""
        if not self._services_config:
            return {"total": 0, "up": 0, "down": 0, "services": []}
        
        import httpx
        
        results = []
        
        with httpx.Client(timeout=5.0, verify=False) as client:
            for svc in self._services_config:
                name = svc.get("name", "unknown")
                url = svc.get("url", "")
                
                if not url:
                    continue
                
                try:
                    response = client.get(url)
                    status = "up" if response.status_code < 500 else "down"
                    results.append({
                        "name": name,
                        "status": status,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                    })
                except Exception as e:
                    results.append({
                        "name": name,
                        "status": "down",
                        "error": str(e)[:100],
                    })
        
        up_count = sum(1 for r in results if r["status"] == "up")
        down_count = len(results) - up_count
        down_services = [r["name"] for r in results if r["status"] == "down"]
        
        return {
            "total": len(results),
            "up": up_count,
            "down": down_count,
            "down_services": down_services,
            "services": results,
        }
    
    def _check_hardware_sync(self) -> Dict[str, Any]:
        """Synchronous version of hardware check."""
        if not self._servers_config:
            return {"servers": []}
        
        import httpx
        
        servers = []
        
        with httpx.Client(timeout=5.0) as client:
            for srv in self._servers_config:
                host = srv["host"]
                port = srv["port"]
                name = srv["display_name"]
                
                server_data = {"name": name, "host": host}
                
                try:
                    base_url = f"http://{host}:{port}"
                    
                    # Detect API version (v4 is newer Glances)
                    try:
                        client.get(f"{base_url}/api/4/status")
                        api_version = 4
                    except Exception:
                        api_version = 3
                    
                    # Get stats
                    cpu = client.get(f"{base_url}/api/{api_version}/cpu")
                    mem = client.get(f"{base_url}/api/{api_version}/mem")
                    fs = client.get(f"{base_url}/api/{api_version}/fs")
                    load = client.get(f"{base_url}/api/{api_version}/load")
                    
                    cpu_data = cpu.json()
                    mem_data = mem.json()
                    fs_data = fs.json()
                    load_data = load.json()
                    
                    # Parse CPU
                    if isinstance(cpu_data, dict):
                        cpu_percent = cpu_data.get("total", 0)
                        cpu_cores = cpu_data.get("cpucore", 1)
                    else:
                        cpu_percent = 0
                        cpu_cores = 1
                    
                    # Parse memory
                    mem_percent = mem_data.get("percent", 0) if isinstance(mem_data, dict) else 0
                    
                    # Parse disk
                    disk_percent = 0
                    if isinstance(fs_data, list):
                        for disk in fs_data:
                            pct = disk.get("percent", 0)
                            if pct > disk_percent:
                                disk_percent = pct
                    
                    # Parse load
                    if isinstance(load_data, dict):
                        load_1 = load_data.get("min1", 0)
                        load_5 = load_data.get("min5", 0)
                    else:
                        load_1 = load_5 = 0
                    
                    server_data.update({
                        "status": "ok",
                        "cpu_percent": round(cpu_percent, 1),
                        "cpu_cores": cpu_cores,
                        "memory_percent": round(mem_percent, 1),
                        "disk_percent": round(disk_percent, 1),
                        "load_1min": round(load_1, 2),
                        "load_5min": round(load_5, 2),
                    })
                    
                except Exception as e:
                    server_data.update({
                        "status": "error",
                        "error": str(e)[:100],
                    })
                
                servers.append(server_data)
        
        return {"servers": servers}
    
    async def _check_services(self) -> Dict[str, Any]:
        """Check health of all configured services."""
        if not self._services_config:
            return {"total": 0, "up": 0, "down": 0, "services": []}
        
        import httpx
        
        results = []
        
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            for svc in self._services_config:
                name = svc.get("name", "unknown")
                url = svc.get("url", "")
                
                if not url:
                    continue
                
                try:
                    response = await client.get(url)
                    status = "up" if response.status_code < 500 else "down"
                    results.append({
                        "name": name,
                        "status": status,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                    })
                except Exception as e:
                    results.append({
                        "name": name,
                        "status": "down",
                        "error": str(e)[:100],
                    })
        
        up_count = sum(1 for r in results if r["status"] == "up")
        down_count = len(results) - up_count
        down_services = [r["name"] for r in results if r["status"] == "down"]
        
        return {
            "total": len(results),
            "up": up_count,
            "down": down_count,
            "down_services": down_services,
            "services": results,
        }
    
    async def _check_hardware(self) -> Dict[str, Any]:
        """Check hardware stats from Glances API on each server."""
        if not self._servers_config:
            return {"servers": []}
        
        import httpx
        
        servers = []
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for srv in self._servers_config:
                host = srv["host"]
                port = srv["port"]
                name = srv["display_name"]
                
                server_data = {"name": name, "host": host}
                
                try:
                    # Detect API version
                    base_url = f"http://{host}:{port}"
                    
                    # Detect API version (v4 is newer Glances)
                    try:
                        await client.get(f"{base_url}/api/4/status")
                        api_version = 4
                    except Exception:
                        api_version = 3
                    
                    # Get stats
                    cpu = await client.get(f"{base_url}/api/{api_version}/cpu")
                    mem = await client.get(f"{base_url}/api/{api_version}/mem")
                    fs = await client.get(f"{base_url}/api/{api_version}/fs")
                    load = await client.get(f"{base_url}/api/{api_version}/load")
                    
                    cpu_data = cpu.json()
                    mem_data = mem.json()
                    fs_data = fs.json()
                    load_data = load.json()
                    
                    # Parse CPU
                    if isinstance(cpu_data, dict):
                        cpu_percent = cpu_data.get("total", 0)
                        cpu_cores = cpu_data.get("cpucore", 1)
                    else:
                        cpu_percent = 0
                        cpu_cores = 1
                    
                    # Parse memory
                    mem_percent = mem_data.get("percent", 0) if isinstance(mem_data, dict) else 0
                    
                    # Parse disk (find largest)
                    disk_percent = 0
                    if isinstance(fs_data, list):
                        for disk in fs_data:
                            pct = disk.get("percent", 0)
                            if pct > disk_percent:
                                disk_percent = pct
                    
                    # Parse load
                    if isinstance(load_data, dict):
                        load_1 = load_data.get("min1", 0)
                        load_5 = load_data.get("min5", 0)
                    else:
                        load_1 = load_5 = 0
                    
                    server_data.update({
                        "status": "ok",
                        "cpu_percent": round(cpu_percent, 1),
                        "cpu_cores": cpu_cores,
                        "memory_percent": round(mem_percent, 1),
                        "disk_percent": round(disk_percent, 1),
                        "load_1min": round(load_1, 2),
                        "load_5min": round(load_5, 2),
                    })
                    
                except Exception as e:
                    server_data.update({
                        "status": "error",
                        "error": str(e)[:100],
                    })
                
                servers.append(server_data)
        
        return {"servers": servers}
    
    def _get_local_stats(self) -> Dict[str, Any]:
        """Get local system stats."""
        import shutil
        import os
        
        # Disk usage
        try:
            total, used, free = shutil.disk_usage("/")
            disk_percent = (used / total) * 100
        except OSError as e:
            logger.debug(f"Failed to get disk usage: {e}")
            disk_percent = 0
        
        # Memory (read from /proc/meminfo)
        mem_percent = 0
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            meminfo = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])
                    meminfo[key] = val
            
            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", 0)
            mem_percent = ((total - available) / total) * 100
        except (OSError, ValueError, KeyError) as e:
            logger.debug(f"Failed to get memory info: {e}")
        
        # Load average
        try:
            load_1, load_5, load_15 = os.getloadavg()
        except OSError:
            load_1 = load_5 = load_15 = 0
        
        # GPU temperature (nvidia-smi)
        gpu_temp = None
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                gpu_temp = int(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass  # nvidia-smi not available or failed
        
        return {
            "disk_percent": round(disk_percent, 1),
            "memory_percent": round(mem_percent, 1),
            "load_1min": round(load_1, 2),
            "load_5min": round(load_5, 2),
            "gpu_temp": gpu_temp,
        }
