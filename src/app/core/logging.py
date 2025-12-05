"""Logging configuration."""
import logging
import os
import sys
from pathlib import Path


# Singleton logger instance
_logger = None
_initialized = False


def _get_log_path() -> Path:
    """Get the log file path from environment or default."""
    # Use environment variable to avoid circular import with config
    root = os.getenv("FRIDAY_ROOT", "/home/artur/friday")
    logs_path = os.getenv("FRIDAY_LOGS_PATH", f"{root}/logs")
    return Path(logs_path) / "friday.log"


def _get_log_level() -> int:
    """Get log level from environment or default."""
    level_str = os.getenv("FRIDAY_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_str, logging.INFO)


def get_logger() -> logging.Logger:
    """Get or create the singleton logger instance."""
    global _logger, _initialized
    
    if _logger is None:
        # Create the logger
        _logger = logging.getLogger("friday")
        _logger.setLevel(_get_log_level())
        _logger.propagate = False
    
    # Only initialize handlers once, even if get_logger is called multiple times
    if not _initialized:
        # Clear any existing handlers first (defensive)
        _logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)
        
        # File handler
        log_path = _get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
        
        _initialized = True
    
    return _logger


# Export the singleton logger
logger = get_logger()
