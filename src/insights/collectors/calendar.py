"""
Friday Insights Engine - Calendar Collector

Collects calendar events from Nextcloud and Google Calendar.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from src.core.constants import BRT
from src.insights.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class CalendarCollector(BaseCollector):
    """
    Collects calendar events from Nextcloud (personal) and Google (work).
    
    Data collected:
    - Today's events
    - Tomorrow's events  
    - Upcoming events (next 7 days)
    - Meeting count and duration
    """
    
    def __init__(self):
        super().__init__("calendar")
        self._manager = None
    
    def initialize(self) -> bool:
        """Initialize calendar manager."""
        try:
            from src.tools.calendar import get_calendar_manager
            self._manager = get_calendar_manager()
            self._initialized = True
            logger.info("CalendarCollector initialized")
            return True
        except Exception as e:
            logger.error(f"CalendarCollector init failed: {e}")
            return False
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect calendar events."""
        if not self._manager:
            if not self.initialize():
                return None
        
        now = datetime.now(BRT)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        tomorrow_end = today_start + timedelta(days=2)
        week_end = today_start + timedelta(days=7)
        
        try:
            # Get events
            today_events = self._manager.get_all_events(today_start, today_end)
            tomorrow_events = self._manager.get_all_events(today_end, tomorrow_end)
            week_events = self._manager.get_all_events(today_start, week_end)
            
            # Analyze today
            today_data = self._analyze_day(today_events, "today")
            tomorrow_data = self._analyze_day(tomorrow_events, "tomorrow")
            
            # Find upcoming important events
            upcoming = self._get_upcoming_soon(today_events, now)
            
            # Week summary
            week_summary = self._analyze_week(week_events)
            
            return {
                "collected_at": now.isoformat(),
                "today": today_data,
                "tomorrow": tomorrow_data,
                "week_summary": week_summary,
                "upcoming_soon": upcoming,
            }
            
        except Exception as e:
            logger.error(f"Calendar collection failed: {e}")
            return None
    
    def _analyze_day(self, events: List, day_name: str) -> Dict[str, Any]:
        """Analyze events for a single day."""
        if not events:
            return {
                "event_count": 0,
                "meeting_count": 0,
                "meeting_hours": 0,
                "has_conflicts": False,
                "events": [],
            }
        
        meetings = [e for e in events if not e.all_day]
        all_day = [e for e in events if e.all_day]
        
        # Calculate meeting time
        total_minutes = 0
        for m in meetings:
            duration = (m.end - m.start).total_seconds() / 60
            total_minutes += duration
        
        # Check for conflicts
        has_conflicts = self._check_conflicts(meetings)
        
        # Build event list
        event_list = []
        for e in events:
            event_list.append({
                "title": e.title,
                "start": e.start.isoformat() if hasattr(e.start, 'isoformat') else str(e.start),
                "end": e.end.isoformat() if hasattr(e.end, 'isoformat') else str(e.end),
                "calendar": e.calendar,
                "all_day": e.all_day,
                "location": getattr(e, 'location', ''),
            })
        
        return {
            "event_count": len(events),
            "meeting_count": len(meetings),
            "all_day_count": len(all_day),
            "meeting_hours": round(total_minutes / 60, 1),
            "has_conflicts": has_conflicts,
            "events": event_list,
        }
    
    def _check_conflicts(self, meetings: List) -> bool:
        """Check if any meetings overlap."""
        if len(meetings) < 2:
            return False
        
        # Sort by start time
        sorted_meetings = sorted(meetings, key=lambda m: m.start)
        
        for i in range(len(sorted_meetings) - 1):
            current = sorted_meetings[i]
            next_meeting = sorted_meetings[i + 1]
            
            # Check if current ends after next starts
            if current.end > next_meeting.start:
                return True
        
        return False
    
    def _get_upcoming_soon(self, today_events: List, now: datetime) -> List[Dict]:
        """Get events happening in the next 30 minutes."""
        upcoming = []
        
        for event in today_events:
            if event.all_day:
                continue
            
            # Calculate minutes until event
            if hasattr(event.start, 'tzinfo') and event.start.tzinfo:
                start = event.start
            else:
                start = event.start.replace(tzinfo=BRT)
            
            if now.tzinfo is None:
                now = now.replace(tzinfo=BRT)
            
            minutes_until = (start - now).total_seconds() / 60
            
            if 0 < minutes_until <= 30:
                upcoming.append({
                    "title": event.title,
                    "minutes_until": int(minutes_until),
                    "calendar": event.calendar,
                    "location": getattr(event, 'location', ''),
                })
        
        return sorted(upcoming, key=lambda x: x["minutes_until"])
    
    def _analyze_week(self, events: List) -> Dict[str, Any]:
        """Analyze the week's events."""
        if not events:
            return {"total_events": 0, "total_meeting_hours": 0, "busiest_day": None}
        
        # Count by day
        day_counts = {}
        day_minutes = {}
        
        for event in events:
            if event.all_day:
                continue
            
            day = event.start.strftime("%A")
            day_counts[day] = day_counts.get(day, 0) + 1
            
            duration = (event.end - event.start).total_seconds() / 60
            day_minutes[day] = day_minutes.get(day, 0) + duration
        
        # Find busiest day
        busiest_day = max(day_minutes.keys(), key=lambda d: day_minutes[d]) if day_minutes else None
        
        total_minutes = sum(day_minutes.values())
        
        return {
            "total_events": len(events),
            "total_meetings": sum(day_counts.values()),
            "total_meeting_hours": round(total_minutes / 60, 1),
            "busiest_day": busiest_day,
            "busiest_day_hours": round(day_minutes.get(busiest_day, 0) / 60, 1) if busiest_day else 0,
            "meetings_by_day": day_counts,
        }
