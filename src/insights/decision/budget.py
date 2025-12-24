"""
Friday Insights Engine - Budget Manager

Handles rate limiting, quiet hours, and daily reach-out budgets.
"""

from datetime import datetime, time
from typing import Optional
import logging

from src.insights.models import BRT, Priority, Insight
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Manages daily reach-out budget and quiet hours.
    
    Constraints:
    - Max N reach-outs per day (default 5)
    - Quiet hours (default 22:00 - 08:00 BRT)
    - URGENT priority bypasses quiet hours
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        self.config = config
        self.store = store
    
    def can_deliver(self, insight: Insight) -> bool:
        """Check if an insight can be delivered right now.
        
        Considers:
        - Daily budget
        - Quiet hours (unless URGENT)
        
        Args:
            insight: The insight to potentially deliver
            
        Returns:
            True if delivery is allowed
        """
        # URGENT always goes through
        if insight.priority == Priority.URGENT:
            logger.debug(f"URGENT insight bypasses all checks: {insight.title}")
            return True
        
        # Check quiet hours for non-urgent
        if self.is_quiet_hours():
            logger.debug(f"In quiet hours, blocking: {insight.title}")
            return False
        
        # Check daily budget
        if not self.has_budget():
            logger.debug(f"Daily budget exhausted, blocking: {insight.title}")
            return False
        
        return True
    
    def is_quiet_hours(self) -> bool:
        """Check if we're currently in quiet hours."""
        now = datetime.now(BRT).time()
        start = self.config.decision.quiet_hours_start
        end = self.config.decision.quiet_hours_end
        
        # Handle overnight quiet hours (e.g., 22:00 - 08:00)
        if start > end:
            # Quiet if after start OR before end
            return now >= start or now < end
        else:
            # Normal range (e.g., 13:00 - 14:00)
            return start <= now < end
    
    def has_budget(self) -> bool:
        """Check if we have remaining reach-out budget for today."""
        budget = self.store.get_today_budget(
            max_per_day=self.config.decision.max_reach_outs_per_day
        )
        return budget.can_reach_out()
    
    def consume_budget(self, insight_id: str):
        """Consume one unit of today's budget."""
        self.store.increment_budget(insight_id)
        logger.info(f"Budget consumed for insight {insight_id}")
    
    def get_budget_status(self) -> dict:
        """Get current budget status."""
        budget = self.store.get_today_budget(
            max_per_day=self.config.decision.max_reach_outs_per_day
        )
        return {
            "date": budget.date,
            "used": budget.count,
            "max": budget.max_per_day,
            "remaining": budget.max_per_day - budget.count,
            "is_quiet_hours": self.is_quiet_hours(),
        }
    
    def minutes_until_quiet_ends(self) -> Optional[int]:
        """Get minutes until quiet hours end, if in quiet hours."""
        if not self.is_quiet_hours():
            return None
        
        now = datetime.now(BRT)
        end_time = self.config.decision.quiet_hours_end
        
        # Build end datetime
        end_dt = now.replace(
            hour=end_time.hour, 
            minute=end_time.minute, 
            second=0, 
            microsecond=0
        )
        
        # If end is tomorrow
        if end_dt <= now:
            from datetime import timedelta
            end_dt += timedelta(days=1)
        
        delta = end_dt - now
        return int(delta.total_seconds() / 60)
