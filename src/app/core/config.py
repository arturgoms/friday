"""
Application configuration with layered loading.

Configuration precedence (highest to lowest):
1. Environment variables
2. config.yml values
3. Default values defined here

This allows for flexible configuration across different environments
while maintaining sensible defaults.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import timezone, timedelta
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file first (lowest priority, will be overridden by config.yml and env vars)
load_dotenv()

# Setup basic logging for config loading
logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Find the project root directory."""
    # Start from this file's location and go up
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "config.example.yml").exists() or (parent / "Pipfile").exists():
            return parent
    # Fallback to environment variable or default
    return Path(os.getenv("FRIDAY_ROOT", "/home/artur/friday"))


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file if it exists."""
    if not config_path.exists():
        logger.debug(f"Config file not found: {config_path}")
        return {}
    
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except ImportError:
        logger.warning("PyYAML not installed. Run: pip install pyyaml")
        return {}
    except Exception as e:
        logger.error(f"Error loading config file {config_path}: {e}")
        return {}


def _get_nested(d: Dict, *keys, default=None):
    """Safely get a nested dictionary value."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d if d is not None else default


def _env_or_yaml(env_key: str, yaml_config: Dict, *yaml_keys, default=None):
    """Get value from environment variable, falling back to YAML config, then default."""
    # Environment variable has highest priority
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value
    
    # Then YAML config
    yaml_value = _get_nested(yaml_config, *yaml_keys)
    if yaml_value is not None:
        return yaml_value
    
    # Finally, default
    return default


# Find project root and load YAML config
PROJECT_ROOT = _find_project_root()
YAML_CONFIG = _load_yaml_config(PROJECT_ROOT / "config.yml")

# Resolve base paths from config
_paths_root = _env_or_yaml("FRIDAY_ROOT", YAML_CONFIG, "paths", "root", default=str(PROJECT_ROOT))
_paths_brain = _env_or_yaml("BRAIN_PATH", YAML_CONFIG, "paths", "brain", default=f"{_paths_root}/brain")
_paths_data = _env_or_yaml("FRIDAY_DATA_PATH", YAML_CONFIG, "paths", "data", default=f"{_paths_root}/data")
_paths_logs = _env_or_yaml("FRIDAY_LOGS_PATH", YAML_CONFIG, "paths", "logs", default=f"{_paths_root}/logs")
_paths_config = _env_or_yaml("FRIDAY_CONFIG_PATH", YAML_CONFIG, "paths", "config", default=f"{_paths_root}/config")


class PathsConfig(BaseModel):
    """Path configuration."""
    root: Path = Path(_paths_root)
    brain: Path = Path(_paths_brain)
    data: Path = Path(_paths_data)
    logs: Path = Path(_paths_logs)
    config: Path = Path(_paths_config)


class BrainStructureConfig(BaseModel):
    """Brain folder structure configuration."""
    vault: str = _get_nested(YAML_CONFIG, "brain_structure", "vault", default="1. Notes")
    friday_root: str = _get_nested(YAML_CONFIG, "brain_structure", "friday_root", default="5. Friday")
    about: str = _get_nested(YAML_CONFIG, "brain_structure", "about", default="5. Friday/5.0 About")
    memories: str = _get_nested(YAML_CONFIG, "brain_structure", "memories", default="5. Friday/5.1 Memories")
    journal: str = _get_nested(YAML_CONFIG, "brain_structure", "journal", default="5. Friday/5.2 Journal")
    reports: str = _get_nested(YAML_CONFIG, "brain_structure", "reports", default="5. Friday/5.3 Reports")
    reminders: str = _get_nested(YAML_CONFIG, "brain_structure", "reminders", default="5. Friday/5.4 Reminders")
    conversations: str = _get_nested(YAML_CONFIG, "brain_structure", "conversations", default="5. Friday/5.5 Conversations")
    learnings: str = _get_nested(YAML_CONFIG, "brain_structure", "learnings", default="5. Friday/5.6 Learnings")


class UserConfig(BaseModel):
    """User-specific configuration."""
    name: str = _env_or_yaml("FRIDAY_USER_NAME", YAML_CONFIG, "user", "name", default="Artur")
    profile_file: str = _get_nested(YAML_CONFIG, "user", "profile_file", default="Artur Gomes.md")
    timezone_offset_hours: int = int(_env_or_yaml(
        "FRIDAY_TIMEZONE_OFFSET", YAML_CONFIG, "user", "timezone_offset_hours", default=-3
    ))
    authorized_user: str = _env_or_yaml("FRIDAY_AUTHORIZED_USER", YAML_CONFIG, "user", "authorized_user", default="artur")
    
    @property
    def timezone(self):
        """Get user's timezone as a timezone object."""
        return timezone(timedelta(hours=self.timezone_offset_hours))


class LLMConfig(BaseModel):
    """LLM configuration."""
    base_url: str = _env_or_yaml("LLM_BASE_URL", YAML_CONFIG, "llm", "base_url", default="http://localhost:8000/v1")
    model_name: str = _env_or_yaml("LLM_MODEL_NAME", YAML_CONFIG, "llm", "model_name", default="Qwen/Qwen2.5-14B-Instruct")
    temperature: float = float(_env_or_yaml("LLM_TEMPERATURE", YAML_CONFIG, "llm", "temperature", default=0.3))


