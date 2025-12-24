"""
Friday Insights Engine - Resource Trend Analyzer

Analyzes disk, memory, and other resource trends to predict
when they might become critical.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging

from src.insights.analyzers.base import PeriodicAnalyzer
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


class ResourceTrendAnalyzer(PeriodicAnalyzer):
    """
    Analyzes resource usage trends and predicts future issues.
    
    Checks:
    - Disk usage growth rate → predict when full
    - Memory usage patterns → detect leaks
    - Service uptime patterns → predict failures
    
    Runs every 6 hours.
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        super().__init__("resource_trend", config, store, interval_hours=6)
    
    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Analyze resource trends and generate predictions."""
        insights = []
        
        # Get homelab data
        homelab = data.get("homelab", {})
        if not homelab:
            return insights
        
        # Analyze disk trends
        insights.extend(self._analyze_disk_trends(homelab))
        
        # Analyze memory patterns
        insights.extend(self._analyze_memory_trends(homelab))
        
        return insights
    
    def _analyze_disk_trends(self, homelab: Dict[str, Any]) -> List[Insight]:
        """Analyze disk usage trends across servers."""
        insights = []
        
        # Get historical homelab snapshots
        snapshots = self.get_recent_snapshots("homelab", hours=24*7)  # 1 week
        
        if len(snapshots) < 10:
            return insights
        
        # Track disk usage over time for each server
        disk_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        for snapshot in snapshots:
            timestamp = snapshot.get("collected_at")
            if not timestamp:
                continue
            
            try:
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except:
                continue
            
            # Local disk
            local = snapshot.get("local", {})
            local_disk = local.get("disk_percent")
            if local_disk is not None:
                if "local" not in disk_history:
                    disk_history["local"] = []
                disk_history["local"].append((ts, local_disk))
            
            # Server disks
            hardware = snapshot.get("hardware", {})
            for server in hardware.get("servers", []):
                name = server.get("name", "unknown")
                disk_pct = server.get("disk_percent")
                if disk_pct is not None:
                    if name not in disk_history:
                        disk_history[name] = []
                    disk_history[name].append((ts, disk_pct))
        
        # Analyze each server's disk trend
        for server_name, history in disk_history.items():
            if len(history) < 5:
                continue
            
            # Sort by timestamp
            history.sort(key=lambda x: x[0])
            
            # Calculate growth rate (percentage points per day)
            first_ts, first_val = history[0]
            last_ts, last_val = history[-1]
            
            days_elapsed = (last_ts - first_ts).total_seconds() / 86400
            if days_elapsed < 1:
                continue
            
            growth_rate = (last_val - first_val) / days_elapsed
            
            # Only alert if growing significantly (>0.5% per day)
            if growth_rate > 0.5:
                # Predict days until full
                remaining = 100 - last_val
                days_until_full = remaining / growth_rate if growth_rate > 0 else float('inf')
                
                # Get configured alert threshold
                alert_days = 30
                ana_config = self.config.analyzers.get("resource_trend")
                if ana_config and ana_config.alert_days:
                    alert_days = ana_config.alert_days
                
                if days_until_full <= alert_days:
                    dedupe_key = f"disk_trend_{server_name}"
                    if not self.was_insight_delivered_recently(dedupe_key, hours=48):
                        priority = Priority.HIGH if days_until_full <= 7 else Priority.MEDIUM
                        
                        insights.append(Insight(
                            type=InsightType.PREDICTION,
                            category=Category.HOMELAB,
                            priority=priority,
                            title=f"Disk filling up on {server_name}",
                            message=f"At current rate ({growth_rate:.1f}%/day), "
                                    f"disk will be full in ~{days_until_full:.0f} days. "
                                    f"Currently at {last_val:.1f}%.",
                            confidence=0.7,
                            dedupe_key=dedupe_key,
                            data={
                                "server": server_name,
                                "current_percent": last_val,
                                "growth_rate_per_day": growth_rate,
                                "days_until_full": days_until_full,
                            },
                            expires_at=datetime.now(BRT) + timedelta(days=2),
                        ))
        
        return insights
    
    def _analyze_memory_trends(self, homelab: Dict[str, Any]) -> List[Insight]:
        """Analyze memory usage patterns for potential leaks."""
        insights = []
        
        # Get recent snapshots (last 24 hours for memory analysis)
        snapshots = self.get_recent_snapshots("homelab", hours=24)
        
        if len(snapshots) < 20:
            return insights
        
        # Track memory over time
        memory_history: Dict[str, List[float]] = {}
        
        for snapshot in snapshots:
            # Local memory
            local = snapshot.get("local", {})
            mem = local.get("memory_percent")
            if mem is not None:
                if "local" not in memory_history:
                    memory_history["local"] = []
                memory_history["local"].append(mem)
            
            # Server memory
            hardware = snapshot.get("hardware", {})
            for server in hardware.get("servers", []):
                name = server.get("name", "unknown")
                mem_pct = server.get("memory_percent")
                if mem_pct is not None:
                    if name not in memory_history:
                        memory_history[name] = []
                    memory_history[name].append(mem_pct)
        
        # Check for consistently increasing memory (potential leak)
        for server_name, history in memory_history.items():
            if len(history) < 10:
                continue
            
            # Check if memory is consistently increasing
            increasing_count = 0
            for i in range(1, len(history)):
                if history[i] > history[i-1]:
                    increasing_count += 1
            
            increase_ratio = increasing_count / (len(history) - 1)
            
            # If >80% of samples show increase and current is high
            current_mem = history[-1]
            if increase_ratio > 0.8 and current_mem > 80:
                dedupe_key = f"memory_leak_{server_name}"
                if not self.was_insight_delivered_recently(dedupe_key, hours=24):
                    insights.append(Insight(
                        type=InsightType.ANOMALY,
                        category=Category.HOMELAB,
                        priority=Priority.MEDIUM,
                        title=f"Possible memory leak on {server_name}",
                        message=f"Memory has been consistently increasing (currently {current_mem:.1f}%). "
                                "Consider checking for runaway processes.",
                        confidence=0.6,
                        dedupe_key=dedupe_key,
                        data={
                            "server": server_name,
                            "current_percent": current_mem,
                            "increase_ratio": increase_ratio,
                            "samples": len(history),
                        },
                        expires_at=datetime.now(BRT) + timedelta(hours=12),
                    ))
        
        return insights
