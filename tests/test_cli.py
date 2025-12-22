"""
Tests for Friday 3.0 CLI

Tests the CLI commands and utilities.
"""

import pytest
import subprocess
import sys


class TestCLIBasics:
    """Basic CLI tests."""
    
    def test_cli_help(self):
        """Test CLI help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        assert result.returncode == 0
        assert "Friday 3.0" in result.stdout
        assert "status" in result.stdout
        assert "chat" in result.stdout
    
    def test_cli_version(self):
        """Test CLI version command."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "version"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        assert result.returncode == 0
        assert "Friday 3.0" in result.stdout
    
    def test_cli_tools_list(self):
        """Test CLI tools command lists tools."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "tools"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        assert result.returncode == 0
        assert "get_current_time" in result.stdout
        assert "get_disk_usage" in result.stdout
    
    def test_cli_sensors_list(self):
        """Test CLI sensors command lists sensors."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "sensors"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        assert result.returncode == 0
        assert "disk_usage" in result.stdout
        assert "memory_usage" in result.stdout


class TestCLIConfig:
    """Tests for CLI config command."""
    
    def test_config_show(self):
        """Test config show command."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "config", "show"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        assert result.returncode == 0
        # Should show config file contents or parsed config


class TestCLIHelpers:
    """Tests for CLI helper functions."""
    
    def test_get_api_url_default(self):
        """Test get_api_url returns default."""
        import os
        # Clear env var if set
        old_val = os.environ.pop("FRIDAY_API_URL", None)
        
        try:
            from src.cli import get_api_url, DEFAULT_API_URL
            url = get_api_url()
            assert url == DEFAULT_API_URL
        finally:
            if old_val:
                os.environ["FRIDAY_API_URL"] = old_val
    
    def test_get_api_url_from_env(self):
        """Test get_api_url uses env var."""
        import os
        old_val = os.environ.get("FRIDAY_API_URL")
        os.environ["FRIDAY_API_URL"] = "http://test:9999"
        
        try:
            # Need to reload to pick up new env
            import importlib
            import src.cli
            importlib.reload(src.cli)
            
            url = src.cli.get_api_url()
            assert url == "http://test:9999"
        finally:
            if old_val:
                os.environ["FRIDAY_API_URL"] = old_val
            else:
                os.environ.pop("FRIDAY_API_URL", None)
    
    def test_get_api_headers_without_key(self):
        """Test headers without API key."""
        import os
        old_val = os.environ.pop("FRIDAY_API_KEY", None)
        
        try:
            from src.cli import get_api_headers
            headers = get_api_headers()
            
            assert "Content-Type" in headers
            assert "Authorization" not in headers
        finally:
            if old_val:
                os.environ["FRIDAY_API_KEY"] = old_val
    
    def test_get_api_headers_with_key(self):
        """Test headers with API key."""
        import os
        old_val = os.environ.get("FRIDAY_API_KEY")
        os.environ["FRIDAY_API_KEY"] = "test-key-123"
        
        try:
            import importlib
            import src.cli
            importlib.reload(src.cli)
            
            headers = src.cli.get_api_headers()
            
            assert "Authorization" in headers
            assert "Bearer test-key-123" in headers["Authorization"]
        finally:
            if old_val:
                os.environ["FRIDAY_API_KEY"] = old_val
            else:
                os.environ.pop("FRIDAY_API_KEY", None)


class TestCLIServiceCommands:
    """Tests for service management commands (requires systemd)."""
    
    @pytest.mark.skipif(
        subprocess.run(["systemctl", "--user", "--version"], capture_output=True).returncode != 0,
        reason="systemd user services not available"
    )
    def test_status_command(self):
        """Test status command runs."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "status"],
            capture_output=True,
            text=True,
            cwd="/home/artur/friday"
        )
        
        # Should at least show the table header
        assert "Service" in result.stdout or result.returncode == 0
