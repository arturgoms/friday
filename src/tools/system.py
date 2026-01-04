"""
Friday 3.0 System Tools

Tools for system administration and monitoring.
"""

import logging
import shutil
import subprocess
from datetime import datetime, timezone, timedelta

from src.core.config import get_config, get_brt
from src.core.registry import friday_tool

logger = logging.getLogger(__name__)

# Friday service names
FRIDAY_SERVICES = ["friday-vllm", "friday-core", "friday-awareness", "friday-telegram"]


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
    return datetime.now(get_brt()).strftime(format)


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


@friday_tool(name="get_homelab_status")
def get_homelab_status() -> str:
    """Get full monitoring status of all homelab services and servers.
    
    Returns:
        Comprehensive status report including:
        - All monitored web services (up/down)
        - All server hardware metrics (CPU, memory, disk)
        - Garmin sync status
    """
    from src.sensors.homelab import check_homelab_services, check_remote_server_hardware
    from src.sensors.health import check_garmin_sync_status
    
    lines = []
    
    # ===== Server Hardware =====
    lines.append("SERVER HARDWARE")
    lines.append("=" * 50)
    
    try:
        hw_data = check_remote_server_hardware()
        for srv in hw_data.get("servers", []):
            name = srv.get("display_name", srv.get("server", "Unknown"))
            if srv.get("status") != "ok":
                lines.append(f"  {name}: {srv.get('error', 'Unreachable')}")
            else:
                cpu = srv.get("cpu_percent", 0)
                mem = srv.get("memory_percent", 0)
                disk = srv.get("disk_percent", 0)
                load = srv.get("load_5min", 0)
                cores = srv.get("cpu_cores", 1)
                
                # Status indicators
                mem_icon = "" if mem < 90 else "" if mem < 95 else ""
                disk_icon = "" if disk < 90 else "" if disk < 95 else ""
                
                lines.append(f"  {name}")
                lines.append(f"    CPU:  {cpu:5.1f}% ({cores} cores, load: {load:.2f})")
                lines.append(f"    Mem:  {mem:5.1f}% ({srv.get('memory_used_gb', 0):.1f}/{srv.get('memory_total_gb', 0):.1f} GB) {mem_icon}")
                lines.append(f"    Disk: {disk:5.1f}% ({srv.get('disk_used_gb', 0):.1f}/{srv.get('disk_total_gb', 0):.1f} GB) {disk_icon}")
    except Exception as e:
        lines.append(f"  Error fetching hardware data: {e}")
    
    lines.append("")
    
    # ===== Web Services =====
    lines.append("WEB SERVICES")
    lines.append("=" * 50)
    
    try:
        svc_data = check_homelab_services()
        up = svc_data.get("up", 0)
        down = svc_data.get("down", 0)
        total = svc_data.get("total_services", 0)
        
        lines.append(f"  Status: {up}/{total} services up")
        lines.append("")
        
        for svc in sorted(svc_data.get("services", []), key=lambda x: x.get("name", "")):
            name = svc.get("name", "Unknown")
            status = svc.get("status", "unknown")
            rt = svc.get("response_time_ms")
            
            if status == "up":
                icon = "UP"
                rt_str = f"({rt}ms)" if rt else ""
            elif status == "down":
                icon = "DOWN"
                rt_str = f"- {svc.get('error', 'Unknown error')}"
            else:
                icon = "WARN"
                rt_str = f"({svc.get('status_code', '?')})"
            
            lines.append(f"  [{icon:4}] {name:20} {rt_str}")
    except Exception as e:
        lines.append(f"  Error fetching services: {e}")
    
    lines.append("")
    
    # ===== Garmin Sync =====
    lines.append("GARMIN SYNC")
    lines.append("=" * 50)
    
    try:
        sync_data = check_garmin_sync_status()
        if "error" in sync_data:
            lines.append(f"  Error: {sync_data['error']}")
        else:
            hours = sync_data.get("hours_since_sync", 0)
            status = sync_data.get("status", "unknown")
            last_hr = sync_data.get("last_heart_rate", 0)
            
            status_icon = "OK" if hours < 6 else "WARN" if hours < 12 else "STALE"
            lines.append(f"  Status: {status_icon} - Last sync {hours:.1f} hours ago")
            lines.append(f"  Last HR: {last_hr} bpm")
    except Exception as e:
        lines.append(f"  Error: {e}")
    
    return "\n".join(lines)


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


