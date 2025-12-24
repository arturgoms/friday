"""
Friday 3.0 Calendar Sensor

Monitors upcoming events and alerts before they start.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from src.core.constants import BRT
from src.core.registry import friday_sensor

logger = logging.getLogger(__name__)

# Alert thresholds (minutes before event)
ALERT_THRESHOLDS = [15, 5]  # Alert 15 min and 5 min before


@friday_sensor(name="upcoming_events", interval_seconds=300)  # Check every 5 minutes
def check_upcoming_events() -> Dict[str, Any]:
    """Check for events starting soon.
    
    Alerts when events are about to start (15 min and 5 min before).
    
    Returns:
        Dictionary with upcoming event info
    """
    try:
        from src.tools.calendar import get_calendar_manager
        
        manager = get_calendar_manager()
        now = datetime.now(BRT)
        
        # Look ahead 30 minutes
        end = now + timedelta(minutes=30)
        
        events = manager.get_all_events(now, end)
        
        if not events:
            return {
                "sensor": "upcoming_events",
                "status": "clear",
                "events_soon": [],
                "next_event": None
            }
        
        events_soon = []
        
        for event in events:
            if event.all_day:
                continue
                
            minutes_until = (event.start - now).total_seconds() / 60
            
            # Only include events starting in the next 20 minutes
            if 0 < minutes_until <= 20:
                events_soon.append({
                    "title": event.title,
                    "calendar": event.calendar,
                    "start": event.start.isoformat(),
                    "minutes_until": round(minutes_until),
                    "location": event.location
                })
        
        # Get next event info
        next_event = None
        for event in events:
            if not event.all_day and event.start > now:
                next_event = {
                    "title": event.title,
                    "calendar": event.calendar,
                    "start": event.start.isoformat(),
                    "minutes_until": round((event.start - now).total_seconds() / 60)
                }
                break
        
        return {
            "sensor": "upcoming_events",
            "status": "alert" if events_soon else "clear",
            "events_soon": events_soon,
            "next_event": next_event
        }
        
    except Exception as e:
        logger.error(f"Calendar sensor error: {e}")
        return {
            "sensor": "upcoming_events",
            "error": str(e)
        }


@friday_sensor(name="daily_agenda", interval_seconds=3600)  # Check every hour
def check_daily_agenda() -> Dict[str, Any]:
    """Get summary of today's remaining events.
    
    Returns:
        Dictionary with today's agenda
    """
    try:
        from src.tools.calendar import get_calendar_manager
        
        manager = get_calendar_manager()
        now = datetime.now(BRT)
        
        # Get events for rest of today
        end = now.replace(hour=23, minute=59, second=59)
        
        events = manager.get_all_events(now, end)
        
        # Count by calendar
        personal_count = sum(1 for e in events if e.calendar == "personal")
        work_count = sum(1 for e in events if e.calendar == "work")
        
        return {
            "sensor": "daily_agenda",
            "total_events": len(events),
            "personal_events": personal_count,
            "work_events": work_count,
            "events": [
                {
                    "title": e.title,
                    "calendar": e.calendar,
                    "start": e.start.strftime("%H:%M"),
                    "end": e.end.strftime("%H:%M") if not e.all_day else "all-day"
                }
                for e in events[:10]  # Limit to 10
            ]
        }
        
    except Exception as e:
        logger.error(f"Daily agenda sensor error: {e}")
        return {
            "sensor": "daily_agenda",
            "error": str(e)
        }
