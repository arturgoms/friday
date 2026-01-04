"""
Friday Insights Engine - Calendar Analyzer

Analyzes calendar events to generate reminders and detect issues.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.config import get_brt
from src.insights.analyzers.base import RealTimeAnalyzer
from src.insights.config import InsightsConfig
from src.insights.models import (
    Category,
    Insight,
    InsightType,
    Priority,
)
from src.insights.store import InsightsStore

logger = logging.getLogger(__name__)


class CalendarAnalyzer(RealTimeAnalyzer):
    """
    Analyzes calendar events and generates reminders.

    Checks:
    - Upcoming events (15min, 1hr reminders)
    - Back-to-back meetings detection
    - Busy day warnings
    - Event conflicts (overlapping events)
    - Long meetings without breaks
    """

    # Reminder windows in minutes
    REMINDER_WINDOWS = [15, 60]  # 15 min and 1 hour before

    def __init__(self, config: InsightsConfig, store: InsightsStore):
        super().__init__("calendar_reminder", config, store)
        self._reminded_events: Dict[str, datetime] = {}  # event_id -> last reminded

    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Analyze calendar events and generate insights."""
        insights = []

        calendar = data.get("calendar", {})
        if not calendar:
            return insights

        # Handle both dict format (new) and list format (legacy)
        today_data = calendar.get("today", {})
        if isinstance(today_data, dict):
            today_events = today_data.get("events", [])
        else:
            today_events = today_data

        upcoming_data = calendar.get("upcoming", {})
        if isinstance(upcoming_data, dict):
            upcoming_events = upcoming_data.get("events", [])
        else:
            upcoming_events = upcoming_data

        all_events = today_events + upcoming_events

        if not all_events:
            return insights

        now = datetime.now(get_brt())

        # Normalize event format for analysis
        normalized_events = self._normalize_events(all_events)
        normalized_today = self._normalize_events(today_events)

        # Check for upcoming event reminders
        insights.extend(self._check_upcoming_reminders(normalized_events, now))

        # Check for busy day
        insights.extend(self._check_busy_day(normalized_today, now))

        # Check for back-to-back meetings
        insights.extend(self._check_back_to_back(normalized_today, now))

        # Check for conflicts
        insights.extend(self._check_conflicts(normalized_today))

        return insights

    def _check_upcoming_reminders(
        self,
        events: List[Dict[str, Any]],
        now: datetime
    ) -> List[Insight]:
        """Generate reminders for upcoming events."""
        insights = []

        for event in events:
            start_str = event.get("start")
            if not start_str:
                continue

            try:
                # Parse start time (handle both datetime and date strings)
                if "T" in start_str:
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=BRT)
                else:
                    # All-day event, skip reminders
                    continue
            except (ValueError, TypeError):
                continue

            # Calculate minutes until event
            delta = start - now
            minutes_until = delta.total_seconds() / 60

            # Skip past events
            if minutes_until < 0:
                continue

            # Check each reminder window
            for window in self.REMINDER_WINDOWS:
                # Check if we're within this window (with 5 min tolerance)
                if window - 5 <= minutes_until <= window + 5:
                    event_id = event.get("id", event.get("summary", "unknown"))
                    dedupe_key = f"event_reminder_{event_id}_{window}"

                    if not self.was_insight_delivered_recently(dedupe_key, hours=2):
                        title = event.get("summary", "Upcoming event")
                        location = event.get("location", "")

                        if window >= 60:
                            time_str = f"{window // 60} hour"
                        else:
                            time_str = f"{window} minutes"

                        message = f"{title} starts in {time_str}"
                        if location:
                            message += f" at {location}"

                        # Determine priority based on window
                        priority = Priority.HIGH if window <= 15 else Priority.MEDIUM

                        insights.append(Insight(
                            type=InsightType.REMINDER,
                            category=Category.CALENDAR,
                            priority=priority,
                            title=f"Reminder: {title}",
                            message=message,
                            dedupe_key=dedupe_key,
                            data={
                                "event": event,
                                "minutes_until": minutes_until,
                                "window": window,
                            },
                            expires_at=start,
                        ))
                        break  # Only one reminder per event

        return insights

    def _check_busy_day(
        self,
        today_events: List[Dict[str, Any]],
        now: datetime
    ) -> List[Insight]:
        """Warn about unusually busy days."""
        insights = []

        # Count meetings (exclude all-day events)
        meetings = [e for e in today_events if "T" in e.get("start", "")]

        if len(meetings) >= 5:
            dedupe_key = f"busy_day_{now.strftime('%Y-%m-%d')}"

            if not self.was_insight_delivered_recently(dedupe_key, hours=12):
                # Calculate total meeting time
                total_minutes = 0
                for event in meetings:
                    duration = self._get_event_duration(event)
                    if duration:
                        total_minutes += duration

                hours = total_minutes / 60

                insights.append(Insight(
                    type=InsightType.STATUS,
                    category=Category.CALENDAR,
                    priority=Priority.MEDIUM,
                    title="Busy day ahead",
                    message=f"You have {len(meetings)} meetings today ({hours:.1f}h total). Pace yourself!",
                    dedupe_key=dedupe_key,
                    data={
                        "meeting_count": len(meetings),
                        "total_hours": hours,
                    },
                    expires_at=datetime.now(get_brt()) + timedelta(hours=12),
                ))

        return insights

    def _check_back_to_back(
        self,
        today_events: List[Dict[str, Any]],
        now: datetime
    ) -> List[Insight]:
        """Detect back-to-back meetings without breaks."""
        insights = []

        # Get timed events sorted by start
        meetings = []
        for event in today_events:
            start_str = event.get("start", "")
            end_str = event.get("end", "")

            if "T" not in start_str:
                continue

            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=BRT)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=BRT)

                meetings.append({
                    "event": event,
                    "start": start,
                    "end": end,
                })
            except (ValueError, TypeError):
                continue

        # Sort by start time
        meetings.sort(key=lambda x: x["start"])

        # Find back-to-back sequences
        back_to_back_count = 0
        for i in range(len(meetings) - 1):
            current_end = meetings[i]["end"]
            next_start = meetings[i + 1]["start"]

            gap_minutes = (next_start - current_end).total_seconds() / 60

            # Less than 15 minutes between meetings
            if gap_minutes < 15:
                back_to_back_count += 1

        if back_to_back_count >= 2:
            dedupe_key = f"back_to_back_{now.strftime('%Y-%m-%d')}"

            if not self.was_insight_delivered_recently(dedupe_key, hours=12):
                insights.append(Insight(
                    type=InsightType.STATUS,
                    category=Category.CALENDAR,
                    priority=Priority.LOW,
                    title="Back-to-back meetings",
                    message=f"You have {back_to_back_count + 1} meetings with minimal breaks. Try to take short walks between.",
                    dedupe_key=dedupe_key,
                    data={"count": back_to_back_count},
                    expires_at=datetime.now(get_brt()) + timedelta(hours=8),
                ))

        return insights

    def _check_conflicts(
        self,
        today_events: List[Dict[str, Any]]
    ) -> List[Insight]:
        """Detect overlapping events (excludes all-day events)."""
        insights = []

        # Get timed events with parsed times (skip all-day events)
        meetings = []
        for event in today_events:
            # Skip all-day events - they don't create real conflicts
            if event.get("all_day"):
                continue

            start_str = event.get("start", "")
            end_str = event.get("end", "")

            # Also skip if no time component (date-only = all-day)
            if "T" not in start_str:
                continue

            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=BRT)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=BRT)

                meetings.append({
                    "event": event,
                    "start": start,
                    "end": end,
                })
            except (ValueError, TypeError):
                continue

        # Check for overlaps
        for i in range(len(meetings)):
            for j in range(i + 1, len(meetings)):
                m1, m2 = meetings[i], meetings[j]

                # Check if they overlap
                if m1["start"] < m2["end"] and m2["start"] < m1["end"]:
                    title1 = m1["event"].get("summary", "Event 1")
                    title2 = m2["event"].get("summary", "Event 2")

                    dedupe_key = f"conflict_{title1[:20]}_{title2[:20]}"

                    if not self.was_insight_delivered_recently(dedupe_key, hours=4):
                        # Format times for display (HH:MM)
                        time1 = m1["start"].strftime("%H:%M")
                        time2 = m2["start"].strftime("%H:%M")

                        insights.append(Insight(
                            type=InsightType.ANOMALY,
                            category=Category.CALENDAR,
                            priority=Priority.HIGH,
                            title="Calendar conflict",
                            message=f"{title1} ({time1}) overlaps with {title2} ({time2})",
                            dedupe_key=dedupe_key,
                            data={
                                "event1": m1["event"],
                                "event2": m2["event"],
                            },
                            expires_at=m2["end"],
                        ))

        return insights

    def _normalize_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize event format from collector to analyzer expectations.

        Handles field name differences:
        - Collector uses 'title', analyzer expects 'summary'
        """
        normalized = []
        for event in events:
            normalized.append({
                "summary": event.get("title", event.get("summary", "Untitled")),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
                "location": event.get("location", ""),
                "id": event.get("id", event.get("title", "unknown")),
                "all_day": event.get("all_day", False),
                "calendar": event.get("calendar", ""),
            })
        return normalized

    def _get_event_duration(self, event: Dict[str, Any]) -> Optional[int]:
        """Get event duration in minutes."""
        start_str = event.get("start", "")
        end_str = event.get("end", "")

        if not start_str or not end_str or "T" not in start_str:
            return None

        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            return int((end - start).total_seconds() / 60)
        except (ValueError, TypeError):
            return None