class EmbeddingsConfig(BaseModel):
    """Embeddings configuration."""
    model_name: str = _get_nested(YAML_CONFIG, "embeddings", "model_name", default="sentence-transformers/all-MiniLM-L6-v2")
    device: str = _get_nested(YAML_CONFIG, "embeddings", "device", default="cpu")


class RAGConfig(BaseModel):
    """RAG configuration."""
    top_k_obsidian: int = int(_get_nested(YAML_CONFIG, "rag", "top_k_obsidian", default=5))
    neighbor_range: int = int(_get_nested(YAML_CONFIG, "rag", "neighbor_range", default=1))
    top_k_web: int = int(_get_nested(YAML_CONFIG, "rag", "top_k_web", default=4))
    top_k_memory: int = int(_get_nested(YAML_CONFIG, "rag", "top_k_memory", default=5))
    max_conversation_history: int = int(_get_nested(YAML_CONFIG, "rag", "max_conversation_history", default=10))
    chunk_max_chars: int = int(_get_nested(YAML_CONFIG, "rag", "chunk_max_chars", default=2000))
    chunk_overlap: int = int(_get_nested(YAML_CONFIG, "rag", "chunk_overlap", default=200))


class ServicesConfig(BaseModel):
    """External services configuration."""
    friday_api_url: str = _env_or_yaml("FRIDAY_API_URL", YAML_CONFIG, "services", "friday_api", "url", default="http://localhost:8080")
    searxng_url: str = _env_or_yaml("SEARXNG_URL", YAML_CONFIG, "services", "searxng", "url", default="http://localhost:8888")
    whisper_url: str = _env_or_yaml("WHISPER_SERVICE_URL", YAML_CONFIG, "services", "whisper", "url", default="")
    influxdb_config_file: str = _get_nested(YAML_CONFIG, "services", "influxdb", "config_file", default="influxdb_mcp.json")


class GoogleCalendarConfig(BaseModel):
    """Google Calendar configuration."""
    credentials_file: str = _get_nested(YAML_CONFIG, "google_calendar", "credentials_file", default="google_credentials.json")
    token_file: str = _get_nested(YAML_CONFIG, "google_calendar", "token_file", default="google_token.pickle")


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""
    bot_token: str = _env_or_yaml("TELEGRAM_BOT_TOKEN", YAML_CONFIG, "telegram", "bot_token", default="")
    user_id: str = _env_or_yaml("TELEGRAM_USER_ID", YAML_CONFIG, "telegram", "user_id", default="")


class AwarenessConfig(BaseModel):
    """Proactive monitoring (Awareness Engine) configuration."""
    daily_message_limit: int = int(_get_nested(YAML_CONFIG, "awareness", "daily_message_limit", default=5))
    urgent_exempt: bool = _get_nested(YAML_CONFIG, "awareness", "urgent_exempt", default=True)
    alert_cooldown_minutes: int = int(_get_nested(YAML_CONFIG, "awareness", "alert_cooldown_minutes", default=30))


class WeatherConfig(BaseModel):
    """Weather integration configuration."""
    api_key: str = _env_or_yaml("WEATHER_API_KEY", YAML_CONFIG, "weather", "api_key", default="")
    city: str = _env_or_yaml("WEATHER_CITY", YAML_CONFIG, "weather", "city", default="São Paulo")


