"""
Tests for Friday 3.0 Sensors

Tests all sensors in src/sensors/hardware.py
"""

import pytest


class TestHardwareSensors:
    """Tests for hardware sensors."""
    
    def test_disk_usage_sensor(self):
        """Test disk_usage sensor returns valid data."""
        from src.sensors.hardware import check_disk_usage
        
        result = check_disk_usage()
        
        assert isinstance(result, dict)
        assert result["sensor"] == "disk_usage"
        
        if "error" not in result:
            assert "total_gb" in result
            assert "used_gb" in result
            assert "free_gb" in result
            assert "percent_used" in result
            assert result["total_gb"] > 0
            assert 0 <= result["percent_used"] <= 100
    
    def test_memory_usage_sensor(self):
        """Test memory_usage sensor returns valid data."""
        from src.sensors.hardware import check_memory_usage
        
        result = check_memory_usage()
        
        assert isinstance(result, dict)
        assert result["sensor"] == "memory_usage"
        
        if "error" not in result:
            assert "total_mb" in result
            assert "used_mb" in result
            assert "available_mb" in result
            assert "percent_used" in result
            assert result["total_mb"] > 0
            assert 0 <= result["percent_used"] <= 100
    
    def test_cpu_load_sensor(self):
        """Test cpu_load sensor returns valid data."""
        from src.sensors.hardware import check_cpu_load
        
        result = check_cpu_load()
        
        assert isinstance(result, dict)
        assert result["sensor"] == "cpu_load"
        
        if "error" not in result:
            assert "load_1min" in result
            assert "load_5min" in result
            assert "load_15min" in result
            assert result["load_1min"] >= 0
    
    def test_gpu_temperature_sensor(self):
        """Test gpu_temperature sensor (may fail if no GPU)."""
        from src.sensors.hardware import check_gpu_temperature
        
        result = check_gpu_temperature()
        
        assert isinstance(result, dict)
        assert result["sensor"] == "gpu_temperature"
        # This might have an error if no NVIDIA GPU
        assert "temperature_celsius" in result or "error" in result


class TestSensorRegistry:
    """Tests for sensor registry functionality."""
    
    def test_sensors_are_registered(self):
        """Test that sensors are properly registered."""
        from src.core.loader import load_extensions
        from src.core.registry import get_sensor_registry
        
        load_extensions()
        registry = get_sensor_registry()
        
        assert len(registry) >= 4
        assert "disk_usage" in registry
        assert "memory_usage" in registry
        assert "cpu_load" in registry
        assert "gpu_temperature" in registry
    
    def test_sensor_has_interval(self):
        """Test that sensors have interval configuration."""
        from src.core.loader import load_extensions
        from src.core.registry import get_sensor_registry
        
        load_extensions()
        registry = get_sensor_registry()
        
        for name, entry in registry.items():
            assert entry.name == name
            assert entry.interval_seconds > 0
            assert isinstance(entry.enabled, bool)
    
    def test_sensor_is_callable(self):
        """Test that registered sensors are callable."""
        from src.core.loader import load_extensions
        from src.core.registry import get_sensor_registry
        
        load_extensions()
        registry = get_sensor_registry()
        
        for name, entry in registry.items():
            assert callable(entry.func)
            # All sensors should work with no arguments
            result = entry.func()
            assert isinstance(result, dict)
            assert "sensor" in result
