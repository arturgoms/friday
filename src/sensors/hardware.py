"""
Friday 3.0 Hardware Sensors

Example sensors for monitoring system hardware.
"""

import shutil
from typing import Dict, Any

from src.core.registry import friday_sensor


@friday_sensor(name="disk_usage", interval_seconds=300)
def check_disk_usage() -> Dict[str, Any]:
    """Check disk usage on root partition.
    
    Returns:
        Dictionary with disk usage information
    """
    try:
        total, used, free = shutil.disk_usage("/")
        
        return {
            "sensor": "disk_usage",
            "path": "/",
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception as e:
        return {
            "sensor": "disk_usage",
            "error": str(e)
        }


@friday_sensor(name="memory_usage", interval_seconds=60)
def check_memory_usage() -> Dict[str, Any]:
    """Check system memory usage.
    
    Returns:
        Dictionary with memory usage information
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
        
        total = meminfo.get("MemTotal", 0) / 1024  # Convert to MB
        available = meminfo.get("MemAvailable", 0) / 1024
        used = total - available
        percent = (used / total) * 100 if total > 0 else 0
        
        return {
            "sensor": "memory_usage",
            "total_mb": round(total, 2),
            "used_mb": round(used, 2),
            "available_mb": round(available, 2),
            "percent_used": round(percent, 1)
        }
    except Exception as e:
        return {
            "sensor": "memory_usage",
            "error": str(e)
        }


@friday_sensor(name="cpu_load", interval_seconds=60)
def check_cpu_load() -> Dict[str, Any]:
    """Check CPU load averages.
    
    Returns:
        Dictionary with CPU load information
    """
    try:
        with open("/proc/loadavg", "r") as f:
            load_data = f.read().strip().split()
        
        return {
            "sensor": "cpu_load",
            "load_1min": float(load_data[0]),
            "load_5min": float(load_data[1]),
            "load_15min": float(load_data[2]),
            "running_processes": load_data[3]
        }
    except Exception as e:
        return {
            "sensor": "cpu_load",
            "error": str(e)
        }


@friday_sensor(name="gpu_temperature", interval_seconds=120, enabled=False)
def check_gpu_temperature() -> Dict[str, Any]:
    """Check GPU temperature using nvidia-smi.
    
    Note: Disabled by default - enable if NVIDIA GPU is present.
    
    Returns:
        Dictionary with GPU temperature information
    """
    try:
        import subprocess
        
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            temp = int(result.stdout.strip())
            return {
                "sensor": "gpu_temperature",
                "temperature_celsius": temp,
                "status": "warning" if temp > 80 else "normal"
            }
        else:
            return {
                "sensor": "gpu_temperature",
                "error": "nvidia-smi failed"
            }
    except FileNotFoundError:
        return {
            "sensor": "gpu_temperature",
            "error": "nvidia-smi not found"
        }
    except Exception as e:
        return {
            "sensor": "gpu_temperature",
            "error": str(e)
        }
