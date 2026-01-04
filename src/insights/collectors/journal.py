"""
Friday Insights Engine - Journal Collector

Collects all data needed for the daily journal note:
- Journal entries (text and voice)
- Calendar events
- Weather data
- Health summary with anomalies
"""

import logging
from datetime import datetime, timedelta, date as date_type
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from src.core.config import get_brt
from src.insights.collectors.base import BaseCollector
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


@dataclass
class JournalEntry:
    """A single journal entry."""
    timestamp: datetime
    entry_type: str  # 'text' or 'voice'
    content: str


@dataclass
class CalendarEvent:
    """A calendar event."""
    start: datetime
    end: datetime
    title: str
    calendar: str


@dataclass
class WeatherData:
    """Weather information for the day."""
    summary: str
    temp_high: Optional[float]
    temp_low: Optional[float]
    conditions: str


@dataclass
class HealthSummary:
    """Health metrics summary with anomalies."""
    sleep_hours: Optional[float]
    sleep_score: Optional[int]
    body_battery_start: Optional[int]
    body_battery_end: Optional[int]
    avg_stress: Optional[int]
    steps: Optional[int]
    activities: List[str]
    anomalies: List[str]  # Descriptions of what's unusual


@dataclass
class JournalSnapshot:
    """Complete snapshot for daily journal processing."""
    date: str  # YYYY-MM-DD
    entries: List[JournalEntry]
    calendar_events: List[CalendarEvent]
    weather: Optional[WeatherData]
    health: Optional[HealthSummary]


