"""
Configuration management for Friday.

Loads settings from:
1. config.yml (main configuration)
2. .env (secrets and overrides)
3. Environment variables (FRIDAY_* prefix)
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import pytz
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class SystemConfig(BaseModel):
    """System configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"


class LLMConfig(BaseModel):
    """LLM configuration."""
    model_name: str = "NousResearch/Hermes-4-14B"
    base_url: str = "http://localhost:8000/v1"
    temperature: float = 0.6
    max_tokens: int = 2048


class PathsConfig(BaseModel):
    """Paths configuration."""
    root: Path
    brain: Path
    data: Path
    logs: Path


class UserConfig(BaseModel):
    """User configuration."""
    name: str = "Artur"
    profile_file: str = "Artur Gomes.md"
    timezone_offset_hours: int = -3
    timezone: str = "America/Sao_Paulo"


class Config(BaseModel):
    """Main Friday configuration."""
    system: SystemConfig = Field(default_factory=SystemConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    paths: PathsConfig
    user: UserConfig = Field(default_factory=UserConfig)
    
    def get_timezone(self):
        """Get timezone object."""
        return pytz.timezone(self.user.timezone)


# Global config instance
_config: Optional[Config] = None


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file and environment.
    
    Args:
        config_path: Path to config.yml (defaults to project root)
        
    Returns:
        Config instance
    """
    global _config
    
    # Load .env first
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    # Load config.yml
    if config_path is None:
        config_path = project_root / "config.yml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    # Apply environment variable overrides
    # Example: FRIDAY_LLM__MODEL_NAME -> config_data['llm']['model_name']
    for key, value in os.environ.items():
        if key.startswith("FRIDAY_"):
            parts = key[7:].lower().split("__")
            if len(parts) == 2:
                section, field = parts
                if section in config_data:
                    config_data[section][field] = value
    
    _config = Config(**config_data)
    return _config


def get_config() -> Config:
    """Get the global config instance.
    
    Returns:
        Config instance
        
    Raises:
        RuntimeError: If config not loaded
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


# Backwards compatibility - cached BRT timezone
_brt_cache = None

def get_brt():
    """Get BRT timezone (backwards compatibility helper).
    
    Returns:
        pytz timezone object for America/Sao_Paulo
    """
    global _brt_cache
    if _brt_cache is None:
        config = get_config()
        _brt_cache = config.get_timezone()
    return _brt_cache


# Alias for backwards compatibility
# Usage: from src.core.config import BRT
BRT = None  # Will be set on module load

def _init_module():
    """Initialize module-level variables."""
    global BRT
    BRT = get_brt()

# Initialize on import
try:
    _init_module()
except:
    # Config not loaded yet, will be initialized later
    pass
