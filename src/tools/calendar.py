"""
Friday 3.0 Calendar Tools

Unified calendar management for:
- Personal calendar (Nextcloud CalDAV)
- Work calendar (Google Calendar)

Features:
- View upcoming events
- Add/edit/delete events
- Find free time slots
- Cross-calendar availability check
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import json
import logging
import os
import pickle
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from settings import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = settings.PATHS["data"]

# Nextcloud CalDAV config
NEXTCLOUD_CALDAV_URL = settings.NEXTCLOUD_CALDAV_URL
NEXTCLOUD_USERNAME = settings.NEXTCLOUD_USERNAME
NEXTCLOUD_PASSWORD = settings.NEXTCLOUD_PASSWORD

# Google Calendar config
GOOGLE_CREDENTIALS_FILE = DATA_DIR / "google_credentials.json"
GOOGLE_TOKEN_FILE = DATA_DIR / "google_token.pickle"
GOOGLE_CALENDAR_ID = settings.GOOGLE_CALENDAR_ID

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CalendarEvent:
    """Unified event representation."""
    id: str
    title: str
    start: datetime
    end: datetime
    calendar: str  # "personal" or "work"
    description: str = ""
    location: str = ""
    all_day: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "calendar": self.calendar,
            "description": self.description,
            "location": self.location,
            "all_day": self.all_day,
        }
    
    def format_short(self) -> str:
        """Short format for listing."""
        if self.all_day:
            time_str = "All day"
        else:
            time_str = f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"
        cal_icon = "🏠" if self.calendar == "personal" else "💼"
        return f"{cal_icon} {time_str}: {self.title}"
    
    def format_full(self) -> str:
        """Full format with details."""
        lines = [f"📅 {self.title}"]
        lines.append(f"   Calendar: {'Personal' if self.calendar == 'personal' else 'Work'}")
        if self.all_day:
            lines.append(f"   Date: {self.start.strftime('%Y-%m-%d')} (All day)")
        else:
            if self.start.date() == self.end.date():
                lines.append(f"   Time: {self.start.strftime('%Y-%m-%d %H:%M')} - {self.end.strftime('%H:%M')}")
            else:
                lines.append(f"   Start: {self.start.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"   End: {self.end.strftime('%Y-%m-%d %H:%M')}")
        if self.location:
            lines.append(f"   Location: {self.location}")
        if self.description:
            lines.append(f"   Description: {self.description[:100]}...")
        return "\n".join(lines)


# =============================================================================
# Nextcloud CalDAV Client
# =============================================================================

class NextcloudCalendar:
    """Nextcloud CalDAV calendar client."""
    
    def __init__(self):
        self.url = NEXTCLOUD_CALDAV_URL
        self.username = NEXTCLOUD_USERNAME
        self.password = NEXTCLOUD_PASSWORD
        self._client = None
        self._calendar = None
    
    def _connect(self):
        """Connect to Nextcloud CalDAV."""
        if self._calendar is not None:
            return self._calendar
        
        try:
            import caldav
            
            self._client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password
            )
            
            # Get the calendar directly from URL
            self._calendar = caldav.Calendar(client=self._client, url=self.url)
            return self._calendar
            
        except Exception as e:
            logger.error(f"Failed to connect to Nextcloud: {e}")
            raise
    
    def get_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        """Get events in date range."""
        try:
            calendar = self._connect()
            events = calendar.search(
                start=start,
                end=end,
                event=True,
                expand=True
            )
            
            result = []
            for event in events:
                try:
                    vevent = event.vobject_instance.vevent
                    
                    # Parse start/end times
                    dtstart = vevent.dtstart.value
                    dtend = vevent.dtend.value if hasattr(vevent, 'dtend') else dtstart + timedelta(hours=1)
                    
                    # Check if all-day event
                    all_day = not isinstance(dtstart, datetime)
                    
                    if all_day:
                        dtstart = datetime.combine(dtstart, datetime.min.time()).replace(tzinfo=settings.TIMEZONE)
                        dtend = datetime.combine(dtend, datetime.min.time()).replace(tzinfo=settings.TIMEZONE)
                    else:
                        if dtstart.tzinfo is None:
                            dtstart = dtstart.replace(tzinfo=settings.TIMEZONE)
                        if dtend.tzinfo is None:
                            dtend = dtend.replace(tzinfo=settings.TIMEZONE)
                    
                    result.append(CalendarEvent(
                        id=str(event.url),
                        title=str(vevent.summary.value) if hasattr(vevent, 'summary') else "No title",
                        start=dtstart,
                        end=dtend,
                        calendar="personal",
                        description=str(vevent.description.value) if hasattr(vevent, 'description') else "",
                        location=str(vevent.location.value) if hasattr(vevent, 'location') else "",
                        all_day=all_day
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse event: {e}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Nextcloud events: {e}")
            return []
    
    def add_event(self, title: str, start: datetime, end: datetime, 
                  description: str = "", location: str = "") -> Optional[str]:
        """Add a new event."""
        try:
            calendar = self._connect()
            
            # Create iCal event
            from icalendar import Calendar as iCalendar, Event as iEvent
            import uuid
            
            cal = iCalendar()
            cal.add('prodid', '-//Friday AI Assistant//EN')
            cal.add('version', '2.0')
            
            event = iEvent()
            event.add('uid', str(uuid.uuid4()))
            event.add('summary', title)
            event.add('dtstart', start)
            event.add('dtend', end)
            if description:
                event.add('description', description)
            if location:
                event.add('location', location)
            event.add('dtstamp', datetime.now(timezone.utc))
            
            cal.add_component(event)
            
            # Save to calendar
            calendar.save_event(cal.to_ical().decode('utf-8'))
            
            return event['uid']
            
        except Exception as e:
            logger.error(f"Failed to add Nextcloud event: {e}")
            return None
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID (URL)."""
        try:
            import caldav
            calendar = self._connect()
            event = caldav.Event(client=self._client, url=event_id, parent=calendar)
            event.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False


