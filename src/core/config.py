"""
Friday 3.0 Configuration Loader

Loads configuration from:
1. Environment variables (.env)
2. config.yml (YAML file)
3. Default values

Environment variables take precedence over YAML values.
"""

import os
from pathlib import Path
from typing import Optional, List

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


# Load .env file
load_dotenv()


# =============================================================================
# Pydantic Configuration Models
# =============================================================================

class SystemConfig(BaseModel):
    """System-level configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"


class LLMConfig(BaseModel):
    """LLM configuration."""
    model_name: str = "dphn/Dolphin3.0-Llama3.1-8B"
    base_url: str = "http://localhost:8000/v1"
    temperature: float = 0.3
    max_tokens: int = 4096


class EmbeddingsConfig(BaseModel):
    """Embeddings configuration."""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"


class MemoryConfig(BaseModel):
    """Memory and session configuration."""
    session_timeout_seconds: int = 3600
    chroma_path: str = "./data/chroma"
    rag_top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200


class PathsConfig(BaseModel):
    """Paths configuration."""
    root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    brain: Optional[Path] = None
    data: Optional[Path] = None
    logs: Optional[Path] = None

    def model_post_init(self, __context) -> None:
        """Set default paths relative to root."""
        if self.brain is None:
            self.brain = self.root / "brain"
        if self.data is None:
            self.data = self.root / "data"
        if self.logs is None:
            self.logs = self.root / "logs"


class UserConfig(BaseModel):
    """User configuration."""
    name: str = "User"
    profile_file: str = "User.md"
    timezone_offset_hours: int = 0


class RouterConfig(BaseModel):
    """Router configuration."""
    use_structured_chain: bool = True
    max_tool_retries: int = 3


class InterpreterConfig(BaseModel):
    """Code interpreter configuration."""
    require_confirmation: List[str] = Field(
        default_factory=lambda: ["os.remove", "shutil.rmtree", "subprocess"]
    )
    execution_timeout_sec: int = 30
    max_iterations: int = 5


class SensorsConfig(BaseModel):
    """Sensors configuration."""
    check_interval_default: int = 300
    disk_threshold_percent: int = 90
    gpu_temp_threshold: int = 80


class ServicesConfig(BaseModel):
    """Services ports configuration."""
    core_port: int = 8080
    vllm_port: int = 8000


class Config(BaseModel):
    """Main configuration container."""
    system: SystemConfig = Field(default_factory=SystemConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    user: UserConfig = Field(default_factory=UserConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    interpreter: InterpreterConfig = Field(default_factory=InterpreterConfig)
    sensors: SensorsConfig = Field(default_factory=SensorsConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)


# =============================================================================
# Configuration Loading
# =============================================================================

def find_config_file() -> Optional[Path]:
    """Find the config.yml file, searching up the directory tree."""
    # Start from the current file's directory
    current = Path(__file__).parent
    
    # Search up to 5 levels
    for _ in range(5):
        config_path = current / "config.yml"
        if config_path.exists():
            return config_path
        current = current.parent
    
    # Also check working directory
    cwd_config = Path.cwd() / "config.yml"
    if cwd_config.exists():
        return cwd_config
    
    return None


def load_yaml_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load config from {config_path}: {e}")
        return {}


def apply_env_overrides(config_dict: dict) -> dict:
    """Apply environment variable overrides to config dictionary.
    
    Environment variables are mapped using FRIDAY_ prefix and double underscores
    for nesting. For example:
    - FRIDAY_SYSTEM__PORT=9000 -> config['system']['port'] = 9000
    - FRIDAY_LLM__MODEL_NAME=... -> config['llm']['model_name'] = ...
    """
    prefix = "FRIDAY_"
    
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        
        # Remove prefix and split by double underscore
        config_key = key[len(prefix):].lower()
        parts = config_key.split("__")
        
        if len(parts) == 1:
            # Top-level key
            config_dict[parts[0]] = _parse_env_value(value)
        elif len(parts) == 2:
            # Nested key
            section, setting = parts
            if section not in config_dict:
                config_dict[section] = {}
            config_dict[section][setting] = _parse_env_value(value)
    
    return config_dict


def _parse_env_value(value: str):
    """Parse environment variable value to appropriate type."""
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    
    # Integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    
    # String
    return value


def load_config() -> Config:
    """Load configuration from YAML file and environment variables.
    
    Returns:
        Config: Validated configuration object
    """
    # Find and load YAML config
    config_path = find_config_file()
    if config_path:
        config_dict = load_yaml_config(config_path)
    else:
        config_dict = {}
    
    # Apply environment variable overrides
    config_dict = apply_env_overrides(config_dict)
    
    # Create and validate config object
    return Config(**config_dict)


# =============================================================================
# Global Configuration Instance
# =============================================================================

# Singleton config instance - loaded on first import
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.
    
    This function loads the configuration on first call and caches it.
    Use reload_config() to force a reload.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """Force reload of configuration from files.
    
    Returns:
        Config: Newly loaded configuration
    """
    global _config
    _config = load_config()
    return _config


# Convenience alias
config = get_config
