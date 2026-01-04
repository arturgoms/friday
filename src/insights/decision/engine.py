"""
Friday Insights Engine - Decision Engine

Decides which insights to deliver and how.
"""

from datetime import datetime
from typing import List, Dict, Any, Tuple
from enum import Enum
import logging

from src.insights.models import (
    Insight, Priority, DeliveryChannel
)
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore
from src.insights.decision.budget import BudgetManager

logger = logging.getLogger(__name__)


class DeliveryAction(Enum):
    """What to do with an insight."""
    DELIVER_NOW = "deliver_now"      # Send immediately via Telegram
    BATCH_REPORT = "batch_report"    # Add to next morning/evening report
    QUEUE_LATER = "queue_later"      # Wait (quiet hours, budget exhausted)
    SKIP = "skip"                    # Don't deliver (duplicate, expired, etc.)


class DecisionEngine:
    """
    Decides what to do with each insight.
    
    Logic:
    - URGENT: Always deliver immediately
    - HIGH: Deliver if not in quiet hours and budget available
    - MEDIUM: Deliver if budget available, otherwise batch
    - LOW: Always batch for reports
    
    Also handles:
    - Deduplication (don't send same insight twice)
    - Expiration (skip insights past their expiry)
    - Priority scoring for batch ordering
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        self.config = config
        self.store = store
        self.budget = BudgetManager(config, store)
    
    def process(self, insights: List[Insight]) -> Dict[DeliveryAction, List[Insight]]:
        """Process a batch of insights and decide what to do with each.
        
        Args:
            insights: List of insights to process
            
        Returns:
            Dict mapping DeliveryAction to list of insights
        """
        results: Dict[DeliveryAction, List[Insight]] = {
            DeliveryAction.DELIVER_NOW: [],
            DeliveryAction.BATCH_REPORT: [],
            DeliveryAction.QUEUE_LATER: [],
            DeliveryAction.SKIP: [],
        }
        
        for insight in insights:
            action, reason = self._decide(insight)
            results[action].append(insight)
            logger.debug(f"Decision for '{insight.title}': {action.value} ({reason})")
        
        return results
    
    def _decide(self, insight: Insight) -> Tuple[DeliveryAction, str]:
        """Decide what to do with a single insight.
        
        Returns:
            Tuple of (action, reason)
        """
        # Check if expired
        if insight.is_expired():
            return DeliveryAction.SKIP, "expired"
        
        # Check for duplicates
        if insight.dedupe_key and self.store.check_duplicate(
            insight.dedupe_key, 
            hours=int(self.config.decision.cooldown_minutes / 60) or 1
        ):
            return DeliveryAction.SKIP, "duplicate"
        
        # Route based on priority
        if insight.priority == Priority.URGENT:
            # URGENT always goes through immediately
            return DeliveryAction.DELIVER_NOW, "urgent_priority"
        
        elif insight.priority == Priority.HIGH:
            # HIGH: Deliver if allowed, otherwise queue
            if self.budget.can_deliver(insight):
                return DeliveryAction.DELIVER_NOW, "high_priority"
            elif self.budget.is_quiet_hours():
                return DeliveryAction.QUEUE_LATER, "quiet_hours"
            else:
                return DeliveryAction.BATCH_REPORT, "budget_exhausted"
        
        elif insight.priority == Priority.MEDIUM:
            # MEDIUM: Deliver if budget allows, otherwise batch
            if self.budget.is_quiet_hours():
                return DeliveryAction.BATCH_REPORT, "quiet_hours"
            elif self.budget.has_budget():
                return DeliveryAction.DELIVER_NOW, "medium_with_budget"
            else:
                return DeliveryAction.BATCH_REPORT, "budget_exhausted"
        
        else:  # LOW
            # LOW: Always batch
            return DeliveryAction.BATCH_REPORT, "low_priority"
    
    def get_pending_for_delivery(self) -> List[Insight]:
        """Get insights that were queued and are now ready for delivery.
        
        Called when quiet hours end or budget resets.
        """
        pending = self.store.get_pending_insights()
        ready = []
        
        for insight in pending:
            if insight.is_expired():
                continue
            
            if self.budget.can_deliver(insight):
                ready.append(insight)
        
        return ready
    
    def get_for_report(self, channel: DeliveryChannel) -> List[Insight]:
        """Get insights to include in a scheduled report.
        
        Args:
            channel: Which report (morning, evening, weekly)
            
        Returns:
            List of insights, sorted by priority
        """
        # Get recent insights that haven't been delivered
        hours = 24 if channel != DeliveryChannel.WEEKLY_REPORT else 168
        recent = self.store.get_recent_insights(hours=hours)
        
        # Filter for batched/undelivered
        batched = [i for i in recent if not i.is_expired()]
        
        # Sort by priority (urgent first, then high, medium, low)
        priority_order = {
            Priority.URGENT: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        batched.sort(key=lambda i: priority_order.get(i.priority, 99))
        
        return batched
    
    def record_delivery(self, insight: Insight, channel: DeliveryChannel):
        """Record that an insight was delivered.
        
        Args:
            insight: The insight that was delivered
            channel: How it was delivered
        """
        from src.insights.models import Delivery
        
        # Save insight to store if not already saved
        try:
            self.store.save_insight(insight)
        except Exception:
            pass  # May already exist
        
        # Record delivery
        delivery = Delivery(
            insight_id=insight.id,
            channel=channel,
        )
        self.store.save_delivery(delivery)
        self.store.mark_delivered(insight.id)
        
        # Consume budget for immediate deliveries
        if channel == DeliveryChannel.TELEGRAM:
            self.budget.consume_budget(insight.id)
        
        logger.info(f"Recorded delivery: {insight.title} via {channel.value}")
