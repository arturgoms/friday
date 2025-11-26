"""Unified Calendar Service - Merges Nextcloud and Google Calendar."""
from datetime import datetime, timedelta, timezone
from typing import List
from app.core.logging import logger
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


# Singleton instance
unified_calendar_service = UnifiedCalendarService()
