"""
Tests for Friday Sensor Tools

Tests all sensor monitoring tools including hardware sensors (disk, memory, CPU)
and homelab service monitoring (Glances servers, external services).

Tools tested:
- get_detailed_disk_usage() - Disk space monitoring
- get_detailed_memory_usage() - Memory usage stats
- get_cpu_load() - CPU load averages
- check_external_service() - Single service health check
- get_glances_server_stats() - Remote server monitoring
- get_all_homelab_servers() - All Glances servers
- get_all_external_services() - All external service checks
- report_homelab_status() - Comprehensive report
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.sensors import (
    get_detailed_disk_usage,
    get_detailed_memory_usage,
    get_cpu_load,
    check_external_service,
    get_glances_server_stats,
    get_all_homelab_servers,
    get_all_external_services,
    report_homelab_status,
)


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# Hardware Sensors Tests
# =============================================================================

def test_get_detailed_disk_usage_returns_dict():
    """Test disk usage tool returns a dict."""
    result = get_detailed_disk_usage("/")
    assert isinstance(result, dict)
    assert result is not None


def test_get_detailed_disk_usage_structure():
    """Test disk usage has correct structure."""
    result = get_detailed_disk_usage("/")
    
    if "error" not in result:
        assert "path" in result
        assert "total_gb" in result
        assert "used_gb" in result
        assert "free_gb" in result
        assert "percent_used" in result
        assert "status" in result
        
        # Type checks
        assert isinstance(result["path"], str)
        assert isinstance(result["total_gb"], (int, float))
        assert isinstance(result["used_gb"], (int, float))
        assert isinstance(result["free_gb"], (int, float))
        assert isinstance(result["percent_used"], (int, float))
        assert isinstance(result["status"], str)
        
        # Value checks
        assert result["total_gb"] > 0
        assert result["used_gb"] >= 0
        assert result["free_gb"] >= 0
        assert 0 <= result["percent_used"] <= 100
        assert result["status"] in ["normal", "warning", "critical"]


def test_get_detailed_disk_usage_custom_path():
    """Test disk usage with custom path."""
    result = get_detailed_disk_usage("/home")
    
    if "error" not in result:
        assert result["path"] == "/home"
        assert result["total_gb"] > 0


def test_get_detailed_disk_usage_invalid_path():
    """Test disk usage with invalid path returns error."""
    result = get_detailed_disk_usage("/nonexistent/path/12345")
    assert "error" in result


def test_get_detailed_memory_usage_returns_dict():
    """Test memory usage tool returns a dict."""
    result = get_detailed_memory_usage()
    assert isinstance(result, dict)
    assert result is not None


def test_get_detailed_memory_usage_structure():
    """Test memory usage has correct structure."""
    result = get_detailed_memory_usage()
    
    if "error" not in result:
        assert "total_mb" in result
        assert "used_mb" in result
        assert "available_mb" in result
        assert "percent_used" in result
        assert "swap_total_mb" in result
        assert "swap_used_mb" in result
        assert "swap_percent" in result
        assert "status" in result
        
        # Type checks
        assert isinstance(result["total_mb"], (int, float))
        assert isinstance(result["used_mb"], (int, float))
        assert isinstance(result["available_mb"], (int, float))
        assert isinstance(result["percent_used"], (int, float))
        assert isinstance(result["swap_total_mb"], (int, float))
        assert isinstance(result["swap_used_mb"], (int, float))
        assert isinstance(result["swap_percent"], (int, float))
        assert isinstance(result["status"], str)
        
        # Value checks
        assert result["total_mb"] > 0
        assert result["used_mb"] >= 0
        assert result["available_mb"] >= 0
        assert 0 <= result["percent_used"] <= 100
        assert result["status"] in ["normal", "warning", "critical"]


def test_get_cpu_load_returns_dict():
    """Test CPU load tool returns a dict."""
    result = get_cpu_load()
    assert isinstance(result, dict)
    assert result is not None


def test_get_cpu_load_structure():
    """Test CPU load has correct structure."""
    result = get_cpu_load()
    
    if "error" not in result:
        assert "load_1min" in result
        assert "load_5min" in result
        assert "load_15min" in result
        assert "cpu_cores" in result
        assert "status" in result
        
        # Type checks
        assert isinstance(result["load_1min"], (int, float))
        assert isinstance(result["load_5min"], (int, float))
        assert isinstance(result["load_15min"], (int, float))
        assert isinstance(result["cpu_cores"], int)
        assert isinstance(result["status"], str)
        
        # Value checks
        assert result["load_1min"] >= 0
        assert result["load_5min"] >= 0
        assert result["load_15min"] >= 0
        assert result["cpu_cores"] > 0
        assert result["status"] in ["normal", "high"]


# =============================================================================
# External Service Tests
# =============================================================================

def test_check_external_service_returns_dict():
    """Test external service check returns a dict."""
    # Use a mock to avoid real network call
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        result = check_external_service("http://example.com")
        assert isinstance(result, dict)
        assert result is not None


def test_check_external_service_success():
    """Test external service check with successful response."""
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        with patch('time.time', side_effect=[0.0, 0.1]):  # Mock 100ms response time
            result = check_external_service("http://example.com", timeout=5)
        
        assert "url" in result
        assert "status" in result
        assert "status_code" in result
        assert "response_time_ms" in result
        
        assert result["url"] == "http://example.com"
        assert result["status"] == "up"
        assert result["status_code"] == 200
        assert result["response_time_ms"] == 100


def test_check_external_service_timeout():
    """Test external service check with timeout."""
    with patch('httpx.Client') as mock_client:
        import httpx
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("Timeout")
        
        result = check_external_service("http://slow.example.com", timeout=1)
        
        assert "url" in result
        assert "status" in result
        assert "error" in result
        assert result["status"] == "timeout"


def test_check_external_service_connection_error():
    """Test external service check with connection error."""
    with patch('httpx.Client') as mock_client:
        import httpx
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("Connection failed")
        
        result = check_external_service("http://unreachable.example.com")
        
        assert "url" in result
        assert "status" in result
        assert "error" in result
        assert result["status"] == "down"


def test_check_external_service_405_is_up():
    """Test that 405 Method Not Allowed is considered 'up'."""
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 405
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        with patch('time.time', side_effect=[0.0, 0.05]):
            result = check_external_service("http://example.com")
        
        assert result["status"] == "up"
        assert result["status_code"] == 405


def test_check_external_service_500_is_down():
    """Test that 500 Internal Server Error is considered 'down'."""
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        with patch('time.time', side_effect=[0.0, 0.05]):
            result = check_external_service("http://example.com")
        
        assert result["status"] == "down"
        assert result["status_code"] == 500


# =============================================================================
# Glances Server Tests
# =============================================================================

def test_get_glances_server_stats_returns_dict():
    """Test Glances server stats returns a dict."""
    with patch('httpx.Client') as mock_client:
        # Mock successful responses
        mock_context = mock_client.return_value.__enter__.return_value
        
        status_resp = Mock()
        status_resp.status_code = 200
        
        cpu_resp = Mock()
        cpu_resp.json.return_value = {"total": 25.5}
        
        mem_resp = Mock()
        mem_resp.json.return_value = {
            "percent": 45.2,
            "used": 8 * 1024**3,  # 8 GB in bytes
            "total": 16 * 1024**3  # 16 GB in bytes
        }
        
        load_resp = Mock()
        load_resp.json.return_value = {"min1": 1.5}
        
        mock_context.get.side_effect = [status_resp, cpu_resp, mem_resp, load_resp]
        
        result = get_glances_server_stats("http://192.168.1.16:61208")
        assert isinstance(result, dict)
        assert result is not None


def test_get_glances_server_stats_structure():
    """Test Glances server stats has correct structure."""
    with patch('httpx.Client') as mock_client:
        mock_context = mock_client.return_value.__enter__.return_value
        
        status_resp = Mock()
        status_resp.status_code = 200
        
        cpu_resp = Mock()
        cpu_resp.json.return_value = {"total": 25.5}
        
        mem_resp = Mock()
        mem_resp.json.return_value = {
            "percent": 45.2,
            "used": 8 * 1024**3,
            "total": 16 * 1024**3
        }
        
        load_resp = Mock()
        load_resp.json.return_value = {"min1": 1.5}
        
        mock_context.get.side_effect = [status_resp, cpu_resp, mem_resp, load_resp]
        
        result = get_glances_server_stats("http://192.168.1.16:61208")
        
        assert "server_url" in result
        assert "status" in result
        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert "memory_used_gb" in result
        assert "memory_total_gb" in result
        assert "load_1min" in result
        assert "warnings" in result
        
        # Type checks
        assert isinstance(result["server_url"], str)
        assert isinstance(result["status"], str)
        assert isinstance(result["cpu_percent"], (int, float))
        assert isinstance(result["memory_percent"], (int, float))
        assert isinstance(result["memory_used_gb"], (int, float))
        assert isinstance(result["memory_total_gb"], (int, float))
        assert isinstance(result["load_1min"], (int, float))
        assert isinstance(result["warnings"], list)


def test_get_glances_server_stats_high_cpu_warning():
    """Test Glances detects high CPU usage."""
    with patch('httpx.Client') as mock_client:
        mock_context = mock_client.return_value.__enter__.return_value
        
        status_resp = Mock()
        status_resp.status_code = 200
        
        cpu_resp = Mock()
        cpu_resp.json.return_value = {"total": 85.0}  # High CPU
        
        mem_resp = Mock()
        mem_resp.json.return_value = {
            "percent": 45.2,
            "used": 8 * 1024**3,
            "total": 16 * 1024**3
        }
        
        load_resp = Mock()
        load_resp.json.return_value = {"min1": 1.5}
        
        mock_context.get.side_effect = [status_resp, cpu_resp, mem_resp, load_resp]
        
        result = get_glances_server_stats("http://192.168.1.16:61208")
        
        assert result["status"] == "warning"
        assert "high_cpu" in result["warnings"]


def test_get_glances_server_stats_unreachable():
    """Test Glances server unreachable."""
    with patch('httpx.Client') as mock_client:
        import httpx
        mock_context = mock_client.return_value.__enter__.return_value
        mock_context.get.side_effect = httpx.ConnectError("Connection failed")
        
        result = get_glances_server_stats("http://192.168.1.16:61208")
        
        assert "server_url" in result
        assert "status" in result
        assert "error" in result
        assert result["status"] == "unreachable"


# =============================================================================
# Homelab All Servers Tests
# =============================================================================

def test_get_all_homelab_servers_returns_dict():
    """Test all homelab servers returns a dict."""
    with patch('src.tools.sensors.get_glances_server_stats') as mock_stats:
        mock_stats.return_value = {
            "server_url": "http://192.168.1.16:61208",
            "status": "normal",
            "cpu_percent": 25.0,
            "memory_percent": 45.0,
            "memory_used_gb": 8.0,
            "memory_total_gb": 16.0,
            "load_1min": 1.5,
            "warnings": []
        }
        
        result = get_all_homelab_servers()
        assert isinstance(result, dict)
        assert result is not None


def test_get_all_homelab_servers_structure():
    """Test all homelab servers has correct structure."""
    with patch('src.tools.sensors.get_glances_server_stats') as mock_stats:
        mock_stats.return_value = {
            "server_url": "http://192.168.1.16:61208",
            "status": "normal",
            "cpu_percent": 25.0,
            "memory_percent": 45.0,
            "memory_used_gb": 8.0,
            "memory_total_gb": 16.0,
            "load_1min": 1.5,
            "warnings": []
        }
        
        result = get_all_homelab_servers()
        
        assert "overall_status" in result
        assert "total_servers" in result
        assert "total_warnings" in result
        assert "servers" in result
        
        # Type checks
        assert isinstance(result["overall_status"], str)
        assert isinstance(result["total_servers"], int)
        assert isinstance(result["total_warnings"], int)
        assert isinstance(result["servers"], list)
        
        # Value checks
        assert result["total_servers"] == 3  # Portainer, TrueNAS, Friday
        assert len(result["servers"]) == 3
        
        # Check each server has server_name added
        for server in result["servers"]:
            assert "server_name" in server
            assert isinstance(server["server_name"], str)


def test_get_all_homelab_servers_degraded_status():
    """Test all homelab servers detects degraded status."""
    with patch('src.tools.sensors.get_glances_server_stats') as mock_stats:
        # First two servers normal, third unreachable
        mock_stats.side_effect = [
            {
                "server_url": "http://192.168.1.16:61208",
                "status": "normal",
                "cpu_percent": 25.0,
                "memory_percent": 45.0,
                "memory_used_gb": 8.0,
                "memory_total_gb": 16.0,
                "load_1min": 1.5,
                "warnings": []
            },
            {
                "server_url": "http://192.168.1.17:61208",
                "status": "normal",
                "cpu_percent": 30.0,
                "memory_percent": 50.0,
                "memory_used_gb": 4.0,
                "memory_total_gb": 8.0,
                "load_1min": 0.8,
                "warnings": []
            },
            {
                "server_url": "http://192.168.1.18:61208",
                "status": "unreachable",
                "error": "Cannot connect"
            }
        ]
        
        result = get_all_homelab_servers()
        
        assert result["overall_status"] == "degraded"


# =============================================================================
# External Services Tests
# =============================================================================

def test_get_all_external_services_returns_dict():
    """Test all external services returns a dict."""
    with patch('src.tools.sensors.EXTERNAL_SERVICES', [
        {"name": "Test Service", "url": "http://example.com", "timeout": 5}
    ]):
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            with patch('time.time', side_effect=[0.0, 0.1]):
                result = get_all_external_services()
            
            assert isinstance(result, dict)
            assert result is not None


def test_get_all_external_services_structure():
    """Test all external services has correct structure."""
    with patch('src.tools.sensors.EXTERNAL_SERVICES', [
        {"name": "Test Service 1", "url": "http://example1.com", "timeout": 5},
        {"name": "Test Service 2", "url": "http://example2.com", "timeout": 5}
    ]):
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            with patch('time.time', side_effect=[0.0, 0.1, 0.2, 0.25]):
                result = get_all_external_services()
            
            assert "overall_status" in result
            assert "total_services" in result
            assert "up_count" in result
            assert "down_count" in result
            assert "degraded_count" in result
            assert "services" in result
            
            # Type checks
            assert isinstance(result["overall_status"], str)
            assert isinstance(result["total_services"], int)
            assert isinstance(result["up_count"], int)
            assert isinstance(result["down_count"], int)
            assert isinstance(result["degraded_count"], int)
            assert isinstance(result["services"], list)
            
            # Value checks
            assert result["total_services"] == 2
            assert result["up_count"] == 2
            assert result["down_count"] == 0


def test_get_all_external_services_no_config():
    """Test all external services with no configuration."""
    with patch('src.tools.sensors.EXTERNAL_SERVICES', []):
        result = get_all_external_services()
        assert "error" in result


def test_get_all_external_services_mixed_status():
    """Test all external services with mixed up/down status."""
    with patch('src.tools.sensors.EXTERNAL_SERVICES', [
        {"name": "Up Service", "url": "http://up.example.com", "timeout": 5},
        {"name": "Down Service", "url": "http://down.example.com", "timeout": 5}
    ]):
        with patch('httpx.Client') as mock_client:
            mock_context = mock_client.return_value.__enter__.return_value
            
            # First call succeeds, second fails
            import httpx
            up_response = Mock()
            up_response.status_code = 200
            
            mock_context.get.side_effect = [
                up_response,
                httpx.ConnectError("Connection failed")
            ]
            
            with patch('time.time', side_effect=[0.0, 0.1]):
                result = get_all_external_services()
            
            assert result["total_services"] == 2
            assert result["up_count"] == 1
            assert result["down_count"] == 1
            assert result["overall_status"] == "degraded"


# =============================================================================
# Homelab Report Tests
# =============================================================================

def test_report_homelab_status_returns_str():
    """Test homelab status report returns a string."""
    with patch('src.tools.sensors.get_all_homelab_servers') as mock_servers, \
         patch('src.tools.sensors.get_all_external_services') as mock_services:
        
        mock_servers.return_value = {
            "overall_status": "normal",
            "total_servers": 1,
            "total_warnings": 0,
            "servers": [{
                "server_name": "Test Server",
                "status": "normal",
                "cpu_percent": 25.0,
                "memory_percent": 45.0,
                "memory_used_gb": 8.0,
                "memory_total_gb": 16.0,
                "load_1min": 1.5,
                "warnings": []
            }]
        }
        
        mock_services.return_value = {
            "overall_status": "normal",
            "total_services": 1,
            "up_count": 1,
            "down_count": 0,
            "degraded_count": 0,
            "services": [{
                "name": "Test Service",
                "url": "http://example.com",
                "status": "up",
                "status_code": 200,
                "response_time_ms": 100
            }]
        }
        
        result = report_homelab_status()
        assert isinstance(result, str)
        assert result is not None
        assert len(result) > 0


def test_report_homelab_status_contains_sections():
    """Test homelab status report contains expected sections."""
    with patch('src.tools.sensors.get_all_homelab_servers') as mock_servers, \
         patch('src.tools.sensors.get_all_external_services') as mock_services:
        
        mock_servers.return_value = {
            "overall_status": "normal",
            "total_servers": 1,
            "total_warnings": 0,
            "servers": [{
                "server_name": "Test Server",
                "status": "normal",
                "cpu_percent": 25.0,
                "memory_percent": 45.0,
                "memory_used_gb": 8.0,
                "memory_total_gb": 16.0,
                "load_1min": 1.5
            }]
        }
        
        mock_services.return_value = {
            "overall_status": "normal",
            "total_services": 1,
            "up_count": 1,
            "down_count": 0,
            "degraded_count": 0,
            "services": [{
                "name": "Test Service",
                "url": "http://example.com",
                "status": "up",
                "response_time_ms": 100
            }]
        }
        
        result = report_homelab_status()
        
        # Check for section headers
        assert "Homelab Status Report" in result
        assert "SERVER HARDWARE" in result
        assert "EXTERNAL SERVICES" in result
        assert "Test Server" in result
        assert "Test Service" in result


# =============================================================================
# None Value Detection Tests
# =============================================================================

def test_get_detailed_disk_usage_no_none_values():
    """CRITICAL: Ensure disk usage has no None values."""
    result = get_detailed_disk_usage("/")
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_detailed_disk_usage has None values at: {none_values}"


def test_get_detailed_memory_usage_no_none_values():
    """CRITICAL: Ensure memory usage has no None values."""
    result = get_detailed_memory_usage()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_detailed_memory_usage has None values at: {none_values}"


def test_get_cpu_load_no_none_values():
    """CRITICAL: Ensure CPU load has no None values."""
    result = get_cpu_load()
    
    if "error" not in result:
        none_values = check_for_none_values(result)
        assert len(none_values) == 0, \
            f"CRITICAL: get_cpu_load has None values at: {none_values}"


def test_check_external_service_no_none_values():
    """CRITICAL: Ensure external service check has no None values."""
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        with patch('time.time', side_effect=[0.0, 0.1]):
            result = check_external_service("http://example.com")
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: check_external_service has None values at: {none_values}"


def test_get_glances_server_stats_no_none_values():
    """CRITICAL: Ensure Glances server stats has no None values."""
    with patch('httpx.Client') as mock_client:
        mock_context = mock_client.return_value.__enter__.return_value
        
        status_resp = Mock()
        status_resp.status_code = 200
        
        cpu_resp = Mock()
        cpu_resp.json.return_value = {"total": 25.5}
        
        mem_resp = Mock()
        mem_resp.json.return_value = {
            "percent": 45.2,
            "used": 8 * 1024**3,
            "total": 16 * 1024**3
        }
        
        load_resp = Mock()
        load_resp.json.return_value = {"min1": 1.5}
        
        mock_context.get.side_effect = [status_resp, cpu_resp, mem_resp, load_resp]
        
        result = get_glances_server_stats("http://192.168.1.16:61208")
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: get_glances_server_stats has None values at: {none_values}"


def test_get_all_homelab_servers_no_none_values():
    """CRITICAL: Ensure all homelab servers has no None values."""
    with patch('src.tools.sensors.get_glances_server_stats') as mock_stats:
        mock_stats.return_value = {
            "server_url": "http://192.168.1.16:61208",
            "status": "normal",
            "cpu_percent": 25.0,
            "memory_percent": 45.0,
            "memory_used_gb": 8.0,
            "memory_total_gb": 16.0,
            "load_1min": 1.5,
            "warnings": []
        }
        
        result = get_all_homelab_servers()
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: get_all_homelab_servers has None values at: {none_values}"


def test_get_all_external_services_no_none_values():
    """CRITICAL: Ensure all external services has no None values."""
    with patch('src.tools.sensors.EXTERNAL_SERVICES', [
        {"name": "Test Service", "url": "http://example.com", "timeout": 5}
    ]):
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            with patch('time.time', side_effect=[0.0, 0.1]):
                result = get_all_external_services()
            
            if "error" not in result:
                none_values = check_for_none_values(result)
                assert len(none_values) == 0, \
                    f"CRITICAL: get_all_external_services has None values at: {none_values}"


def test_all_sensors_tools_no_none_values():
    """CRITICAL: Batch test - check all sensors tools for None values."""
    errors = []
    
    # Hardware sensors
    result = get_detailed_disk_usage("/")
    if "error" not in result:
        none_vals = check_for_none_values(result)
        if none_vals:
            errors.append(f"get_detailed_disk_usage: {none_vals}")
    
    result = get_detailed_memory_usage()
    if "error" not in result:
        none_vals = check_for_none_values(result)
        if none_vals:
            errors.append(f"get_detailed_memory_usage: {none_vals}")
    
    result = get_cpu_load()
    if "error" not in result:
        none_vals = check_for_none_values(result)
        if none_vals:
            errors.append(f"get_cpu_load: {none_vals}")
    
    # Service checks (mocked)
    with patch('httpx.Client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        with patch('time.time', side_effect=[0.0, 0.1]):
            result = check_external_service("http://example.com")
        
        if "error" not in result:
            none_vals = check_for_none_values(result)
            if none_vals:
                errors.append(f"check_external_service: {none_vals}")
    
    # Assert no errors found
    assert len(errors) == 0, \
        f"CRITICAL: Found None values in sensors tools:\n" + "\n".join(errors)
