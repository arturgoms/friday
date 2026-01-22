"""
Friday Power Tools

UPS monitoring and power management tools using NUT (Network UPS Tools).
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

import logging
import subprocess
from typing import Any, Dict, Optional

from settings import settings
from src.core.agent import agent

logger = logging.getLogger(__name__)

# NUT server configuration
NUT_HOST = "192.168.1.208"
NUT_UPS_NAME = "nhs"


def _parse_upsc_output(output: str) -> Dict[str, str]:
    """Parse upsc command output into a dictionary.

    Args:
        output: Raw output from upsc command

    Returns:
        Dict mapping variable names to values
    """
    result = {}
    for line in output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def _parse_ups_status(status_str: str) -> Dict[str, Any]:
    """Parse UPS status flags into human-readable format.

    NUT status flags:
    - OL: Online (on AC power)
    - OB: On Battery
    - LB: Low Battery
    - HB: High Battery
    - RB: Replace Battery
    - CHRG: Charging
    - DISCHRG: Discharging
    - BYPASS: Bypass mode
    - CAL: Calibrating
    - OFF: Offline
    - OVER: Overloaded
    - TRIM: Trimming voltage
    - BOOST: Boosting voltage
    - FSD: Forced Shutdown

    Args:
        status_str: Space-separated status flags from ups.status

    Returns:
        Dict with parsed status information
    """
    flags = status_str.upper().split()

    # Determine power source
    on_battery = "OB" in flags
    on_line = "OL" in flags

    # Determine battery state
    low_battery = "LB" in flags
    replace_battery = "RB" in flags
    charging = "CHRG" in flags
    discharging = "DISCHRG" in flags

    # Determine UPS state
    overloaded = "OVER" in flags
    bypass = "BYPASS" in flags
    forced_shutdown = "FSD" in flags

    # Overall status determination
    if forced_shutdown:
        overall_status = "critical"
        status_text = "Forced shutdown imminent"
    elif low_battery and on_battery:
        overall_status = "critical"
        status_text = "On battery - LOW BATTERY"
    elif on_battery:
        overall_status = "warning"
        status_text = "On battery"
    elif overloaded:
        overall_status = "warning"
        status_text = "Overloaded"
    elif replace_battery:
        overall_status = "warning"
        status_text = "Battery needs replacement"
    elif on_line:
        overall_status = "normal"
        if charging:
            status_text = "Online - Charging"
        else:
            status_text = "Online"
    else:
        overall_status = "unknown"
        status_text = "Unknown status"

    return {
        "overall_status": overall_status,
        "status_text": status_text,
        "on_battery": on_battery,
        "on_line": on_line,
        "low_battery": low_battery,
        "replace_battery": replace_battery,
        "charging": charging,
        "discharging": discharging,
        "overloaded": overloaded,
        "bypass": bypass,
        "forced_shutdown": forced_shutdown,
        "raw_flags": flags,
    }


@agent.tool_plain
def get_ups_status(
    ups_name: str = NUT_UPS_NAME,
    host: str = NUT_HOST,
) -> Dict[str, Any]:
    """Get current UPS status from NUT server.

    Retrieves comprehensive UPS information including power status,
    battery charge, runtime estimate, and input/output voltages.

    Args:
        ups_name: Name of the UPS in NUT (default: nhs)
        host: NUT server hostname or IP (default: 192.168.1.208)

    Returns:
        Dict with UPS status including:
            - status: Overall status (normal/warning/critical)
            - on_battery: Whether running on battery power
            - battery_charge: Battery percentage
            - runtime_minutes: Estimated runtime in minutes
            - input_voltage: Input voltage from mains
            - output_voltage: Output voltage to equipment
            - load_percent: UPS load percentage
    """
    try:
        # Run upsc command to get UPS variables
        result = subprocess.run(
            ["upsc", f"{ups_name}@{host}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error"
            logger.error(f"upsc command failed: {error_msg}")
            return {
                "error": f"Failed to query UPS: {error_msg}",
                "status": "unreachable",
                "ups_name": ups_name,
                "host": host,
            }

        # Parse the output
        data = _parse_upsc_output(result.stdout)

        # Parse status flags
        status_info = _parse_ups_status(data.get("ups.status", ""))

        # Extract key metrics with safe parsing
        battery_charge = None
        if "battery.charge" in data:
            try:
                battery_charge = float(data["battery.charge"])
            except ValueError:
                pass

        runtime_seconds = None
        runtime_minutes = None
        if "battery.runtime" in data:
            try:
                runtime_seconds = int(data["battery.runtime"])
                runtime_minutes = round(runtime_seconds / 60, 1)
            except ValueError:
                pass

        input_voltage = None
        if "input.voltage" in data:
            try:
                input_voltage = float(data["input.voltage"])
            except ValueError:
                pass

        output_voltage = None
        if "output.voltage" in data:
            try:
                output_voltage = float(data["output.voltage"])
            except ValueError:
                pass

        load_percent = None
        if "ups.load" in data:
            try:
                load_percent = float(data["ups.load"])
            except ValueError:
                pass

        return {
            "ups_name": ups_name,
            "host": host,
            "status": status_info["overall_status"],
            "status_text": status_info["status_text"],
            "on_battery": status_info["on_battery"],
            "on_line": status_info["on_line"],
            "low_battery": status_info["low_battery"],
            "replace_battery": status_info["replace_battery"],
            "charging": status_info["charging"],
            "forced_shutdown": status_info["forced_shutdown"],
            "battery_charge": battery_charge,
            "runtime_seconds": runtime_seconds,
            "runtime_minutes": runtime_minutes,
            "input_voltage": input_voltage,
            "output_voltage": output_voltage,
            "load_percent": load_percent,
            "model": data.get("device.model", data.get("ups.model")),
            "manufacturer": data.get("device.mfr", data.get("ups.mfr")),
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout querying UPS {ups_name}@{host}")
        return {
            "error": "Timeout querying UPS",
            "status": "timeout",
            "ups_name": ups_name,
            "host": host,
        }
    except FileNotFoundError:
        logger.error("upsc command not found - is nut-client installed?")
        return {
            "error": "upsc command not found. Install nut-client package.",
            "status": "error",
            "ups_name": ups_name,
            "host": host,
        }
    except Exception as e:
        logger.error(f"Error querying UPS: {e}")
        return {
            "error": str(e),
            "status": "error",
            "ups_name": ups_name,
            "host": host,
        }


@agent.tool_plain
def report_ups_status() -> str:
    """Generate a formatted UPS status report.

    Returns a human-readable summary of UPS power status,
    battery level, and runtime estimate.

    Returns:
        Formatted status report string
    """
    data = get_ups_status()

    if "error" in data:
        return f"UPS Status: {data['error']}"

    lines = ["UPS Status Report", "=" * 40]

    # Status with icon
    status = data.get("status", "unknown")
    if status == "normal":
        icon = "✅"
    elif status == "warning":
        icon = "⚠️"
    elif status == "critical":
        icon = "🔴"
    else:
        icon = "❓"

    lines.append(f"{icon} Status: {data.get('status_text', 'Unknown')}")

    # Battery info
    if data.get("battery_charge") is not None:
        lines.append(f"🔋 Battery: {data['battery_charge']:.0f}%")

    if data.get("runtime_minutes") is not None:
        lines.append(f"⏱️ Runtime: {data['runtime_minutes']:.0f} minutes")

    # Power info
    if data.get("input_voltage") is not None:
        lines.append(f"⚡ Input: {data['input_voltage']:.0f}V")

    if data.get("output_voltage") is not None:
        lines.append(f"🔌 Output: {data['output_voltage']:.0f}V")

    if data.get("load_percent") is not None:
        lines.append(f"📊 Load: {data['load_percent']:.0f}%")

    # Model info
    if data.get("model"):
        lines.append(f"📦 Model: {data.get('manufacturer', '')} {data['model']}".strip())

    return "\n".join(lines)
