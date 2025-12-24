"""
Friday Insights Engine - Delivery Manager

Orchestrates insight delivery across all channels.
"""

from datetime import datetime
from typing import List, Dict, Any
import logging

from src.insights.models import (
    Insight, Priority, Category, BRT, DeliveryChannel
)
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore
from src.insights.decision.engine import DecisionEngine, DeliveryAction
from src.insights.delivery.telegram import TelegramSender
from src.insights.delivery.reports import ReportGenerator

logger = logging.getLogger(__name__)


class DeliveryManager:
    """
    Central manager for all insight delivery.
    
    Responsibilities:
    - Process insights through decision engine
    - Route to appropriate delivery channel
    - Generate and send scheduled reports
    - Track delivery status
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        self.config = config
        self.store = store
        self.decision = DecisionEngine(config, store)
        self.telegram = TelegramSender()
        self.reports = ReportGenerator(config, store)
    
    def process_insights(self, insights: List[Insight]) -> Dict[str, int]:
        """Process a batch of insights from analyzers.
        
        Args:
            insights: List of insights to process
            
        Returns:
            Stats: {"delivered": N, "batched": N, "skipped": N}
        """
        stats = {"delivered": 0, "batched": 0, "queued": 0, "skipped": 0}
        
        # Run through decision engine
        decisions = self.decision.process(insights)
        
        # Process each decision
        for insight in decisions[DeliveryAction.DELIVER_NOW]:
            success = self._deliver_immediate(insight)
            if success:
                stats["delivered"] += 1
            else:
                stats["queued"] += 1
        
        for insight in decisions[DeliveryAction.BATCH_REPORT]:
            self._batch_for_report(insight)
            stats["batched"] += 1
        
        for insight in decisions[DeliveryAction.QUEUE_LATER]:
            self._queue_for_later(insight)
            stats["queued"] += 1
        
        stats["skipped"] = len(decisions[DeliveryAction.SKIP])
        
        logger.info(f"Processed {len(insights)} insights: {stats}")
        return stats
    
    def _deliver_immediate(self, insight: Insight) -> bool:
        """Deliver an insight immediately via Telegram."""
        try:
            success = self.telegram.send_insight_sync(insight)
            if success:
                self.decision.record_delivery(insight, DeliveryChannel.TELEGRAM)
            return success
        except Exception as e:
            logger.error(f"Failed to deliver insight: {e}")
            return False
    
    def _batch_for_report(self, insight: Insight):
        """Save insight for inclusion in next report."""
        try:
            self.store.save_insight(insight)
            logger.debug(f"Batched insight for report: {insight.title}")
        except Exception as e:
            logger.error(f"Failed to batch insight: {e}")
    
    def _queue_for_later(self, insight: Insight):
        """Save insight for later delivery (when budget available/quiet hours end)."""
        try:
            self.store.save_insight(insight)
            logger.debug(f"Queued insight for later: {insight.title}")
        except Exception as e:
            logger.error(f"Failed to queue insight: {e}")
    
    def send_morning_report(self) -> bool:
        """Generate and send morning report."""
        try:
            report = self.reports.generate_morning_report()
            success = self.telegram.send_report_sync(report, "morning")
            
            if success:
                logger.info("Morning report sent successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send morning report: {e}")
            return False
    
    def send_evening_report(self) -> bool:
        """Generate and send evening report."""
        try:
            report = self.reports.generate_evening_report()
            success = self.telegram.send_report_sync(report, "evening")
            
            if success:
                logger.info("Evening report sent successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send evening report: {e}")
            return False
    
    def send_weekly_report(self) -> bool:
        """Generate and send weekly report."""
        try:
            report = self.reports.generate_weekly_report()
            success = self.telegram.send_report_sync(report, "weekly")
            
            if success:
                logger.info("Weekly report sent successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send weekly report: {e}")
            return False
    
    def process_queued_insights(self) -> int:
        """Process insights that were queued (after quiet hours end, etc).
        
        Returns:
            Number of insights delivered
        """
        pending = self.decision.get_pending_for_delivery()
        delivered = 0
        
        for insight in pending:
            if self._deliver_immediate(insight):
                delivered += 1
        
        if delivered > 0:
            logger.info(f"Delivered {delivered} queued insights")
        
        return delivered
    
    def should_send_morning_report(self) -> bool:
        """Check if it's time for morning report."""
        if not self.config.delivery.morning_report_enabled:
            return False
        
        now = datetime.now(BRT)
        target = self.config.delivery.morning_report_time
        
        # Check if within 5 minute window of target time
        now_minutes = now.hour * 60 + now.minute
        target_minutes = target.hour * 60 + target.minute
        
        return abs(now_minutes - target_minutes) <= 2
    
    def should_send_evening_report(self) -> bool:
        """Check if it's time for evening report."""
        if not self.config.delivery.evening_report_enabled:
            return False
        
        now = datetime.now(BRT)
        target = self.config.delivery.evening_report_time
        
        now_minutes = now.hour * 60 + now.minute
        target_minutes = target.hour * 60 + target.minute
        
        return abs(now_minutes - target_minutes) <= 2
    
    def should_send_weekly_report(self) -> bool:
        """Check if it's time for weekly report."""
        if not self.config.delivery.weekly_report_enabled:
            return False
        
        now = datetime.now(BRT)
        target_day = self.config.delivery.weekly_report_day.lower()
        target_time = self.config.delivery.weekly_report_time
        
        # Check day
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if days[now.weekday()] != target_day:
            return False
        
        # Check time
        now_minutes = now.hour * 60 + now.minute
        target_minutes = target_time.hour * 60 + target_time.minute
        
        return abs(now_minutes - target_minutes) <= 2
