"""
Friday Insights Engine - Budget Manager

Handles rate limiting, quiet hours, and daily reach-out budgets.
"""

from datetime import datetime, time
from typing import Optional
import logging

from src.awareness.models import Priority, Insight
from settings import settings
from src.awareness.store import InsightsStore

from settings import settings
def get_brt():
    return settings.TIMEZONE

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Manages daily reach-out budget and quiet hours.
    
    Constraints:
    - Max N reach-outs per day (default 5)
    - Quiet hours (default 22:00 - 08:00 BRT)
    - URGENT priority bypasses quiet hours
    """
    
    def __init__(self, config: dict, store: InsightsStore):
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
        now = datetime.now(get_brt()).time()
        decision_config = self.config.get("decision", {})
        quiet_hours = decision_config.get("quiet_hours", {})
        
        # Get start and end times
        start_str = quiet_hours.get("start")
        end_str = quiet_hours.get("end")
        
        # If quiet hours not configured, assume no quiet hours
        if not start_str or not end_str:
            return False
        
        # Parse time strings (format: "HH:MM")
        try:
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
            start = time(start_hour, start_min)
            end = time(end_hour, end_min)
        except (ValueError, AttributeError):
            logger.error(f"Invalid quiet hours format: start={start_str}, end={end_str}")
            return False
        
        # Handle overnight quiet hours (e.g., 22:00 - 08:00)
        if start > end:
            # Quiet if after start OR before end
            return now >= start or now < end
        else:
            # Normal range (e.g., 13:00 - 14:00)
            return start <= now < end
    
    def has_budget(self) -> bool:
        """Check if we have remaining reach-out budget for today."""
        max_per_day = self.config.get("decision", {}).get("max_reach_outs_per_day", 5)
        budget = self.store.get_today_budget(max_per_day=max_per_day)
        return budget.can_reach_out()
    
    def consume_budget(self, insight_id: str):
        """Consume one unit of today's budget."""
        self.store.increment_budget(insight_id)
        logger.info(f"Budget consumed for insight {insight_id}")
    
    def get_budget_status(self) -> dict:
        """Get current budget status."""
        max_per_day = self.config.get("decision", {}).get("max_reach_outs_per_day", 5)
        budget = self.store.get_today_budget(max_per_day=max_per_day)
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
        
        now = datetime.now(get_brt())
        decision_config = self.config.get("decision", {})
        quiet_hours = decision_config.get("quiet_hours", {})
        end_str = quiet_hours.get("end")
        
        if not end_str:
            return None
        
        # Parse end time string (format: "HH:MM")
        try:
            end_hour, end_min = map(int, end_str.split(":"))
            end_time = time(end_hour, end_min)
        except (ValueError, AttributeError):
            logger.error(f"Invalid quiet hours end format: {end_str}")
            return None
        
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
