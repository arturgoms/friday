"""
Tests for Friday 3.0 Tools

Tests all tools in src/tools/system.py
"""

import pytest
from datetime import datetime


class TestSystemTools:
    """Tests for system tools."""
    
    def test_get_current_time(self):
        """Test get_current_time returns valid datetime string."""
        from src.tools.system import get_current_time
        
        result = get_current_time()
        
        assert isinstance(result, str)
        # Should be parseable as datetime
        parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        assert parsed is not None
    
    def test_get_disk_usage_default(self):
        """Test get_disk_usage with default path."""
        from src.tools.system import get_disk_usage
        
        result = get_disk_usage()
        
        assert isinstance(result, str)
        assert "Total:" in result
        assert "Used:" in result
        assert "Free:" in result
        assert "GB" in result
    
    def test_get_disk_usage_custom_path(self):
        """Test get_disk_usage with custom path."""
        from src.tools.system import get_disk_usage
        
        result = get_disk_usage(path="/tmp")
        
        assert isinstance(result, str)
        assert "Total:" in result or "Error" in result
    
    def test_get_disk_usage_invalid_path(self):
        """Test get_disk_usage with invalid path."""
        from src.tools.system import get_disk_usage
        
        result = get_disk_usage(path="/nonexistent/path")
        
        assert isinstance(result, str)
        assert "Error" in result
    
    def test_get_system_info(self):
        """Test get_system_info returns system details."""
        from src.tools.system import get_system_info
        
        result = get_system_info()
        
        assert isinstance(result, str)
        assert "System:" in result
        assert "Release:" in result
        assert "Machine:" in result
        # Hostname may be shown as "Hostname:" not "Node:"
        assert "Hostname:" in result or "Node:" in result
    
    def test_get_uptime(self):
        """Test get_uptime returns uptime info."""
        from src.tools.system import get_uptime
        
        result = get_uptime()
        
        assert isinstance(result, str)
        # Should contain time units
        assert any(unit in result.lower() for unit in ["day", "hour", "minute", "second"])
    
    def test_get_memory_usage(self):
        """Test get_memory_usage returns memory info."""
        from src.tools.system import get_memory_usage
        
        result = get_memory_usage()
        
        assert isinstance(result, str)
        assert "Total:" in result
        assert "Used:" in result
        assert "Available:" in result


class TestToolRegistry:
    """Tests for tool registry functionality."""
    
    def test_tools_are_registered(self):
        """Test that tools are properly registered."""
        from src.core.loader import load_extensions
        from src.core.registry import get_tool_registry
        
        load_extensions()
        registry = get_tool_registry()
        
        assert len(registry) >= 5
        assert "get_current_time" in registry
        assert "get_disk_usage" in registry
        assert "get_system_info" in registry
        assert "get_uptime" in registry
        assert "get_memory_usage" in registry
    
    def test_tool_has_schema(self):
        """Test that registered tools have proper schemas."""
        from src.core.loader import load_extensions
        from src.core.registry import get_tool_registry
        
        load_extensions()
        registry = get_tool_registry()
        
        for name, entry in registry.items():
            assert entry.name == name
            assert entry.description is not None
            assert entry.schema is not None
            assert "type" in entry.schema
            assert entry.schema["type"] == "function"
    
    def test_tool_is_callable(self):
        """Test that registered tools are callable."""
        from src.core.loader import load_extensions
        from src.core.registry import get_tool_registry
        
        load_extensions()
        registry = get_tool_registry()
        
        for name, entry in registry.items():
            assert callable(entry.func)
            # Try calling with no args (should work for most tools)
            try:
                result = entry.func()
                assert result is not None
            except TypeError:
                # Some tools might require arguments, that's OK
                pass
