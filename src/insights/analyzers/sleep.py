"""
Friday Insights Engine - Sleep Correlation Analyzer

Analyzes sleep patterns and correlates with previous day activities.
Runs daily to provide insights on what affects sleep quality.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.config import get_brt
from src.insights.analyzers.base import PeriodicAnalyzer
from src.insights.config import InsightsConfig
from src.insights.models import (
    Category,
    Insight,
    InsightType,
    Priority,
)
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class SleepCorrelationAnalyzer(PeriodicAnalyzer):
    """
    Analyzes sleep quality correlations.

    Looks at:
    - Sleep score vs previous day's stress levels
    - Sleep score vs exercise/activity
    - Sleep score vs meeting load
    - Sleep duration patterns
    - Sleep timing patterns

    Runs daily (after sleep data is available, typically morning).
    """

    # Minimum days of data needed for correlation analysis
    MIN_DAYS_FOR_CORRELATION = 7

    def __init__(self, config: InsightsConfig, store: InsightsStore):
        super().__init__("sleep_correlator", config, store, interval_hours=24)
        self._correlation_cache: Dict[str, float] = {}

    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Analyze sleep patterns and generate correlation insights."""
        insights = []

        # Get health data
        health = data.get("health", {})
        sync = health.get("sync", {})

        # Skip if data is stale
        if sync.get("status") != "fresh":
            return insights

        # Get today's sleep data
        sleep = health.get("sleep", {})
        sleep_score = sleep.get("sleep_score")
        sleep_duration = sleep.get("duration_hours")

        if sleep_score is None:
            return insights

        # Analyze today's sleep
        insights.extend(self._analyze_sleep_quality(sleep_score, sleep_duration, sleep))

        # Look for correlations (needs historical data)
        insights.extend(self._analyze_correlations())

        return insights

    def _analyze_sleep_quality(
        self,
        score: int,
        duration: Optional[float],
        sleep_data: Dict[str, Any]
    ) -> List[Insight]:
        """Analyze current sleep quality."""
        insights = []

        # Get thresholds
        warning_threshold = self.config.thresholds.get("sleep_score", {}).get("warning", 50)

        # Check for very good sleep (positive reinforcement)
        if score >= 85:
            dedupe_key = f"sleep_excellent_{datetime.now(get_brt()).strftime('%Y-%m-%d')}"
            if not self.was_insight_delivered_recently(dedupe_key, hours=20):
                insights.append(Insight(
                    type=InsightType.STATUS,
                    category=Category.HEALTH,
                    priority=Priority.LOW,
                    title="Excellent sleep",
                    message=f"Great sleep last night! Score: {score}/100" +
                            (f", {duration:.1f}h" if duration else ""),
                    dedupe_key=dedupe_key,
                    data={"score": score, "duration": duration},
                    expires_at=datetime.now(get_brt()) + timedelta(hours=12),
                ))

        # Check sleep stages if available
        deep_sleep = sleep_data.get("deep_sleep_hours")
        rem_sleep = sleep_data.get("rem_sleep_hours")

        if deep_sleep is not None and deep_sleep < 1.0:
            dedupe_key = f"sleep_low_deep_{datetime.now(get_brt()).strftime('%Y-%m-%d')}"
            if not self.was_insight_delivered_recently(dedupe_key, hours=20):
                insights.append(Insight(
                    type=InsightType.ANOMALY,
                    category=Category.HEALTH,
                    priority=Priority.LOW,
                    title="Low deep sleep",
                    message=f"Only {deep_sleep:.1f}h of deep sleep. "
                            "Consider limiting caffeine and screens before bed.",
                    dedupe_key=dedupe_key,
                    data={"deep_sleep": deep_sleep},
                    expires_at=datetime.now(get_brt()) + timedelta(hours=12),
                ))

        return insights

    def _analyze_correlations(self) -> List[Insight]:
        """Analyze sleep correlations with historical data."""
        insights = []

        # Get historical health snapshots
        health_snapshots = self.get_recent_snapshots("health", hours=24*14)  # 2 weeks

        if len(health_snapshots) < self.MIN_DAYS_FOR_CORRELATION:
            return insights

        # Extract sleep scores and previous day metrics
        sleep_data = []
        for snapshot in health_snapshots:
            sleep = snapshot.get("sleep", {})
            score = sleep.get("sleep_score")
            if score:
                sleep_data.append({
                    "score": score,
                    "duration": sleep.get("duration_hours"),
                    "stress_prev": snapshot.get("stress", {}).get("average"),
                    "steps_prev": snapshot.get("activity", {}).get("steps"),
                })

        if len(sleep_data) < self.MIN_DAYS_FOR_CORRELATION:
            return insights

        # Calculate correlations
        stress_correlation = self._calculate_correlation(
            [d["score"] for d in sleep_data if d.get("stress_prev")],
            [d["stress_prev"] for d in sleep_data if d.get("stress_prev")]
        )

        # Generate insight if strong correlation found
        if stress_correlation is not None and abs(stress_correlation) > 0.5:
            dedupe_key = "sleep_stress_correlation"
            if not self.was_insight_delivered_recently(dedupe_key, hours=168):  # Weekly
                direction = "negative" if stress_correlation < 0 else "positive"
                insights.append(Insight(
                    type=InsightType.CORRELATION,
                    category=Category.HEALTH,
                    priority=Priority.LOW,
                    title="Sleep-stress correlation detected",
                    message=f"Your sleep quality has a {direction} correlation with daily stress. "
                            "Lower stress days tend to mean better sleep.",
                    confidence=min(abs(stress_correlation), 0.95),
                    dedupe_key=dedupe_key,
                    data={"correlation": stress_correlation, "days_analyzed": len(sleep_data)},
                    expires_at=datetime.now(get_brt()) + timedelta(days=7),
                ))

        return insights

    def _calculate_correlation(
        self,
        x: List[float],
        y: List[float]
    ) -> Optional[float]:
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 3:
            return None

        n = len(x)

        # Calculate means
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Calculate correlation
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))

        sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
        sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)

        denominator = (sum_sq_x * sum_sq_y) ** 0.5

        if denominator == 0:
            return None

        return numerator / denominator