# =============================================================================
# Google Calendar Client
# =============================================================================

class GoogleCalendar:
    """Google Calendar API client."""
    
    def __init__(self):
        self.calendar_id = GOOGLE_CALENDAR_ID
        self._service = None
    
    def _connect(self):
        """Connect to Google Calendar API."""
        if self._service is not None:
            return self._service
        
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            
            creds = None
            
            # Load saved credentials
            if GOOGLE_TOKEN_FILE.exists():
                with open(GOOGLE_TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not GOOGLE_CREDENTIALS_FILE.exists():
                        raise FileNotFoundError(f"Google credentials not found at {GOOGLE_CREDENTIALS_FILE}")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(GOOGLE_CREDENTIALS_FILE), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save credentials
                with open(GOOGLE_TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
            
            self._service = build('calendar', 'v3', credentials=creds)
            return self._service
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Calendar: {e}")
            raise
    
    def get_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        """Get events in date range."""
        try:
            service = self._connect()
            
            events_result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            result = []
            for event in events:
                try:
                    # Parse start/end
                    start_data = event.get('start', {})
                    end_data = event.get('end', {})
                    
                    all_day = 'date' in start_data
                    
                    if all_day:
                        dtstart = datetime.fromisoformat(start_data['date'])
                        dtstart = datetime.combine(dtstart.date(), datetime.min.time()).replace(tzinfo=settings.TIMEZONE)
                        dtend = datetime.fromisoformat(end_data['date'])
                        dtend = datetime.combine(dtend.date(), datetime.min.time()).replace(tzinfo=settings.TIMEZONE)
                    else:
                        dtstart = datetime.fromisoformat(start_data['dateTime'].replace('Z', '+00:00'))
                        dtend = datetime.fromisoformat(end_data['dateTime'].replace('Z', '+00:00'))
                    
                    result.append(CalendarEvent(
                        id=event['id'],
                        title=event.get('summary', 'No title'),
                        start=dtstart,
                        end=dtend,
                        calendar="work",
                        description=event.get('description', ''),
                        location=event.get('location', ''),
                        all_day=all_day
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse Google event: {e}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Google events: {e}")
            return []
    
    def add_event(self, title: str, start: datetime, end: datetime,
                  description: str = "", location: str = "") -> Optional[str]:
        """Add a new event."""
        try:
            service = self._connect()
            
            event = {
                'summary': title,
                'start': {'dateTime': start.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'America/Sao_Paulo'},
            }
            
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            
            result = service.events().insert(calendarId=self.calendar_id, body=event).execute()
            return result.get('id')
            
        except Exception as e:
            logger.error(f"Failed to add Google event: {e}")
            return None
    
    def update_event(self, event_id: str, **kwargs) -> bool:
        """Update an existing event."""
        try:
            service = self._connect()
            
            # Get existing event
            event = service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
            
            # Update fields
            if 'title' in kwargs:
                event['summary'] = kwargs['title']
            if 'start' in kwargs:
                event['start'] = {'dateTime': kwargs['start'].isoformat(), 'timeZone': 'America/Sao_Paulo'}
            if 'end' in kwargs:
                event['end'] = {'dateTime': kwargs['end'].isoformat(), 'timeZone': 'America/Sao_Paulo'}
            if 'description' in kwargs:
                event['description'] = kwargs['description']
            if 'location' in kwargs:
                event['location'] = kwargs['location']
            
            service.events().update(calendarId=self.calendar_id, eventId=event_id, body=event).execute()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Google event: {e}")
            return False
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        try:
            service = self._connect()
            service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete Google event: {e}")
            return False


# =============================================================================
# Unified Calendar Manager
# =============================================================================

class CalendarManager:
    """Unified calendar manager for both personal and work calendars."""
    
    def __init__(self):
        self._nextcloud = None
        self._google = None
    
    @property
    def nextcloud(self) -> NextcloudCalendar:
        if self._nextcloud is None:
            self._nextcloud = NextcloudCalendar()
        return self._nextcloud
    
    @property
    def google(self) -> GoogleCalendar:
        if self._google is None:
            self._google = GoogleCalendar()
        return self._google
    
    def get_all_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        """Get events from both calendars."""
        events = []
        
        # Get personal events
        try:
            events.extend(self.nextcloud.get_events(start, end))
        except Exception as e:
            logger.warning(f"Failed to get personal events: {e}")
        
        # Get work events
        try:
            events.extend(self.google.get_events(start, end))
        except Exception as e:
            logger.warning(f"Failed to get work events: {e}")
        
        # Sort by start time
        events.sort(key=lambda e: e.start)
        
        return events
    
    def find_free_slots(self, date: datetime, min_duration_minutes: int = 30,
                        work_start: int = 9, work_end: int = 18) -> List[Tuple[datetime, datetime]]:
        """Find free time slots on a given date."""
        start_of_day = date.replace(hour=work_start, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=work_end, minute=0, second=0, microsecond=0)
        
        # Get all events for the day
        events = self.get_all_events(start_of_day, end_of_day)
        
        # Filter to non-all-day events and sort
        timed_events = [e for e in events if not e.all_day]
        timed_events.sort(key=lambda e: e.start)
        
        # Find gaps
        free_slots = []
        current_time = start_of_day
        
        for event in timed_events:
            if event.start > current_time:
                gap_minutes = (event.start - current_time).total_seconds() / 60
                if gap_minutes >= min_duration_minutes:
                    free_slots.append((current_time, event.start))
            current_time = max(current_time, event.end)
        
        # Check end of day
        if current_time < end_of_day:
            gap_minutes = (end_of_day - current_time).total_seconds() / 60
            if gap_minutes >= min_duration_minutes:
                free_slots.append((current_time, end_of_day))
        
        return free_slots


# Global instance
_calendar_manager = None
_calendar_manager_lock = threading.Lock()


def get_calendar_manager() -> CalendarManager:
    """Get the global calendar manager instance (thread-safe)."""
    global _calendar_manager
    if _calendar_manager is None:
        with _calendar_manager_lock:
            # Double-check pattern for thread safety
            if _calendar_manager is None:
                _calendar_manager = CalendarManager()
                logger.info("CalendarManager initialized")
    return _calendar_manager


# =============================================================================
# Tools
# =============================================================================

@agent.tool_plain
def get_calendar_events(days: int = 7, calendar: str = "both") -> Dict[str, Any]:
    """Get upcoming calendar events.
    
    Atomic data tool that returns structured calendar event data.
    
    Args:
        days: Number of days to look ahead (default: 7)
        calendar: Which calendar to check - "personal", "work", or "both" (default)
    
    Returns:
        Dict with list of events and metadata
    """
    try:
        manager = get_calendar_manager()
        
        now = datetime.now(settings.TIMEZONE)
        start = now
        end = now + timedelta(days=days)
        
        if calendar == "personal":
            events = manager.nextcloud.get_events(start, end)
        elif calendar == "work":
            events = manager.google.get_events(start, end)
        else:
            events = manager.get_all_events(start, end)
        
        return {
            "events": [event.to_dict() for event in events],
            "count": len(events),
            "calendar_filter": calendar,
            "period_days": days,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def get_today_schedule() -> Dict[str, Any]:
    """Get today's complete schedule from both calendars.
    
    Atomic data tool that returns structured schedule data.
    
    Returns:
        Dict with today's events categorized by status (current, upcoming, completed)
    """
    try:
        manager = get_calendar_manager()
        
        now = datetime.now(settings.TIMEZONE)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        events = manager.get_all_events(start, end)
        
        current_events = []
        upcoming_events = []
        completed_events = []
        
        for event in events:
            event_dict = event.to_dict()
            if event.start < now and event.end > now:
                event_dict["status"] = "current"
                current_events.append(event_dict)
            elif event.start > now:
                event_dict["status"] = "upcoming"
                upcoming_events.append(event_dict)
            else:
                event_dict["status"] = "completed"
                completed_events.append(event_dict)
        
        return {
            "date": start.date().isoformat(),
            "current_events": current_events,
            "upcoming_events": upcoming_events,
            "completed_events": completed_events,
            "total_events": len(events),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def add_calendar_event(title: str, start_time: str, end_time: str,
                       calendar: str = "personal", description: str = "",
                       location: str = "") -> str:
    """Add a new event to a calendar.
    
    NOTE: Only personal calendar supports adding events. Work calendar is read-only.
    
    Args:
        title: Event title
        start_time: Start time in format "YYYY-MM-DD HH:MM" or "HH:MM" for today
        end_time: End time in format "YYYY-MM-DD HH:MM" or "HH:MM" for today
        calendar: Which calendar - only "personal" is supported for adding
        description: Optional event description
        location: Optional event location
    
    Returns:
        Confirmation message with event details
    """
    try:
        # Work calendar is read-only
        if calendar == "work":
            return "❌ Work calendar is read-only. Please add events to personal calendar or use Google Calendar directly."
        
        manager = get_calendar_manager()
        now = datetime.now(settings.TIMEZONE)
        
        # Parse start time
        if len(start_time) <= 5:  # Just time, assume today
            start = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {start_time}", "%Y-%m-%d %H:%M")
        else:
            start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        start = start.replace(tzinfo=settings.TIMEZONE)
        
        # Parse end time
        if len(end_time) <= 5:
            end = datetime.strptime(f"{start.strftime('%Y-%m-%d')} {end_time}", "%Y-%m-%d %H:%M")
        else:
            end = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        end = end.replace(tzinfo=settings.TIMEZONE)
        
        # Add to personal calendar only
        event_id = manager.nextcloud.add_event(title, start, end, description, location)
        cal_name = "Personal (Nextcloud)"
        
        if event_id:
            return (
                f"✅ Event added to {cal_name}!\n"
                f"   Title: {title}\n"
                f"   Time: {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}"
            )
        else:
            return "❌ Failed to add event."
        
    except Exception as e:
        return f"Error adding event: {e}"


@agent.tool_plain
def find_free_time(date: str = "", min_duration: int = 30) -> Dict[str, Any]:
    """Find free time slots on a given date.
    
    Atomic data tool that returns structured free time slot data.
    
    Args:
        date: Date to check in format "YYYY-MM-DD" (default: today)
        min_duration: Minimum slot duration in minutes (default: 30)
    
    Returns:
        Dict with list of free time slots
    """
    try:
        manager = get_calendar_manager()
        
        if date:
            check_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=settings.TIMEZONE)
        else:
            check_date = datetime.now(settings.TIMEZONE)
        
        slots = manager.find_free_slots(check_date, min_duration)
        
        free_slots = []
        for start, end in slots:
            duration_minutes = int((end - start).total_seconds() / 60)
            free_slots.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "duration_minutes": duration_minutes
            })
        
        return {
            "date": check_date.date().isoformat(),
            "free_slots": free_slots,
            "min_duration_minutes": min_duration,
            "total_slots": len(free_slots),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def get_next_event() -> Dict[str, Any]:
    """Get the next upcoming event from either calendar.
    
    Atomic data tool that returns structured next event data.
    
    Returns:
        Dict with next event details and time until event
    """
    try:
        manager = get_calendar_manager()
        
        now = datetime.now(settings.TIMEZONE)
        end = now + timedelta(days=7)
        
        events = manager.get_all_events(now, end)
        
        # Find next event that hasn't started
        for event in events:
            if event.start > now:
                time_until = event.start - now
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                total_minutes = int(time_until.total_seconds() / 60)
                
                return {
                    "event": event.to_dict(),
                    "time_until": {
                        "hours": hours,
                        "minutes": minutes,
                        "total_minutes": total_minutes
                    },
                    "current_time": now.isoformat(),
                    "timestamp": now.isoformat()
                }
        
        return {
            "event": None,
            "message": "No upcoming events in the next 7 days",
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}


@agent.tool_plain
def delete_calendar_event(event_id: str, calendar: str) -> str:
    """Delete an event from a calendar.
    
    NOTE: Only personal calendar supports deletion. Work calendar is read-only.
    
    Args:
        event_id: The event ID to delete
        calendar: Which calendar - only "personal" is supported for deletion
    
    Returns:
        Confirmation message
    """
    try:
        # Work calendar is read-only
        if calendar == "work":
            return "❌ Work calendar is read-only. Please delete events using Google Calendar directly."
        
        manager = get_calendar_manager()
        success = manager.nextcloud.delete_event(event_id)
        
        if success:
            return f"✅ Event deleted from personal calendar."
        else:
            return f"❌ Failed to delete event."
        
    except Exception as e:
        return f"Error deleting event: {e}"
