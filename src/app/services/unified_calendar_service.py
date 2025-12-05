"""Unified Calendar Service - Merges Nextcloud and Google Calendar."""
from datetime import datetime, timedelta, timezone, time
from typing import List, Dict, Any, Optional
from app.core.logging import logger
from app.core.config import settings
from app.services.calendar_service import CalendarService, CalendarEvent
from app.services.google_calendar_service import GoogleCalendarService


class UnifiedCalendarService:
    """Service that combines events from multiple calendar sources."""
    
    def __init__(self):
        self.nextcloud = CalendarService()
        self.google = GoogleCalendarService()
    
    def _merge_and_sort_events(self, *event_lists: List[CalendarEvent]) -> List[CalendarEvent]:
        """Merge multiple event lists and sort by start time."""
        all_events = []
        for events in event_lists:
            all_events.extend(events)
        
        # Remove duplicates by UID (in case same event exists in both calendars)
        seen_uids = set()
        unique_events = []
        for event in all_events:
            if event.uid not in seen_uids:
                seen_uids.add(event.uid)
                unique_events.append(event)
        
        # Sort by start time
        unique_events.sort(key=lambda e: e.start)
        return unique_events
    
    def get_today_events(self) -> List[CalendarEvent]:
        """Get today's events from all calendars."""
        nextcloud_events = []
        google_events = []
        
        try:
            nextcloud_events = self.nextcloud.get_today_events()
            logger.debug(f"Nextcloud: {len(nextcloud_events)} events today")
        except Exception as e:
            logger.error(f"Error fetching Nextcloud events: {e}")
        
        try:
            google_events = self.google.get_today_events()
            logger.debug(f"Google: {len(google_events)} events today")
        except Exception as e:
            logger.error(f"Error fetching Google events: {e}")
        
        merged = self._merge_and_sort_events(nextcloud_events, google_events)
        logger.info(f"📅 Total events today: {len(merged)} (Nextcloud: {len(nextcloud_events)}, Google: {len(google_events)})")
        return merged
    
    def get_tomorrow_events(self) -> List[CalendarEvent]:
        """Get tomorrow's events from all calendars."""
        nextcloud_events = []
        google_events = []
        
        try:
            nextcloud_events = self.nextcloud.get_tomorrow_events()
            logger.debug(f"Nextcloud: {len(nextcloud_events)} events tomorrow")
        except Exception as e:
            logger.error(f"Error fetching Nextcloud events: {e}")
        
        try:
            google_events = self.google.get_tomorrow_events()
            logger.debug(f"Google: {len(google_events)} events tomorrow")
        except Exception as e:
            logger.error(f"Error fetching Google events: {e}")
        
        merged = self._merge_and_sort_events(nextcloud_events, google_events)
        logger.info(f"📅 Total events tomorrow: {len(merged)} (Nextcloud: {len(nextcloud_events)}, Google: {len(google_events)})")
        return merged
    
    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        """Get upcoming events for the next N days from all calendars."""
        nextcloud_events = []
        google_events = []
        
        try:
            nextcloud_events = self.nextcloud.get_upcoming_events(days)
            logger.debug(f"Nextcloud: {len(nextcloud_events)} upcoming events")
        except Exception as e:
            logger.error(f"Error fetching Nextcloud events: {e}")
        
        try:
            google_events = self.google.get_upcoming_events(days)
            logger.debug(f"Google: {len(google_events)} upcoming events")
        except Exception as e:
            logger.error(f"Error fetching Google events: {e}")
        
        merged = self._merge_and_sort_events(nextcloud_events, google_events)
        logger.info(f"📅 Total upcoming events ({days} days): {len(merged)} (Nextcloud: {len(nextcloud_events)}, Google: {len(google_events)})")
        return merged
    
    def _is_all_day_blocking_event(self, event: CalendarEvent) -> bool:
        """
        Check if an event is an all-day event that should BLOCK the entire day.
        
        Only returns True for events that genuinely make you UNAVAILABLE like:
        - Travel (you're not at home)
        - Conferences, weddings, funerals (you're committed elsewhere)
        
        Does NOT block for:
        - PTO, vacation, holidays - these mean you're FREE from work!
        - Short reminder-style events at midnight (like "Take trash out")
        - Events with specific times
        - "Home" or location indicators
        """
        start = event.start
        end = event.end
        
        # Check if times are at midnight
        start_is_midnight = start.hour == 0 and start.minute == 0 and start.second == 0
        end_is_midnight = end.hour == 0 and end.minute == 0 and end.second == 0
        
        # Must start and end at midnight to be an all-day event
        if not (start_is_midnight and end_is_midnight):
            return False
        
        # Check duration in days
        duration_days = (end - start).days
        
        if duration_days < 1:
            return False
        
        summary_lower = event.summary.lower() if event.summary else ""
        
        # These events mean you're FREE (time off from work) - DO NOT BLOCK
        free_time_keywords = [
            'pto', 'vacation', 'holiday', 'day off', 'time off', 'off work',
            'home', 'wfh', 'work from home', 'remote'
        ]
        
        for keyword in free_time_keywords:
            if keyword in summary_lower:
                return False  # This is free time, not blocking!
        
        # These events mean you're UNAVAILABLE - BLOCK the day
        blocking_keywords = [
            'travel', 'trip', 'flying', 'flight',
            'conference', 'wedding', 'funeral', 'ceremony',
            'hospital', 'surgery',
            'blocked', 'busy', 'unavailable', 'reserved'
        ]
        
        for keyword in blocking_keywords:
            if keyword in summary_lower:
                return True
        
        # For other multi-day events (2+ days) without clear keywords, 
        # assume they might be blocking (like unmarked travel)
        if duration_days >= 2:
            # But if it's just a generic multi-day event, don't block
            # Only block if it seems like an away event
            return False
        
        return False
    
    def find_free_slots(
        self,
        days: int = 7,
        duration_minutes: int = 60,
        start_hour: int = 9,
        end_hour: int = 18,
        exclude_weekends: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Find free time slots in the calendar.
        
        Args:
            days: Number of days to look ahead
            duration_minutes: Minimum duration of free slot in minutes
            start_hour: Start of working hours (default 9am)
            end_hour: End of working hours (default 6pm)
            exclude_weekends: Whether to exclude Saturday and Sunday
            
        Returns:
            List of free slots with start time, end time, and duration
        """
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        # Get all events for the period
        events = self.get_upcoming_events(days=days)
        
        free_slots = []
        
        # Identify all-day BLOCKING events and the days they block
        blocked_days = set()
        for event in events:
            if self._is_all_day_blocking_event(event):
                # Block all days this event spans
                event_start_date = event.start.date()
                event_end_date = event.end.date()
                current_date = event_start_date
                while current_date < event_end_date:
                    blocked_days.add(current_date)
                    current_date += timedelta(days=1)
                logger.debug(f"All-day blocking event '{event.summary}' blocks: {event_start_date} to {event_end_date}")
        
        # Iterate through each day
        for day_offset in range(days):
            day = now.date() + timedelta(days=day_offset)
            
            # Skip weekends if requested
            if exclude_weekends and day.weekday() >= 5:
                continue
            
            # Skip days blocked by all-day events
            if day in blocked_days:
                logger.debug(f"Skipping {day} - blocked by all-day event")
                continue
            
            # Define working hours for this day
            day_start = datetime.combine(day, time(start_hour, 0), tzinfo=user_tz)
            day_end = datetime.combine(day, time(end_hour, 0), tzinfo=user_tz)
            
            # For today, start from current time (rounded up to next 30 min)
            if day_offset == 0:
                current_minute = now.minute
                if current_minute > 0:
                    # Round up to next 30 min
                    if current_minute <= 30:
                        day_start = now.replace(minute=30, second=0, microsecond=0)
                    else:
                        day_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                else:
                    day_start = now.replace(second=0, microsecond=0)
                
                # Make sure we don't start before the configured start hour
                if day_start.hour < start_hour:
                    day_start = day_start.replace(hour=start_hour, minute=0)
                
                # If we're past end hour, skip today
                if day_start.hour >= end_hour:
                    continue
            
            # Get events for this day (exclude ALL all-day events - they don't block specific times)
            # An all-day event is one that starts at midnight and ends at midnight (next day or later)
            def is_all_day_event(e: CalendarEvent) -> bool:
                start_midnight = e.start.hour == 0 and e.start.minute == 0 and e.start.second == 0
                end_midnight = e.end.hour == 0 and e.end.minute == 0 and e.end.second == 0
                return start_midnight and end_midnight and (e.end - e.start).days >= 1
            
            # Check if this day has a PTO/vacation event (means work events should be ignored)
            def is_pto_day(check_day) -> bool:
                pto_keywords = ['pto', 'vacation', 'holiday', 'day off', 'time off', 'off work', 'férias']
                for e in events:
                    if is_all_day_event(e):
                        summary_lower = e.summary.lower() if e.summary else ""
                        if any(kw in summary_lower for kw in pto_keywords):
                            # Check if this PTO event covers the day we're checking
                            if e.start.date() <= check_day and e.end.date() > check_day:
                                return True
                return False
            
            # Check if an event looks like a work meeting (should be ignored during PTO)
            def is_work_event(e: CalendarEvent) -> bool:
                summary_lower = e.summary.lower() if e.summary else ""
                work_indicators = [
                    '[mm]', 'standup', 'kickoff', 'meeting', 'sync', '1:1', 'retro',
                    'sprint', 'planning', 'review', 'demo', 'office hours', 'company meeting',
                    "don't book", 'focus time', 'ask anything'
                ]
                return any(indicator in summary_lower for indicator in work_indicators)
            
            # Check if today is a PTO day
            day_is_pto = is_pto_day(day)
            
            day_events = [
                e for e in events 
                if not is_all_day_event(e) and (
                    e.start.date() == day or (
                        e.start.date() < day and e.end.date() >= day
                    )
                ) and not (day_is_pto and is_work_event(e))  # Skip work events on PTO days
            ]
            
            if day_is_pto:
                logger.debug(f"Day {day} is PTO - ignoring work events")
            
            # Sort events by start time
            day_events.sort(key=lambda e: e.start)
            
            # Find free slots between events
            current_time = day_start
            
            for event in day_events:
                # Make sure event times are timezone-aware
                event_start = event.start
                event_end = event.end
                if event_start.tzinfo is None:
                    event_start = event_start.replace(tzinfo=user_tz)
                if event_end.tzinfo is None:
                    event_end = event_end.replace(tzinfo=user_tz)
                
                # If event starts after current time, there's a gap
                if event_start > current_time:
                    gap_end = min(event_start, day_end)
                    gap_duration = (gap_end - current_time).total_seconds() / 60
                    
                    if gap_duration >= duration_minutes:
                        free_slots.append({
                            "date": day.strftime("%a, %b %d"),
                            "start": current_time.strftime("%I:%M %p"),
                            "end": gap_end.strftime("%I:%M %p"),
                            "duration_minutes": int(gap_duration),
                            "datetime_start": current_time,
                            "datetime_end": gap_end,
                        })
                
                # Move current time to after this event
                if event_end > current_time:
                    current_time = event_end
            
            # Check for free time after last event until end of day
            if current_time < day_end:
                gap_duration = (day_end - current_time).total_seconds() / 60
                
                if gap_duration >= duration_minutes:
                    free_slots.append({
                        "date": day.strftime("%a, %b %d"),
                        "start": current_time.strftime("%I:%M %p"),
                        "end": day_end.strftime("%I:%M %p"),
                        "duration_minutes": int(gap_duration),
                        "datetime_start": current_time,
                        "datetime_end": day_end,
                    })
        
        logger.info(f"📅 Found {len(free_slots)} free slots in next {days} days")
        return free_slots
    
    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        calendar: str = "nextcloud",
    ) -> Optional[CalendarEvent]:
        """
        Create a new calendar event.
        
        Args:
            summary: Event title
            start: Start datetime
            end: End datetime
            description: Event description
            location: Event location
            calendar: Which calendar to use ("nextcloud" or "google")
            
        Returns:
            Created CalendarEvent or None on failure
        """
        try:
            if calendar == "google":
                return self.google.create_event(
                    summary=summary,
                    start=start,
                    end=end,
                    description=description,
                    location=location,
                )
            else:
                return self.nextcloud.create_event(
                    summary=summary,
                    start=start,
                    end=end,
                    description=description,
                    location=location,
                )
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None


# Singleton instance
unified_calendar_service = UnifiedCalendarService()
