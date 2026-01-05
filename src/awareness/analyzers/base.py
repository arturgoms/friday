"""
Friday Insights Engine - Base Analyzer

Abstract base class for all analyzers.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import time

from src.awareness.models import Insight, AnalyzerResult
from settings import settings
from src.awareness.store import InsightsStore

from settings import settings
def get_brt():
    return settings.TIMEZONE

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """
    Abstract base class for insight analyzers.
    
    Analyzers process collected data to generate insights. They can be:
    - Real-time: Run on every collection cycle (thresholds, stress)
    - Periodic: Run hourly/daily (correlations, trends)
    - Scheduled: Run at specific times (weekly digest)
    """
    
    def __init__(self, name: str, config: dict, store: InsightsStore):
        """Initialize analyzer.
        
        Args:
            name: Unique name for this analyzer
            config: Insights configuration
            store: Data store for snapshots and insights
        """
        self.name = name
        self.config = config
        self.store = store
        self._last_run: Optional[datetime] = None
    
    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Analyze data and generate insights.
        
        Args:
            data: Current collected data from collectors
            
        Returns:
            List of insights generated (may be empty)
        """
        pass
    
    def run(self, data: Dict[str, Any]) -> AnalyzerResult:
        """Run the analyzer and return results with timing.
        
        This method wraps analyze() with timing and error handling.
        
        Args:
            data: Current collected data from collectors
            
        Returns:
            AnalyzerResult with insights and metadata
        """
        start = time.time()
        result = AnalyzerResult(analyzer_name=self.name)
        
        try:
            insights = self.analyze(data)
            result.insights = insights
            
            # Set source analyzer on all insights
            for insight in result.insights:
                insight.source_analyzer = self.name
                
        except Exception as e:
            logger.error(f"Analyzer {self.name} failed: {e}", exc_info=True)
            result.error = str(e)
        
        result.duration_ms = (time.time() - start) * 1000
        result.run_at = datetime.now(get_brt())
        self._last_run = result.run_at
        
        if result.insights:
            logger.info(f"Analyzer {self.name} generated {len(result.insights)} insights")
        
        return result
    
    def is_enabled(self) -> bool:
        """Check if this analyzer is enabled in config."""
        analyzers = self.config.get("analyzers", {})
        analyzer_config = analyzers.get(self.name, {})
        return analyzer_config.get("enabled", True)
    
    def get_recent_snapshots(
        self, 
        collector: str, 
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent snapshots from a collector.
        
        Args:
            collector: Collector name
            hours: How many hours back to look
            
        Returns:
            List of snapshot data dictionaries
        """
        snapshots = self.store.get_snapshots(collector, hours=hours)
        return [s.data for s in snapshots]
    
    def was_insight_delivered_recently(
        self, 
        dedupe_key: str, 
        hours: Optional[float] = None
    ) -> bool:
        """Check if a similar insight was delivered recently.
        
        Used for deduplication - avoid sending the same alert repeatedly.
        
        Args:
            dedupe_key: Key to check for (e.g., "stress_high", "disk_critical")
            hours: Cooldown period. Defaults to config cooldown_minutes / 60.
            
        Returns:
            True if insight with this key was delivered within cooldown period
        """
        if hours is None:
            decision_config = self.config.get("decision", {})
            cooldown_minutes = decision_config.get("cooldown_minutes", 60)
            hours = cooldown_minutes / 60
        
        # Use the store's check_duplicate method for efficiency
        hours_int = int(hours) if hours else 1
        return self.store.check_duplicate(dedupe_key, hours=hours_int)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class RealTimeAnalyzer(BaseAnalyzer):
    """
    Base class for real-time analyzers.
    
    Real-time analyzers run on every collection cycle and process
    the latest data to detect immediate issues.
    """
    pass


class PeriodicAnalyzer(BaseAnalyzer):
    """
    Base class for periodic analyzers.
    
    Periodic analyzers run on a schedule (hourly/daily) and typically
    analyze historical data for patterns and correlations.
    """
    
    def __init__(
        self, 
        name: str, 
        config: dict, 
        store: InsightsStore,
        interval_hours: int = 24
    ):
        """Initialize periodic analyzer.
        
        Args:
            name: Unique name for this analyzer
            config: Insights configuration
            store: Data store
            interval_hours: How often to run (default 24 = daily)
        """
        super().__init__(name, config, store)
        self.interval_hours = interval_hours
    
    def should_run(self) -> bool:
        """Check if enough time has passed since last run."""
        if self._last_run is None:
            return True
        
        hours_since = (datetime.now(get_brt()) - self._last_run).total_seconds() / 3600
        return hours_since >= self.interval_hours


class ScheduledAnalyzer(BaseAnalyzer):
    """
    Base class for scheduled analyzers.
    
    Scheduled analyzers run at specific times (e.g., Sunday 20:00 for
    weekly digest).
    """
    pass
