"""Nextcloud Calendar integration via CalDAV."""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import caldav
from icalendar import Calendar as iCalendar
from app.core.logging import logger


class CalendarEvent:
    """Calendar event data structure."""
    
    def __init__(
        self,
        uid: str,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.uid = uid
        self.summary = summary
        self.start = start
        self.end = end
        self.description = description
        self.location = location
    
    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "description": self.description,
            "location": self.location,
        }


class CalendarService:
    """Service for interacting with Nextcloud Calendar via CalDAV."""
    
    def __init__(self):
        self.url = os.getenv("NEXTCLOUD_CALDAV_URL")
        self.username = os.getenv("NEXTCLOUD_USERNAME")
        self.password = os.getenv("NEXTCLOUD_PASSWORD")
        self.client = None
        self.calendar = None
        
        if self.url and self.username and self.password:
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Failed to connect to calendar: {e}")
    
    def connect(self):
        """Connect to CalDAV server."""
        try:
            self.client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password
            )
            
            principal = self.client.principal()
            calendars = principal.calendars()
            
            if calendars:
                # Use the first calendar found
                self.calendar = calendars[0]
                logger.info(f"Connected to calendar: {self.calendar.name}")
            else:
                logger.warning("No calendars found")
                
        except Exception as e:
            logger.error(f"Calendar connection error: {e}")
            raise
    
    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        """Get upcoming events for the next N days."""
        if not self.calendar:
            logger.warning("Calendar not connected")
            return []
        
        try:
            user_tz = timezone(timedelta(hours=-3))
            start = datetime.now(user_tz)
            end = start + timedelta(days=days)
            
            # Search for events in the time range
            events = self.calendar.search(
                start=start,
                end=end,
                event=True,
                expand=True
            )
            
            parsed_events = []
            for event in events:
                try:
                    cal = iCalendar.from_ical(event.data)
                    for component in cal.walk():
                        if component.name == "VEVENT":
                            uid = str(component.get('uid'))
                            summary = str(component.get('summary', 'No title'))
                            dtstart = component.get('dtstart').dt
                            dtend = component.get('dtend').dt
                            description = str(component.get('description', ''))
                            location = str(component.get('location', ''))
                            
                            # Convert to timezone-aware if needed
                            if isinstance(dtstart, datetime) and dtstart.tzinfo is None:
                                dtstart = dtstart.replace(tzinfo=user_tz)
                            if isinstance(dtend, datetime) and dtend.tzinfo is None:
                                dtend = dtend.replace(tzinfo=user_tz)
                            
                            parsed_events.append(CalendarEvent(
                                uid=uid,
                                summary=summary,
                                start=dtstart,
                                end=dtend,
                                description=description if description != 'None' else None,
                                location=location if location != 'None' else None,
                            ))
                except Exception as e:
                    logger.error(f"Error parsing event: {e}")
                    continue
            
            # Sort by start time
            parsed_events.sort(key=lambda e: e.start)
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []
    
    def get_tomorrow_events(self) -> List[CalendarEvent]:
        """Get tomorrow's events."""
        if not self.calendar:
            return []
        
        try:
            user_tz = timezone(timedelta(hours=-3))
            now = datetime.now(user_tz)
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            
            events = self.calendar.search(
                start=start,
                end=end,
                event=True,
                expand=True
            )
            
            parsed_events = []
            for event in events:
                try:
                    cal = iCalendar.from_ical(event.data)
                    for component in cal.walk():
                        if component.name == "VEVENT":
                            uid = str(component.get('uid'))
                            summary = str(component.get('summary', 'No title'))
                            dtstart = component.get('dtstart').dt
                            dtend = component.get('dtend').dt
                            description = str(component.get('description', ''))
                            location = str(component.get('location', ''))
                            
                            if isinstance(dtstart, datetime) and dtstart.tzinfo is None:
                                dtstart = dtstart.replace(tzinfo=user_tz)
                            if isinstance(dtend, datetime) and dtend.tzinfo is None:
                                dtend = dtend.replace(tzinfo=user_tz)
                            
                            parsed_events.append(CalendarEvent(
                                uid=uid,
                                summary=summary,
                                start=dtstart,
                                end=dtend,
                                description=description if description != 'None' else None,
                                location=location if location != 'None' else None,
                            ))
                except Exception as e:
                    logger.error(f"Error parsing event: {e}")
                    continue
            
            parsed_events.sort(key=lambda e: e.start)
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching tomorrow's events: {e}")
            return []
    
    def get_today_events(self) -> List[CalendarEvent]:
        """Get today's events."""
        if not self.calendar:
            return []
        
        try:
            user_tz = timezone(timedelta(hours=-3))
            now = datetime.now(user_tz)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            
            events = self.calendar.search(
                start=start,
                end=end,
                event=True,
                expand=True
            )
            
            parsed_events = []
            for event in events:
                try:
                    cal = iCalendar.from_ical(event.data)
                    for component in cal.walk():
                        if component.name == "VEVENT":
                            uid = str(component.get('uid'))
                            summary = str(component.get('summary', 'No title'))
                            dtstart = component.get('dtstart').dt
                            dtend = component.get('dtend').dt
                            description = str(component.get('description', ''))
                            location = str(component.get('location', ''))
                            
                            if isinstance(dtstart, datetime) and dtstart.tzinfo is None:
                                dtstart = dtstart.replace(tzinfo=user_tz)
                            if isinstance(dtend, datetime) and dtend.tzinfo is None:
                                dtend = dtend.replace(tzinfo=user_tz)
                            
                            parsed_events.append(CalendarEvent(
                                uid=uid,
                                summary=summary,
                                start=dtstart,
                                end=dtend,
                                description=description if description != 'None' else None,
                                location=location if location != 'None' else None,
                            ))
                except Exception as e:
                    logger.error(f"Error parsing event: {e}")
                    continue
            
            parsed_events.sort(key=lambda e: e.start)
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching today's events: {e}")
            return []
    
    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> bool:
        """Create a new calendar event."""
        if not self.calendar:
            logger.warning("Calendar not connected")
            return False
        
        try:
            from icalendar import Event
            import uuid
            
            cal = iCalendar()
            event = Event()
            event.add('uid', str(uuid.uuid4()))
            event.add('summary', summary)
            event.add('dtstart', start)
            event.add('dtend', end)
            
            if description:
                event.add('description', description)
            if location:
                event.add('location', location)
            
            cal.add_component(event)
            
            self.calendar.save_event(cal.to_ical().decode('utf-8'))
            logger.info(f"Created event: {summary}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return False


# Singleton instance
calendar_service = CalendarService()
