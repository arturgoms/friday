"""
Friday Insights Engine - Main Orchestrator

The InsightsEngine coordinates all components:
- Collectors: Gather data from various sources
- Analyzers: Process data and generate insights
- Decision Engine: Determine what to deliver and when
- Delivery Manager: Send insights via appropriate channels

Usage:
    python -m src.insights.engine
"""

import asyncio
import json
import logging
import signal
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.insights.config import InsightsConfig
from src.insights.models import Insight, Snapshot, BRT
from src.insights.store import InsightsStore
from src.insights.collectors import (
    HealthCollector, CalendarCollector, HomelabCollector, WeatherCollector
)
from src.insights.analyzers import (
    ThresholdAnalyzer, StressAnalyzer, CalendarAnalyzer,
    SleepCorrelationAnalyzer, ResourceTrendAnalyzer
)
from src.insights.decision import DecisionEngine, BudgetManager
from src.insights.delivery import DeliveryManager

logger = logging.getLogger(__name__)


class InsightsEngine:
    """
    Main orchestrator for the Friday Insights system.
    
    Runs a continuous loop that:
    1. Collects data from various sources (on their intervals)
    2. Runs analyzers to generate insights
    3. Decides which insights to deliver
    4. Delivers via appropriate channels
    5. Sends scheduled reports (morning/evening/weekly)
    """
    
    def __init__(self, config: Optional[InsightsConfig] = None):
        """Initialize the insights engine.
        
        Args:
            config: Configuration. Loads from file if not provided.
        """
        self.config = config or InsightsConfig.load()
        self.store = InsightsStore()
        
        # Initialize collectors
        self._collectors = {
            "health": HealthCollector(),
            "calendar": CalendarCollector(),
            "homelab": HomelabCollector(),
            "weather": WeatherCollector(),
        }
        
        # Initialize collectors
        for name, collector in self._collectors.items():
            collector.initialize()
        
        # Initialize analyzers (they need config and store)
        # Real-time analyzers (run every cycle)
        self._analyzers = {
            "threshold": ThresholdAnalyzer(self.config, self.store),
            "stress_monitor": StressAnalyzer(self.config, self.store),
            "calendar_reminder": CalendarAnalyzer(self.config, self.store),
        }
        
        # Periodic analyzers (run on their own schedules)
        self._periodic_analyzers = {
            "sleep_correlation": SleepCorrelationAnalyzer(self.config, self.store),
            "resource_trend": ResourceTrendAnalyzer(self.config, self.store),
        }
        
        # Track last run times for periodic analyzers
        self._last_periodic_run: Dict[str, float] = {}
        
        # Initialize delivery
        self.delivery = DeliveryManager(self.config, self.store)
        
        # Timing tracking
        self._last_collection: Dict[str, float] = {}
        self._report_state_file = Path(__file__).parent.parent.parent / "data" / "schedule_state.json"
        self._report_state: Dict[str, str] = self._load_report_state()
        
        # Control
        self._running = False
        
        logger.info("[INSIGHTS] Engine initialized with %d collectors, %d analyzers", 
                     len(self._collectors), len(self._analyzers))
    
    def _load_report_state(self) -> Dict[str, str]:
        """Load report delivery state from file."""
        if self._report_state_file.exists():
            try:
                return json.loads(self._report_state_file.read_text())
            except Exception as e:
                logger.warning(f"Failed to load report state: {e}")
        return {}
    
    def _save_report_state(self):
        """Save report delivery state to file."""
        try:
            self._report_state_file.write_text(json.dumps(self._report_state, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save report state: {e}")
    
    async def run(self, check_interval: float = 10.0):
        """Run the insights engine main loop.
        
        Args:
            check_interval: How often to check for work (seconds)
        """
        self._running = True
        logger.info("[INSIGHTS] Engine started - check interval: %.1fs", check_interval)
        
        # Initial cleanup
        self.store.cleanup_old_snapshots(self.config.snapshot_retention_days)
        
        while self._running:
            try:
                cycle_start = time_module.time()
                
                # 1. Run collectors that are due
                collected_data = await self._run_collectors()
                
                # 2. Run analyzers if we have data
                if collected_data:
                    insights = self._run_analyzers(collected_data)
                    
                    # 3. Process and deliver insights
                    if insights:
                        self.delivery.process_insights(insights)
                
                # 4. Run periodic analyzers (they check their own schedules)
                periodic_insights = self._run_periodic_analyzers()
                if periodic_insights:
                    self.delivery.process_insights(periodic_insights)
                
                # 5. Check scheduled reports
                await self._check_scheduled_reports()
                
                # Log cycle time if slow
                cycle_time = time_module.time() - cycle_start
                if cycle_time > 5.0:
                    logger.warning("[INSIGHTS] Slow cycle detected: %.1fs (collectors=%d)", 
                                   cycle_time, len(collected_data) if collected_data else 0)
                
            except Exception as e:
                logger.error("[INSIGHTS] Error in main cycle: %s", e, exc_info=True)
            
            await asyncio.sleep(check_interval)
        
        logger.info("[INSIGHTS] Engine stopped")
    
    def stop(self):
        """Stop the engine."""
        self._running = False
    
    async def _run_collectors(self) -> Dict[str, Any]:
        """Run collectors that are due based on their intervals.
        
        Returns:
            Combined data from all collectors that ran
        """
        now = time_module.time()
        collected_data = {}
        
        for name, collector in self._collectors.items():
            # Check if collector is enabled
            coll_config = self.config.collectors.get(name)
            if coll_config and not coll_config.enabled:
                continue
            
            # Get interval
            interval = coll_config.interval_seconds if coll_config else 300
            
            # Check if due
            last_run = self._last_collection.get(name, 0)
            if now - last_run >= interval:
                try:
                    data = collector.collect()
                    if data:
                        collected_data[name] = data
                        
                        # Save snapshot for historical analysis
                        snapshot = Snapshot(
                            collector=name,
                            timestamp=datetime.now(BRT),
                            data=data
                        )
                        self.store.save_snapshot(snapshot)
                        
                    self._last_collection[name] = now
                    logger.debug(f"Collected from {name}")
                    
                except Exception as e:
                    logger.error(f"Collector {name} error: {e}")
        
        return collected_data
    
    def _run_analyzers(self, data: Dict[str, Any]) -> List[Insight]:
        """Run all analyzers and collect insights.
        
        Args:
            data: Combined data from collectors
            
        Returns:
            List of generated insights
        """
        all_insights: List[Insight] = []
        
        for name, analyzer in self._analyzers.items():
            if not analyzer.is_enabled():
                continue
            
            try:
                result = analyzer.run(data)
                if result.success and result.insights:
                    all_insights.extend(result.insights)
                    logger.debug(f"Analyzer {name}: {len(result.insights)} insights")
            except Exception as e:
                logger.error(f"Analyzer {name} error: {e}")
        
        return all_insights
    
    def _run_periodic_analyzers(self) -> List[Insight]:
        """Run periodic analyzers that are due based on their schedules.
        
        Periodic analyzers (like sleep correlation, resource trends) run
        less frequently (hourly/daily) and analyze historical data.
        
        Returns:
            List of generated insights
        """
        all_insights: List[Insight] = []
        
        for name, analyzer in self._periodic_analyzers.items():
            if not analyzer.is_enabled():
                continue
            
            # Check if analyzer should run (based on its interval)
            if not analyzer.should_run():
                continue
            
            try:
                # Periodic analyzers typically don't need current data
                # They query historical snapshots from the store
                result = analyzer.run({})
                if result.success and result.insights:
                    all_insights.extend(result.insights)
                    logger.info(f"Periodic analyzer {name}: {len(result.insights)} insights")
            except Exception as e:
                logger.error(f"Periodic analyzer {name} error: {e}")
        
        return all_insights
    
    async def _check_scheduled_reports(self):
        """Check if any scheduled reports are due and send them."""
        now = datetime.now(BRT)
        today = now.strftime("%Y-%m-%d")
        
        # Morning report
        if self.config.delivery.morning_report_enabled:
            if self._is_report_due("morning", today, now):
                logger.info("Sending morning report...")
                success = self.delivery.send_morning_report()
                if success:
                    self._mark_report_sent("morning", today)
        
        # Evening report
        if self.config.delivery.evening_report_enabled:
            if self._is_report_due("evening", today, now):
                logger.info("Sending evening report...")
                success = self.delivery.send_evening_report()
                if success:
                    self._mark_report_sent("evening", today)
        
        # Weekly report (check day of week too)
        if self.config.delivery.weekly_report_enabled:
            day_name = now.strftime("%A").lower()
            if day_name == self.config.delivery.weekly_report_day:
                week_key = now.strftime("%Y-W%W")
                if self._is_report_due("weekly", week_key, now, is_weekly=True):
                    logger.info("Sending weekly report...")
                    success = self.delivery.send_weekly_report()
                    if success:
                        self._mark_report_sent("weekly", week_key)
    
    def _is_report_due(
        self, 
        report_type: str, 
        date_key: str, 
        now: datetime,
        is_weekly: bool = False
    ) -> bool:
        """Check if a report is due.
        
        Args:
            report_type: "morning", "evening", or "weekly"
            date_key: Date/week string to track delivery
            now: Current datetime
            is_weekly: Whether this is a weekly report
            
        Returns:
            True if report should be sent now
        """
        # Check if already sent
        state_key = f"{report_type}_report"
        if self._report_state.get(state_key) == date_key:
            return False
        
        # Get target time
        if report_type == "morning":
            target = self.config.delivery.morning_report_time
        elif report_type == "evening":
            target = self.config.delivery.evening_report_time
        else:
            target = self.config.delivery.weekly_report_time
        
        # Check if within 2 minute window of target time
        current_minutes = now.hour * 60 + now.minute
        target_minutes = target.hour * 60 + target.minute
        
        return abs(current_minutes - target_minutes) <= 2
    
    def _mark_report_sent(self, report_type: str, date_key: str):
        """Mark a report as sent."""
        state_key = f"{report_type}_report"
        self._report_state[state_key] = date_key
        self._save_report_state()
        logger.info(f"Marked {report_type} report as sent for {date_key}")


def main():
    """Entry point for the insights engine daemon."""
    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    
    logger.info("Starting Friday Insights Engine...")
    
    engine = InsightsEngine()
    
    # Setup signal handlers
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        engine.stop()
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    try:
        asyncio.run(engine.run(check_interval=10.0))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
