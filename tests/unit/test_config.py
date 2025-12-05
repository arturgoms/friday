"""
Unit tests for the configuration system.

Tests the layered configuration loading:
1. Default values
2. YAML config file overrides
3. Environment variable overrides
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestConfigHelpers:
    """Tests for configuration helper functions."""
    
    def test_get_nested_simple(self):
        """Test simple nested dictionary access."""
        from app.core.config import _get_nested
        
        d = {"a": {"b": {"c": "value"}}}
        assert _get_nested(d, "a", "b", "c") == "value"
    
    def test_get_nested_missing_key(self):
        """Test nested access with missing key."""
        from app.core.config import _get_nested
        
        d = {"a": {"b": "value"}}
        assert _get_nested(d, "a", "c", default="default") == "default"
    
    def test_get_nested_empty_dict(self):
        """Test nested access with empty dictionary."""
        from app.core.config import _get_nested
        
        assert _get_nested({}, "a", "b", default="default") == "default"
    
    def test_get_nested_none_value(self):
        """Test nested access returns default for None values."""
        from app.core.config import _get_nested
        
        d = {"a": {"b": None}}
        assert _get_nested(d, "a", "b", default="default") == "default"


class TestEnvOrYaml:
    """Tests for _env_or_yaml precedence function."""
    
    def test_env_var_takes_precedence(self):
        """Test that environment variables override YAML config."""
        from app.core.config import _env_or_yaml
        
        yaml_config = {"section": {"key": "yaml_value"}}
        
        with patch.dict(os.environ, {"TEST_KEY": "env_value"}):
            result = _env_or_yaml("TEST_KEY", yaml_config, "section", "key", default="default")
            assert result == "env_value"
    
    def test_yaml_takes_precedence_over_default(self):
        """Test that YAML config overrides defaults."""
        from app.core.config import _env_or_yaml
        
        yaml_config = {"section": {"key": "yaml_value"}}
        
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("TEST_KEY_YAML", None)
            result = _env_or_yaml("TEST_KEY_YAML", yaml_config, "section", "key", default="default")
            assert result == "yaml_value"
    
    def test_default_used_when_no_override(self):
        """Test that default is used when no env or YAML value exists."""
        from app.core.config import _env_or_yaml
        
        yaml_config = {}
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TEST_KEY_DEFAULT", None)
            result = _env_or_yaml("TEST_KEY_DEFAULT", yaml_config, "section", "key", default="default")
            assert result == "default"


class TestPathsConfig:
    """Tests for paths configuration."""
    
    def test_paths_have_defaults(self):
        """Test that all paths have sensible defaults."""
        from app.core.config import settings
        
        assert settings.paths.root is not None
        assert settings.paths.brain is not None
        assert settings.paths.data is not None
        assert settings.paths.logs is not None
        assert settings.paths.config is not None
    
    def test_paths_are_path_objects(self):
        """Test that path values are Path objects."""
        from app.core.config import settings
        
        assert isinstance(settings.paths.root, Path)
        assert isinstance(settings.paths.brain, Path)
        assert isinstance(settings.paths.data, Path)


class TestBackwardCompatibility:
    """Tests for backward compatibility properties."""
    
    def test_brain_path_property(self):
        """Test brain_path backward compat property."""
        from app.core.config import settings
        
        assert settings.brain_path == settings.paths.brain
    
    def test_vault_path_property(self):
        """Test vault_path backward compat property."""
        from app.core.config import settings
        
        expected = settings.paths.brain / settings.brain_structure.vault
        assert settings.vault_path == expected
    
    def test_llm_properties(self):
        """Test LLM backward compat properties."""
        from app.core.config import settings
        
        assert settings.llm_base_url == settings.llm.base_url
        assert settings.llm_model_name == settings.llm.model_name
        assert settings.llm_temperature == settings.llm.temperature
    
    def test_rag_properties(self):
        """Test RAG backward compat properties."""
        from app.core.config import settings
        
        assert settings.top_k_obsidian == settings.rag.top_k_obsidian
        assert settings.top_k_memory == settings.rag.top_k_memory
        assert settings.chunk_max_chars == settings.rag.chunk_max_chars
    
    def test_user_timezone_property(self):
        """Test user_timezone backward compat property."""
        from app.core.config import settings
        from datetime import timezone, timedelta
        
        expected = timezone(timedelta(hours=settings.user.timezone_offset_hours))
        assert settings.user_timezone == expected


class TestUserConfig:
    """Tests for user configuration."""
    
    def test_user_has_name(self):
        """Test that user name is configured."""
        from app.core.config import settings
        
        assert settings.user.name is not None
        assert len(settings.user.name) > 0
    
    def test_user_timezone(self):
        """Test that user timezone is configured."""
        from app.core.config import settings
        
        # Timezone offset should be an integer
        assert isinstance(settings.user.timezone_offset_hours, int)
        # Should be within reasonable bounds
        assert -12 <= settings.user.timezone_offset_hours <= 14


class TestLLMConfig:
    """Tests for LLM configuration."""
    
    def test_llm_has_base_url(self):
        """Test that LLM base URL is configured."""
        from app.core.config import settings
        
        assert settings.llm.base_url is not None
        assert settings.llm.base_url.startswith("http")
    
    def test_llm_has_model_name(self):
        """Test that LLM model name is configured."""
        from app.core.config import settings
        
        assert settings.llm.model_name is not None
        assert len(settings.llm.model_name) > 0
    
    def test_llm_temperature_in_range(self):
        """Test that LLM temperature is in valid range."""
        from app.core.config import settings
        
        assert 0.0 <= settings.llm.temperature <= 2.0


class TestFeaturesConfig:
    """Tests for feature flags."""
    
    def test_features_are_booleans(self):
        """Test that feature flags are boolean values."""
        from app.core.config import settings
        
        assert isinstance(settings.features.web_search, bool)
        assert isinstance(settings.features.health_monitoring, bool)
        assert isinstance(settings.features.calendar_integration, bool)
        assert isinstance(settings.features.proactive_alerts, bool)
        assert isinstance(settings.features.voice_transcription, bool)
        assert isinstance(settings.features.learning_system, bool)


class TestConfigSource:
    """Tests for get_config_source function."""
    
    def test_get_config_source_env(self):
        """Test detecting env var source."""
        from app.core.config import get_config_source
        
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://test"}):
            # This might return 'env' or 'yaml' depending on existing config
            source = get_config_source("llm.base_url")
            assert source in ["env", "yaml", "default"]
    
    def test_get_config_source_default(self):
        """Test detecting default source for unknown key."""
        from app.core.config import get_config_source
        
        source = get_config_source("nonexistent.key.path")
        assert source == "default"


class TestYAMLLoading:
    """Tests for YAML configuration loading."""
    
    def test_load_yaml_missing_file(self, tmp_path):
        """Test that missing YAML file returns empty dict."""
        from app.core.config import _load_yaml_config
        
        result = _load_yaml_config(tmp_path / "nonexistent.yml")
        assert result == {}
    
    def test_load_yaml_valid_file(self, tmp_path):
        """Test loading valid YAML file."""
        from app.core.config import _load_yaml_config
        
        config_file = tmp_path / "test_config.yml"
        config_file.write_text("""
paths:
  root: /test/path
llm:
  model_name: test-model
""")
        
        result = _load_yaml_config(config_file)
        assert result["paths"]["root"] == "/test/path"
        assert result["llm"]["model_name"] == "test-model"
    
    def test_load_yaml_empty_file(self, tmp_path):
        """Test loading empty YAML file returns empty dict."""
        from app.core.config import _load_yaml_config
        
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")
        
        result = _load_yaml_config(config_file)
        assert result == {}


@pytest.mark.integration
class TestConfigIntegration:
    """Integration tests for complete config loading."""
    
    def test_settings_singleton_exists(self):
        """Test that settings singleton is created."""
        from app.core.config import settings
        
        assert settings is not None
    
    def test_all_subconfigs_exist(self):
        """Test that all sub-configurations are initialized."""
        from app.core.config import settings
        
        assert settings.paths is not None
        assert settings.brain_structure is not None
        assert settings.user is not None
        assert settings.llm is not None
        assert settings.embeddings is not None
        assert settings.rag is not None
        assert settings.services is not None
        assert settings.google_calendar is not None
        assert settings.telegram is not None
        assert settings.awareness is not None
        assert settings.weather is not None
        assert settings.auth is not None
        assert settings.logging is not None
        assert settings.features is not None
