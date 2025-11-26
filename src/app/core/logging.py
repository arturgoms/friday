"""Logging configuration."""
import logging
import sys


# Singleton logger instance
_logger = None
_initialized = False


def get_logger() -> logging.Logger:
    """Get or create the singleton logger instance."""
    global _logger, _initialized
    
    if _logger is None:
        # Create the logger
        _logger = logging.getLogger("friday")
        _logger.setLevel(logging.INFO)
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
        file_handler = logging.FileHandler('/home/artur/friday/logs/friday.log')
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
        
        _initialized = True
    
    return _logger


# Export the singleton logger
logger = get_logger()