class JournalCollector(BaseCollector):
    """
    Collects all data for the daily journal.
    
    This runs once per day at 23:59 to gather everything
    needed to generate the daily note.
    """
    
    def __init__(self, store: Optional[InsightsStore] = None):
        super().__init__("journal")
        self.store = store or InsightsStore()
    
    def collect(self, target_date: Optional[date_type] = None) -> Optional[Dict[str, Any]]:
        """Collect all data for a specific date.
        
        Args:
            target_date: Date to collect for. If None, uses today.
            
        Returns:
            Dict with journal snapshot data
        """
        if target_date is None:
            target_date = datetime.now(get_brt()).date()
        
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info(f"[JOURNAL_COLLECTOR] Collecting data for {date_str}")
        
        # Collect all components
        entries = self._collect_entries(date_str)
        calendar_events = self._collect_calendar_events(target_date)
        weather = self._collect_weather(target_date)
        health = self._collect_health(target_date)
        
        # Build snapshot
        snapshot = JournalSnapshot(
            date=date_str,
            entries=entries,
            calendar_events=calendar_events,
            weather=weather,
            health=health
        )
        
        # Convert to dict for storage
        data = {
            "date": snapshot.date,
            "entries": [asdict(e) for e in snapshot.entries],
            "calendar_events": [asdict(e) for e in snapshot.calendar_events],
            "weather": asdict(snapshot.weather) if snapshot.weather else None,
            "health": asdict(snapshot.health) if snapshot.health else None,
            "entry_count": len(snapshot.entries),
            "event_count": len(snapshot.calendar_events),
        }
        
        logger.info(f"[JOURNAL_COLLECTOR] Collected {len(entries)} entries, {len(calendar_events)} events for {date_str}")
        return data
    
    def _collect_entries(self, date_str: str) -> List[JournalEntry]:
        """Get journal entries for the date."""
        try:
            raw_entries = self.store.get_journal_entries(date_str)
            return [
                JournalEntry(
                    timestamp=e["timestamp"],
                    entry_type=e["entry_type"],
                    content=e["content"]
                )
                for e in raw_entries
            ]
        except Exception as e:
            logger.error(f"[JOURNAL_COLLECTOR] Error getting entries: {e}")
            return []
    
    def _collect_calendar_events(self, target_date: date_type) -> List[CalendarEvent]:
        """Get calendar events for the date."""
        try:
            # Get calendar snapshots from the store
            date_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=BRT)
            date_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=BRT)
            
            # Get snapshots from calendar collector for this day
            snapshots = self.store.get_snapshots(
                collector="calendar",
                since=date_start,
                until=date_end,
                limit=50
            )
            
            events = []
            seen_events = set()
            
            for snapshot in snapshots:
                # Calendar data is nested under "today", "tomorrow", etc.
                # For the target date, we want "today" key
                today_data = snapshot.data.get("today", {})
                snapshot_events = today_data.get("events", [])
                
                for event in snapshot_events:
                    # Deduplicate by event ID or title+start time
                    event_key = f"{event.get('title', '')}_{event.get('start', '')}"
                    if event_key in seen_events:
                        continue
                    seen_events.add(event_key)
                    
                    try:
                        start = datetime.fromisoformat(event.get("start", ""))
                        end = datetime.fromisoformat(event.get("end", ""))
                        
                        # Skip all-day events (like "Home")
                        if event.get("all_day", False):
                            continue
                        
                        # Only include events on the target date
                        if start.date() == target_date:
                            events.append(CalendarEvent(
                                start=start,
                                end=end,
                                title=event.get("title", "Untitled"),
                                calendar=event.get("calendar", "")
                            ))
                    except Exception as e:
                        logger.debug(f"Skipping event due to parsing error: {e}")
                        continue
            
            # Sort by start time
            events.sort(key=lambda e: e.start)
            return events
            
        except Exception as e:
            logger.error(f"[JOURNAL_COLLECTOR] Error getting calendar events: {e}")
            return []
    
    def _collect_weather(self, target_date: date_type) -> Optional[WeatherData]:
        """Get weather data for the date."""
        try:
            # Get weather snapshots for the day
            date_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=BRT)
            date_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=BRT)
            
            snapshots = self.store.get_snapshots(
                collector="weather",
                since=date_start,
                until=date_end,
                limit=10
            )
            
            if not snapshots:
                return None
            
            # Use the most recent snapshot
            latest = snapshots[0]
            data = latest.data
            
            current = data.get("current", {})
            rain = data.get("rain", {})
            
            # Build description
            condition = current.get("condition", "Unknown")
            temp = current.get("temp")
            
            # Create summary
            summary = condition.capitalize() if condition else "Unknown conditions"
            if temp:
                summary = f"{summary} with {temp}°C"
            
            return WeatherData(
                summary=summary,
                temp_high=temp,  # Current temp as high
                temp_low=None,
                conditions=condition
            )
            
        except Exception as e:
            logger.error(f"[JOURNAL_COLLECTOR] Error getting weather: {e}")
            return None
    
    def _collect_health(self, target_date: date_type) -> Optional[HealthSummary]:
        """Get health summary with anomalies for the date."""
        try:
            # Get health snapshots for the day
            date_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=BRT)
            date_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=BRT)
            
            snapshots = self.store.get_snapshots(
                collector="health",
                since=date_start,
                until=date_end,
                limit=50
            )
            
            if not snapshots:
                return None
            
            # Get the last snapshot of the day for current state
            latest = snapshots[0]
            data = latest.data
            
            # Extract metrics
            sleep_data = data.get("sleep", {})
            daily_stats = data.get("daily_stats", {})
            body_battery = data.get("body_battery", {})
            stress_data = data.get("stress", {})
            
            # Sleep: try both duration_hours and total_hours
            sleep_hours = sleep_data.get("duration_hours") or sleep_data.get("total_hours")
            sleep_score = sleep_data.get("score")
            
            # Body battery
            body_battery_end = body_battery.get("current")
            
            # Stress: get current or calculate average from historical data
            avg_stress = stress_data.get("current")
            
            # Steps
            steps = daily_stats.get("steps")
            
            # Get body battery start (from wake_body_battery or first snapshot)
            body_battery_start = daily_stats.get("wake_body_battery")
            if not body_battery_start and len(snapshots) > 0:
                first_snapshot = snapshots[-1]  # Oldest first
                body_battery_start = first_snapshot.data.get("body_battery", {}).get("current")
            
            # Get activities
            activities = daily_stats.get("activities", [])
            activity_names = [a.get("name", "") for a in activities if a.get("name")]
            
            # Detect anomalies by comparing to 7-day average
            anomalies = []
            anomalies.extend(self._detect_health_anomalies(
                target_date=target_date,
                sleep_hours=sleep_hours,
                sleep_score=sleep_score,
                avg_stress=avg_stress,
                steps=steps
            ))
            
            return HealthSummary(
                sleep_hours=sleep_hours,
                sleep_score=sleep_score,
                body_battery_start=body_battery_start,
                body_battery_end=body_battery_end,
                avg_stress=avg_stress,
                steps=steps,
                activities=activity_names,
                anomalies=anomalies
            )
            
        except Exception as e:
            logger.error(f"[JOURNAL_COLLECTOR] Error getting health data: {e}")
            return None
    
    def _detect_health_anomalies(
        self,
        target_date: date_type,
        sleep_hours: Optional[float],
        sleep_score: Optional[int],
        avg_stress: Optional[int],
        steps: Optional[int]
    ) -> List[str]:
        """Detect anomalies by comparing to 7-day baseline."""
        anomalies = []
        
        try:
            # Get snapshots from the past 7 days (excluding today)
            end_date = target_date - timedelta(days=1)
            start_date = end_date - timedelta(days=6)
            
            date_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=BRT)
            date_end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=BRT)
            
            historical_snapshots = self.store.get_snapshots(
                collector="health",
                since=date_start,
                until=date_end,
                limit=500
            )
            
            if len(historical_snapshots) < 7:
                # Not enough data for comparison
                return anomalies
            
            # Calculate averages
            sleep_hours_list = []
            sleep_score_list = []
            stress_list = []
            steps_list = []
            
            for snapshot in historical_snapshots:
                data = snapshot.data
                sleep = data.get("sleep", {})
                daily = data.get("daily_stats", {})
                
                if sleep.get("duration_hours"):
                    sleep_hours_list.append(sleep["duration_hours"])
                if sleep.get("score"):
                    sleep_score_list.append(sleep["score"])
                if daily.get("avg_stress"):
                    stress_list.append(daily["avg_stress"])
                if daily.get("steps"):
                    steps_list.append(daily["steps"])
            
            # Compare to averages (with thresholds)
            if sleep_hours and sleep_hours_list:
                avg_sleep = sum(sleep_hours_list) / len(sleep_hours_list)
                if sleep_hours < avg_sleep - 1.5:
                    anomalies.append(f"Sleep below average ({sleep_hours:.1f}h vs {avg_sleep:.1f}h)")
                elif sleep_hours > avg_sleep + 1.5:
                    anomalies.append(f"Sleep above average ({sleep_hours:.1f}h vs {avg_sleep:.1f}h)")
            
            if sleep_score and sleep_score_list:
                avg_score = sum(sleep_score_list) / len(sleep_score_list)
                if sleep_score < avg_score - 15:
                    anomalies.append(f"Sleep quality low (score {sleep_score} vs {int(avg_score)} avg)")
            
            if avg_stress and stress_list:
                avg_stress_baseline = sum(stress_list) / len(stress_list)
                if avg_stress > avg_stress_baseline + 15:
                    anomalies.append(f"Stress elevated ({avg_stress} vs {int(avg_stress_baseline)} avg)")
            
            if steps and steps_list:
                avg_steps = sum(steps_list) / len(steps_list)
                if steps < avg_steps * 0.5:
                    anomalies.append(f"Steps low ({steps} vs {int(avg_steps)} avg)")
                elif steps > avg_steps * 1.5:
                    anomalies.append(f"Steps high ({steps} vs {int(avg_steps)} avg)")
            
        except Exception as e:
            logger.error(f"[JOURNAL_COLLECTOR] Error detecting anomalies: {e}")
        
        return anomalies
