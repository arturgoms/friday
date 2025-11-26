"""Logging configuration."""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup application logging."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/home/artur/friday/logs/friday.log')
        ]
    )
    return logging.getLogger("friday")


logger = setup_logging()