class AuthConfig(BaseModel):
    """Authentication configuration."""
    api_key: Optional[str] = _env_or_yaml("FRIDAY_API_KEY", YAML_CONFIG, "auth", "api_key", default=None)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = _env_or_yaml("FRIDAY_LOG_LEVEL", YAML_CONFIG, "logging", "level", default="INFO")
    format: str = _get_nested(YAML_CONFIG, "logging", "format", default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class FeaturesConfig(BaseModel):
    """Feature flags."""
    web_search: bool = _get_nested(YAML_CONFIG, "features", "web_search", default=True)
    health_monitoring: bool = _get_nested(YAML_CONFIG, "features", "health_monitoring", default=True)
    calendar_integration: bool = _get_nested(YAML_CONFIG, "features", "calendar_integration", default=True)
    proactive_alerts: bool = _get_nested(YAML_CONFIG, "features", "proactive_alerts", default=True)
    voice_transcription: bool = _get_nested(YAML_CONFIG, "features", "voice_transcription", default=False)
    learning_system: bool = _get_nested(YAML_CONFIG, "features", "learning_system", default=True)


class Settings(BaseModel):
    """
    Application settings with layered configuration.
    
    Configuration is loaded from (in order of precedence):
    1. Environment variables
    2. config.yml
    3. Default values
    """
    
    # Sub-configurations
    paths: PathsConfig = Field(default_factory=PathsConfig)
    brain_structure: BrainStructureConfig = Field(default_factory=BrainStructureConfig)
    user: UserConfig = Field(default_factory=UserConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    google_calendar: GoogleCalendarConfig = Field(default_factory=GoogleCalendarConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    awareness: AwarenessConfig = Field(default_factory=AwarenessConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    
    class Config:
        arbitrary_types_allowed = True
    
    # =========================================================================
    # Backward Compatibility Properties
    # =========================================================================
    # These properties maintain compatibility with the existing codebase
    # while we migrate to the new configuration structure.
    # =========================================================================
    
    @property
    def brain_path(self) -> Path:
        """Brain folder path (backward compat)."""
        return self.paths.brain
    
    @property
    def vault_path(self) -> Path:
        """Vault path for RAG (backward compat)."""
        return self.paths.brain / self.brain_structure.vault
    
    @property
    def friday_path(self) -> Path:
        """Friday's data folder (backward compat)."""
        return self.paths.brain / self.brain_structure.friday_root
    
    @property
    def about_path(self) -> Path:
        """About folder path (backward compat)."""
        return self.paths.brain / self.brain_structure.about
    
    @property
    def memories_path(self) -> Path:
        """Memories folder path (backward compat)."""
        return self.paths.brain / self.brain_structure.memories
    
    @property
    def memory_path(self) -> Path:
        """Memory path alias (backward compat)."""
        return self.memories_path
    
    @property
    def journal_path(self) -> Path:
        """Journal folder path (backward compat)."""
        return self.paths.brain / self.brain_structure.journal
    
    @property
    def reports_path(self) -> Path:
        """Reports folder path (backward compat)."""
        return self.paths.brain / self.brain_structure.reports
    
    @property
    def reminders_path(self) -> Path:
        """Reminders folder path (backward compat)."""
        return self.paths.brain / self.brain_structure.reminders
    
    @property
    def conversations_path(self) -> Path:
        """Conversations folder path."""
        return self.paths.brain / self.brain_structure.conversations
    
    @property
    def learnings_path(self) -> Path:
        """Learnings folder path."""
        return self.paths.brain / self.brain_structure.learnings
    
    @property
    def chroma_path(self) -> Path:
        """ChromaDB path (backward compat)."""
        return self.paths.data / "chroma_db"
    
    @property
    def user_profile_file(self) -> str:
        """User profile file (backward compat)."""
        return self.user.profile_file
    
    @property
    def user_timezone(self):
        """User timezone (backward compat)."""
        return self.user.timezone
    
    @property
    def timezone_offset_hours(self) -> int:
        """Timezone offset (backward compat)."""
        return self.user.timezone_offset_hours
    
    @property
    def authorized_user(self) -> str:
        """Authorized user (backward compat)."""
        return self.user.authorized_user
    
    @property
    def embed_model_name(self) -> str:
        """Embedding model name (backward compat)."""
        return self.embeddings.model_name
    
    @property
    def embed_device(self) -> str:
        """Embedding device (backward compat)."""
        return self.embeddings.device
    
    @property
    def llm_base_url(self) -> str:
        """LLM base URL (backward compat)."""
        return self.llm.base_url
    
    @property
    def llm_model_name(self) -> str:
        """LLM model name (backward compat)."""
        return self.llm.model_name
    
    @property
    def llm_temperature(self) -> float:
        """LLM temperature (backward compat)."""
        return self.llm.temperature
    
    @property
    def api_key(self) -> Optional[str]:
        """API key (backward compat)."""
        return self.auth.api_key
    
    @property
    def top_k_obsidian(self) -> int:
        """RAG top_k for Obsidian (backward compat)."""
        return self.rag.top_k_obsidian
    
    @property
    def neighbor_range(self) -> int:
        """RAG neighbor range (backward compat)."""
        return self.rag.neighbor_range
    
    @property
    def top_k_web(self) -> int:
        """RAG top_k for web (backward compat)."""
        return self.rag.top_k_web
    
    @property
    def top_k_memory(self) -> int:
        """RAG top_k for memory (backward compat)."""
        return self.rag.top_k_memory
    
    @property
    def max_conversation_history(self) -> int:
        """Max conversation history (backward compat)."""
        return self.rag.max_conversation_history
    
    @property
    def chunk_max_chars(self) -> int:
        """Chunk max chars (backward compat)."""
        return self.rag.chunk_max_chars
    
    @property
    def chunk_overlap(self) -> int:
        """Chunk overlap (backward compat)."""
        return self.rag.chunk_overlap


# Create singleton instance
settings = Settings()


def get_config_source(key: str) -> str:
    """
    Get the source of a configuration value.
    
    Returns 'env', 'yaml', or 'default'.
    """
    # Check if environment variable exists
    env_key = key.upper().replace(".", "_")
    if os.getenv(env_key) is not None:
        return "env"
    
    # Check if value exists in YAML
    keys = key.split(".")
    yaml_value = _get_nested(YAML_CONFIG, *keys)
    if yaml_value is not None:
        return "yaml"
    
    return "default"


def reload_config():
    """Reload configuration from files."""
    global YAML_CONFIG, settings
    YAML_CONFIG = _load_yaml_config(PROJECT_ROOT / "config.yml")
    settings = Settings()
    logger.info("Configuration reloaded")