@friday_tool(name="days_until_date")
def days_until_date(month: int, day: int, year: int = 0) -> str:
    """Calculate how many days until a specific date.
    
    Use this tool when the user asks "how many days until X" or "when is X birthday".
    DO NOT try to calculate dates yourself - always use this tool.
    
    Args:
        month: Month number (1-12, where 1=January, 12=December)
        day: Day of month (1-31)
        year: Optional specific year (if not provided, assumes current or next occurrence)
    
    Returns:
        String with the date and number of days until that date
    
    Examples:
        - days_until_date(12, 25) → Days until December 25th
        - days_until_date(3, 15, 2026) → Days until March 15, 2026
    """
    try:
        now = datetime.now(get_brt())
        
        # Determine target year
        if year and year > 0:
            target_year = year
        else:
            # Try current year first
            target_year = now.year
            target_date = datetime(target_year, month, day, tzinfo=BRT)
            
            # If date has already passed this year, use next year
            if target_date < now:
                target_year = now.year + 1
        
        # Create target date
        target_date = datetime(target_year, month, day, tzinfo=BRT)
        
        # Calculate difference
        delta = target_date - now
        days_until = delta.days
        
        # Format target date
        date_formatted = target_date.strftime("%B %d, %Y")
        day_name = target_date.strftime("%A")
        
        if days_until < 0:
            return f"❌ {date_formatted} ({day_name}) was {abs(days_until)} days ago"
        elif days_until == 0:
            return f"🎉 {date_formatted} is TODAY!"
        elif days_until == 1:
            return f"📅 {date_formatted} ({day_name}) is TOMORROW"
        else:
            return f"📅 {date_formatted} ({day_name}) is in {days_until} days"
        
    except Exception as e:
        logger.error(f"Error calculating days until date: {e}")
        return f"❌ Error: Invalid date - month={month}, day={day}, year={year}: {e}"


@friday_tool(name="days_between_dates")
def days_between_dates(month1: int, day1: int, month2: int, day2: int) -> str:
    """Calculate the difference in days between two dates (same year).
    
    Use this tool when the user asks "what's the difference between X and Y dates".
    DO NOT try to calculate date differences yourself - always use this tool.
    
    Args:
        month1: First date's month (1-12)
        day1: First date's day (1-31)
        month2: Second date's month (1-12)
        day2: Second date's day (1-31)
    
    Returns:
        String with the number of days between the two dates
    
    Examples:
        - days_between_dates(12, 25, 1, 1) → Days between Dec 25 and Jan 1
        - days_between_dates(3, 15, 12, 12) → Days between Mar 15 and Dec 12
    """
    try:
        now = datetime.now(get_brt())
        current_year = now.year
        
        # Create both dates in the same year for comparison
        date1 = datetime(current_year, month1, day1, tzinfo=BRT)
        date2 = datetime(current_year, month2, day2, tzinfo=BRT)
        
        # Calculate absolute difference
        delta = abs((date2 - date1).days)
        
        # Format dates
        date1_formatted = date1.strftime("%B %d")
        date2_formatted = date2.strftime("%B %d")
        
        # Determine which is earlier
        if date1 < date2:
            earlier = date1_formatted
            later = date2_formatted
        else:
            earlier = date2_formatted
            later = date1_formatted
        
        return f"📊 There are {delta} days between {earlier} and {later}"
        
    except Exception as e:
        logger.error(f"Error calculating days between dates: {e}")
        return f"❌ Error: Invalid dates - date1: {month1}/{day1}, date2: {month2}/{day2}: {e}"
