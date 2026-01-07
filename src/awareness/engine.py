"""
Friday Awareness Engine - Main Orchestrator

The AwarenessEngine coordinates all components:
- Data Sources: Call atomic tools to gather data (replaces collectors)
- Analyzers: Process data and generate insights
- Decision Engine: Determine what to deliver and when
- Delivery Manager: Send insights via appropriate channels

Usage:
    python -m src.awareness.engine
"""

import asyncio
import json
import logging
import signal
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from croniter import croniter

from settings import settings
from src.awareness.models import Insight, Snapshot
from src.awareness.store import InsightsStore
from src.awareness.analyzers import (
    ThresholdAnalyzer,
    StressAnalyzer,
    CalendarAnalyzer,
    SleepCorrelationAnalyzer,
    ResourceTrendAnalyzer,
)
from src.awareness.analyzers.daily_journal import DailyJournalAnalyzer
from src.awareness.decision import DecisionEngine, BudgetManager
from src.awareness.delivery import DeliveryManager

logger = logging.getLogger(__name__)


class AwarenessEngine:
    """
    Main orchestrator for the Friday Awareness system.

    Runs a continuous loop that:
    1. Calls atomic tools from data sources (on their cron schedules)
    2. Runs analyzers to generate insights
    3. Decides which insights to deliver
    4. Delivers via appropriate channels
    5. Sends scheduled reports (morning/evening/weekly)
    """

    def __init__(self, config=None):
        """Initialize the awareness engine.

        Args:
            config: Configuration dict. Uses settings.AWARENESS if not provided.
        """
        self.config = config or settings.AWARENESS
        self.store = InsightsStore()

        # Import agent to access registered tools
        from src.core.agent import agent
        self.agent = agent

        # Initialize data source schedulers (cron-based)
        self._data_source_iters: Dict[str, croniter] = {}
        self._data_source_next_run: Dict[str, datetime] = {}
        
        for source in self.config.get("data_sources", []):
            if source.get("enabled", True):
                name = source["name"]
                schedule = source["schedule"]
                now = datetime.now()
                
                # Create croniter instance with timezone
                now_tz = datetime.now(settings.TIMEZONE)
                cron = croniter(schedule, now_tz)
                self._data_source_iters[name] = cron
                self._data_source_next_run[name] = cron.get_next(datetime)
                
                logger.info(f"[AWARENESS] Scheduled data source '{name}' with cron: {schedule}")

        # Initialize report schedulers (cron-based)
        self._report_iters: Dict[str, croniter] = {}
        self._report_next_run: Dict[str, datetime] = {}
        self._report_state: Dict[str, str] = {}
        
        for report in self.config.get("scheduled_reports", []):
            if report.get("enabled", True):
                name = report["name"]
                schedule = report["schedule"]
                now_tz = datetime.now(settings.TIMEZONE)
                
                # Create croniter instance with timezone
                cron = croniter(schedule, now_tz)
                self._report_iters[name] = cron
                self._report_next_run[name] = cron.get_next(datetime)
                
                logger.info(f"[AWARENESS] Scheduled report '{name}' with cron: {schedule}")

        # Initialize analyzers (they need config and store)
        # Real-time analyzers (run every cycle when data is collected)
        self._analyzers = {}
        
        for source in self.config.get("data_sources", []):
            if not source.get("enabled", True):
                continue
                
            analyzer_names = source.get("analyzers", [])
            for analyzer_name in analyzer_names:
                if analyzer_name not in self._analyzers:
                    # Create analyzer instance based on name
                    if analyzer_name == "threshold":
                        self._analyzers[analyzer_name] = ThresholdAnalyzer(self.config, self.store)
                    elif analyzer_name == "stress_monitor":
                        self._analyzers[analyzer_name] = StressAnalyzer(self.config, self.store)
                    elif analyzer_name == "calendar_reminder":
                        self._analyzers[analyzer_name] = CalendarAnalyzer(self.config, self.store)
                    
                    logger.info(f"[AWARENESS] Initialized analyzer: {analyzer_name}")

        # Periodic analyzers (run on their own schedules)
        self._periodic_analyzers = {
            "sleep_correlation": SleepCorrelationAnalyzer(self.config, self.store),
            "resource_trend": ResourceTrendAnalyzer(self.config, self.store),
        }

        # Scheduled analyzers (run at specific times)
        self._scheduled_analyzers = {
            "daily_journal": DailyJournalAnalyzer(self.config, self.store),
        }

        # Initialize delivery
        self.delivery = DeliveryManager(self.config, self.store)

        # Control
        self._running = False

        logger.info(
            "[AWARENESS] Engine initialized with %d data sources, %d analyzers",
            len(self._data_source_iters),
            len(self._analyzers),
        )

    async def run(self, check_interval: float = 60.0):
        """Run the awareness engine main loop.

        Args:
            check_interval: How often to check for work (seconds)
        """
        self._running = True
        logger.info("[AWARENESS] Engine started - check interval: %.1fs", check_interval)

        # Initial cleanup
        self.store.cleanup_old_snapshots(self.config.get("snapshot_retention_days", 90))

        while self._running:
            try:
                cycle_start = time_module.time()
                now = datetime.now(settings.TIMEZONE)

                # 1. Run data sources that are due
                collected_data = await self._run_data_sources(now)

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
                await self._check_scheduled_reports(now)

                # Log cycle time if slow
                cycle_time = time_module.time() - cycle_start
                if cycle_time > 5.0:
                    logger.warning(
                        "[AWARENESS] Slow cycle detected: %.1fs (data_sources=%d)",
                        cycle_time,
                        len(collected_data) if collected_data else 0,
                    )

            except Exception as e:
                logger.error("[AWARENESS] Error in main cycle: %s", e, exc_info=True)

            await asyncio.sleep(check_interval)

        logger.info("[AWARENESS] Engine stopped")

    def stop(self):
        """Stop the engine."""
        self._running = False

    async def _run_data_sources(self, now: datetime) -> Dict[str, Any]:
        """Run data sources that are due based on their cron schedules.

        Args:
            now: Current datetime

        Returns:
            Combined data from all data sources that ran
        """
        collected_data = {}

        for source in self.config.get("data_sources", []):
            if not source.get("enabled", True):
                continue
                
            name = source["name"]
            tool_path = source["tool"]  # Format: "src.tools.health.get_recovery_status"
            
            # Check if due to run
            next_run = self._data_source_next_run.get(name)
            if next_run and now >= next_run:
                try:
                    # Import and call the tool function dynamically
                    tool_func = self._import_tool(tool_path)
                    
                    if tool_func:
                        # Call the tool
                        logger.debug(f"[AWARENESS] Calling data source: {name} -> {tool_path}()")
                        data = tool_func()
                        
                        if data and not (isinstance(data, dict) and data.get("error")):
                            collected_data[name] = data
                            
                            # Save snapshot manually (tools called directly don't auto-save)
                            tool_name = tool_path.split(".")[-1]  # Extract function name
                            snapshot = Snapshot(
                                collector=tool_name,
                                timestamp=datetime.now(),
                                data=data
                            )
                            self.store.save_snapshot(snapshot)
                            logger.debug(f"[AWARENESS] Saved snapshot for {tool_name}")
                            
                            logger.info(f"[AWARENESS] Collected data from: {name}")
                        else:
                            error_msg = data.get("error") if isinstance(data, dict) else "Unknown error"
                            logger.warning(f"[AWARENESS] Data source {name} returned error: {error_msg}")
                    else:
                        logger.error(f"[AWARENESS] Tool not found: {tool_path}")
                    
                    # Update next run time
                    cron = self._data_source_iters[name]
                    self._data_source_next_run[name] = cron.get_next(datetime)
                    logger.debug(f"[AWARENESS] Next run for {name}: {self._data_source_next_run[name]}")
                    
                except Exception as e:
                    logger.error(f"[AWARENESS] Data source {name} error: {e}", exc_info=True)

        return collected_data
    
    def _import_tool(self, tool_path: str):
        """Import a tool function from a dotted path.
        
        Args:
            tool_path: Full dotted path to tool (e.g., "src.tools.health.get_recovery_status")
            
        Returns:
            The tool function or None if not found
        """
        try:
            import importlib
            
            # Split path into module and function name
            parts = tool_path.rsplit(".", 1)
            if len(parts) != 2:
                logger.error(f"Invalid tool path format: {tool_path}")
                return None
            
            module_path, func_name = parts
            
            # Import module and get function
            module = importlib.import_module(module_path)
            tool_func = getattr(module, func_name, None)
            
            if not tool_func:
                logger.error(f"Function {func_name} not found in {module_path}")
                return None
                
            return tool_func
            
        except Exception as e:
            logger.error(f"Failed to import tool {tool_path}: {e}")
            return None
    
    def trigger_report(self, report_name: str) -> bool:
        """Manually trigger a scheduled report by name.
        
        This allows manual execution of any scheduled report through the same
        code path as the automatic scheduler, ensuring consistent behavior.
        
        Args:
            report_name: Name of the report to trigger (e.g., 'journal_thread')
            
        Returns:
            True if report was triggered successfully, False otherwise
        """
        # Find the report configuration
        for report in self.config.get("scheduled_reports", []):
            if report["name"] == report_name:
                if not report.get("enabled", True):
                    logger.warning(f"[AWARENESS] Report {report_name} is disabled")
                    return False
                
                # Execute the report with force=True to bypass duplicate check
                return self._execute_report(report, force=True)
        
        logger.error(f"[AWARENESS] Report not found: {report_name}")
        return False
    
    def get_scheduled_reports(self) -> list[dict]:
        """Get list of all scheduled reports with their configuration.
        
        Returns:
            List of report configurations
        """
        return self.config.get("scheduled_reports", [])
    
    def get_report_status(self, report_name: str) -> dict:
        """Get status information for a specific report.
        
        Args:
            report_name: Name of the report
            
        Returns:
            Dict with status info (last_sent, next_run, enabled)
        """
        # Find the report
        report_config = None
        for report in self.config.get("scheduled_reports", []):
            if report["name"] == report_name:
                report_config = report
                break
        
        if not report_config:
            return {"error": f"Report '{report_name}' not found"}
        
        return {
            "name": report_name,
            "enabled": report_config.get("enabled", True),
            "schedule": report_config.get("schedule", "N/A"),
            "last_sent": self._report_state.get(report_name),
            "next_run": self._report_next_run.get(report_name).strftime("%Y-%m-%d %H:%M:%S") if self._report_next_run.get(report_name) else None,
            "description": report_config.get("description", ""),
            "channels": report_config.get("channels", []),
        }
    
    def _send_journal_thread(self, insight):
        """Send journal thread and return message_id.
        
        Args:
            insight: The insight to send
            
        Returns:
            Message ID if sent successfully, None otherwise
        """
        try:
            # Get telegram channel from delivery manager's registry
            telegram_channel = self.delivery.channel_registry.get("telegram")
            if not telegram_channel:
                logger.error("[AWARENESS] No Telegram channel configured")
                return None
            
            # Send and get message_id
            message_id = telegram_channel.send_insight_sync_with_id(insight)
            
            if message_id:
                logger.info(f"[AWARENESS] Journal thread sent with message_id={message_id}")
                return message_id
            else:
                logger.error("[AWARENESS] Failed to send journal thread")
                return None
                
        except Exception as e:
            logger.error(f"[AWARENESS] Error sending journal thread: {e}")
            return None

    def _run_analyzers(self, data: Dict[str, Any]) -> List[Insight]:
        """Run all analyzers and collect insights.

        Args:
            data: Combined data from data sources

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
                    logger.info(
                        f"Periodic analyzer {name}: {len(result.insights)} insights"
                    )
            except Exception as e:
                logger.error(f"Periodic analyzer {name} error: {e}")

        return all_insights

    def _execute_report(self, report: dict, force: bool = False) -> bool:
        """Execute a scheduled report.
        
        Args:
            report: Report configuration dict
            force: If True, bypasses duplicate check and sends anyway
            
        Returns:
            True if report was executed successfully, False otherwise
        """
        name = report["name"]
        tool_path = report["tool"]
        today = datetime.now(settings.TIMEZONE).strftime("%Y-%m-%d")
        
        # Check if already sent today (unless forced)
        if not force:
            last_sent = self._report_state.get(name)
            if last_sent == today:
                logger.info(f"[AWARENESS] Report {name} already sent today, skipping")
                return False
        
        try:
            # Import and call the report tool
            tool_func = self._import_tool(tool_path)
            
            if not tool_func:
                logger.error(f"[AWARENESS] Report tool not found: {tool_path}")
                return False
            
            logger.info(f"[AWARENESS] Executing scheduled report: {name}")
            report_text = tool_func()
            
            # Send via delivery manager
            channels = report.get("channels", ["telegram"])
            if "telegram" in channels:
                # Create a simple insight to wrap the report
                from src.awareness.models import Insight, Priority, InsightType, Category
                insight = Insight(
                    type=InsightType.DIGEST,
                    category=Category.SYSTEM,
                    priority=Priority.HIGH,
                    title=name,
                    message=report_text,
                    confidence=1.0
                )
                
                # For journal threads, send directly and capture message_id
                if name == "journal_thread":
                    message_id = self._send_journal_thread(insight)
                    if message_id:
                        # Save thread to database
                        from src.tools.journal import save_journal_thread
                        save_journal_thread(today, message_id)
                        logger.info(f"[AWARENESS] Saved journal thread with message_id={message_id}")
                else:
                    # Regular report - use normal delivery process
                    self.delivery.process_insights([insight])
                
                self._report_state[name] = today
                logger.info(f"[AWARENESS] Sent report: {name}")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"[AWARENESS] Report {name} error: {e}", exc_info=True)
            return False
    
    async def _check_scheduled_reports(self, now: datetime):
        """Check if any scheduled reports are due and send them.
        
        Args:
            now: Current datetime
        """
        for report in self.config.get("scheduled_reports", []):
            if not report.get("enabled", True):
                continue
                
            name = report["name"]
            
            # Check if due to run
            next_run = self._report_next_run.get(name)
            if next_run and now >= next_run:
                # Execute the report
                self._execute_report(report, force=False)
                
                # Update next run time
                cron = self._report_iters[name]
                self._report_next_run[name] = cron.get_next(datetime)


def main():
    """Entry point for the awareness engine daemon."""
    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    logger.info("Starting Friday Awareness Engine...")

    engine = AwarenessEngine()

    # Setup signal handlers
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        engine.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        asyncio.run(engine.run(check_interval=60.0))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
