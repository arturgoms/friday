"""
Friday Insights Engine - Stress Analyzer

Detects sustained high stress levels over time.
Different from ThresholdAnalyzer - this looks for patterns, not single values.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from src.insights.analyzers.base import RealTimeAnalyzer
from src.insights.models import (
    Insight,
    InsightType,
    Priority,
    Category,
    BRT,
)
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class StressAnalyzer(RealTimeAnalyzer):
    """
    Analyzes stress patterns over time.
    
    Unlike ThresholdAnalyzer which checks instant values, this analyzer
    looks for sustained periods of elevated stress and generates insights
    with recommendations for recovery.
    
    Checks:
    - Sustained high stress (>50) for 2+ hours
    - Sustained critical stress (>70) for 1+ hour
    - Stress recovery patterns (stress dropping after high period)
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        super().__init__("stress_monitor", config, store)
        self._high_stress_start: Optional[datetime] = None
        self._critical_stress_start: Optional[datetime] = None
        self._last_recovery_alert: Optional[datetime] = None
    
    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Analyze stress patterns and generate insights."""
        insights = []
        
        health = data.get("health", {})
        sync_info = health.get("sync", {})
        
        # Skip if data is stale
        if sync_info.get("status") != "fresh":
            return insights
        
        stress = health.get("stress", {}).get("current")
        if stress is None:
            return insights
        
        # Get threshold config
        stress_config = self.config.thresholds.get("stress", {})
        warning_threshold = stress_config.get("warning", 50)
        critical_threshold = stress_config.get("critical", 70)
        sustained_minutes = stress_config.get("sustained_minutes", 120)
        
        now = datetime.now(BRT)
        
        # Check for critical stress
        if stress >= critical_threshold:
            if self._critical_stress_start is None:
                self._critical_stress_start = now
                logger.debug(f"Critical stress started: {stress}")
            else:
                duration = now - self._critical_stress_start
                duration_minutes = duration.total_seconds() / 60
                
                # Alert after 60 minutes of critical stress
                if duration_minutes >= 60:
                    insights.extend(self._generate_critical_stress_insight(
                        stress, duration_minutes
                    ))
        else:
            # Reset critical counter if stress dropped
            if self._critical_stress_start is not None:
                self._critical_stress_start = None
        
        # Check for sustained high stress
        if stress >= warning_threshold:
            if self._high_stress_start is None:
                self._high_stress_start = now
                logger.debug(f"High stress started: {stress}")
            else:
                duration = now - self._high_stress_start
                duration_minutes = duration.total_seconds() / 60
                
                # Alert after sustained_minutes of high stress
                if duration_minutes >= sustained_minutes:
                    insights.extend(self._generate_sustained_stress_insight(
                        stress, duration_minutes
                    ))
        else:
            # Check for recovery (stress dropped from elevated)
            if self._high_stress_start is not None:
                duration = now - self._high_stress_start
                duration_minutes = duration.total_seconds() / 60
                
                # Only celebrate recovery if they were stressed for a while
                if duration_minutes >= 30:
                    insights.extend(self._generate_recovery_insight(stress))
            
            self._high_stress_start = None
        
        return insights
    
    def _generate_critical_stress_insight(
        self, 
        stress: int, 
        duration_minutes: float
    ) -> List[Insight]:
        """Generate insight for critical stress levels."""
        dedupe_key = "stress_critical_sustained"
        
        # Only alert once per 4 hours for critical stress
        if self.was_insight_delivered_recently(dedupe_key, hours=4):
            return []
        
        hours = duration_minutes / 60
        
        return [Insight(
            type=InsightType.THRESHOLD,
            category=Category.HEALTH,
            priority=Priority.HIGH,
            title="Critical stress level sustained",
            message=(
                f"Stress at {stress} for {hours:.1f}h. "
                "Consider taking a break: walk, breathe, or step away from screens."
            ),
            dedupe_key=dedupe_key,
            data={
                "stress": stress,
                "duration_minutes": duration_minutes,
                "recommendation": "immediate_break",
            },
            expires_at=datetime.now(BRT) + timedelta(hours=2),
        )]
    
    def _generate_sustained_stress_insight(
        self, 
        stress: int, 
        duration_minutes: float
    ) -> List[Insight]:
        """Generate insight for sustained elevated stress."""
        dedupe_key = "stress_high_sustained"
        
        # Only alert once per 4 hours for sustained high stress
        if self.was_insight_delivered_recently(dedupe_key, hours=4):
            return []
        
        hours = duration_minutes / 60
        
        # Get body battery context if available
        body_battery = None
        snapshots = self.get_recent_snapshots("health", hours=1)
        if snapshots:
            latest = snapshots[-1]
            body_battery = latest.get("body_battery", {}).get("current")
        
        message = f"Stress elevated ({stress}) for {hours:.1f}h."
        if body_battery is not None and body_battery < 30:
            message += f" Body battery is also low ({body_battery}%). Consider rest."
        else:
            message += " A short break might help."
        
        return [Insight(
            type=InsightType.THRESHOLD,
            category=Category.HEALTH,
            priority=Priority.MEDIUM,
            title="Sustained elevated stress",
            message=message,
            dedupe_key=dedupe_key,
            data={
                "stress": stress,
                "duration_minutes": duration_minutes,
                "body_battery": body_battery,
            },
            expires_at=datetime.now(BRT) + timedelta(hours=2),
        )]
    
    def _generate_recovery_insight(self, current_stress: int) -> List[Insight]:
        """Generate a positive insight when stress recovers."""
        dedupe_key = "stress_recovery"
        
        # Only send recovery message once per 8 hours
        if self.was_insight_delivered_recently(dedupe_key, hours=8):
            return []
        
        # Also skip if we recently sent any stress alert (don't spam)
        if self.was_insight_delivered_recently("stress_high_sustained", hours=2):
            return []
        if self.was_insight_delivered_recently("stress_critical_sustained", hours=2):
            return []
        
        return [Insight(
            type=InsightType.STATUS,
            category=Category.HEALTH,
            priority=Priority.LOW,  # Low priority = batch for reports
            title="Stress recovered",
            message=f"Stress back to normal ({current_stress}). Good recovery!",
            dedupe_key=dedupe_key,
            data={"stress": current_stress},
            expires_at=datetime.now(BRT) + timedelta(hours=4),
        )]
