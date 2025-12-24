"""
Friday Insights Engine - Base Collector

Abstract base class for all collectors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for data collectors.
    
    Collectors are responsible for gathering data from various sources
    (InfluxDB, APIs, system stats, etc.) and returning it in a
    standardized format for storage and analysis.
    """
    
    def __init__(self, name: str):
        """Initialize collector.
        
        Args:
            name: Unique name for this collector (e.g., "health", "calendar")
        """
        self.name = name
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the collector (connect to APIs, etc.).
        
        Override this method to perform one-time setup.
        
        Returns:
            True if initialization successful
        """
        self._initialized = True
        return True
    
    @abstractmethod
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect data from the source.
        
        Returns:
            Dictionary of collected data, or None if collection failed.
            The data structure depends on the collector type.
        """
        pass
    
    def is_available(self) -> bool:
        """Check if the data source is available.
        
        Override to implement health checks.
        
        Returns:
            True if source is available and can be collected from
        """
        return self._initialized
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
