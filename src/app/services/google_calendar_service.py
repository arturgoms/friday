"""Google Calendar integration."""
import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.logging import logger
from app.services.calendar_service import CalendarEvent


# If modifying these scopes, delete the token file
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class GoogleCalendarService:
    """Service for interacting with Google Calendar."""
    
    def __init__(self):
        self.credentials_path = Path("/home/artur/friday/data/google_credentials.json")
        self.token_path = Path("/home/artur/friday/data/google_token.pickle")
        self.service = None
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")  # Default to primary calendar
        
        # Ensure data directory exists
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.credentials_path.exists():
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Failed to connect to Google Calendar: {e}")
    
    def connect(self):
        """Authenticate and connect to Google Calendar."""
        creds = None
        
        # Load existing token
        if self.token_path.exists():
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    creds = None
            
            if not creds:
                if not self.credentials_path.exists():
                    logger.error(f"Credentials file not found: {self.credentials_path}")
                    return
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                # Try local server first, fall back to manual auth if no browser
                try:
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.warning(f"Cannot open browser: {e}. Using manual authorization...")
                    # Get the authorization URL
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print("\n" + "="*70)
                    print("GOOGLE CALENDAR AUTHORIZATION")
                    print("="*70)
                    print("\n1. Open this URL in your browser:")
                    print(f"\n{auth_url}\n")
                    print("2. Sign in and authorize the application")
                    print("3. Copy the authorization code from the browser")
                    print("4. Paste it below:")
                    print("="*70)
                    code = input("\nEnter authorization code: ").strip()
                    flow.fetch_token(code=code)
                    creds = flow.credentials
            
            # Save token for future use
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build the service
        self.service = build('calendar', 'v3', credentials=creds)
        logger.info(f"✅ Connected to Google Calendar (ID: {self.calendar_id})")
    
    def get_events(self, start_time: datetime, end_time: datetime) -> List[CalendarEvent]:
        """Get events between start and end time."""
        if not self.service:
            logger.warning("Google Calendar not connected")
            return []
        
        try:
            # Convert to RFC3339 format
            time_min = start_time.isoformat()
            time_max = end_time.isoformat()
            
            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            parsed_events = []
            user_tz = timezone(timedelta(hours=-3))
            
            for event in events:
                try:
                    # Parse start time
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    
                    # Convert to datetime objects
                    if 'T' in start:  # DateTime
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    else:  # Date only (all-day event)
                        start_dt = datetime.fromisoformat(start).replace(tzinfo=user_tz)
                        end_dt = datetime.fromisoformat(end).replace(tzinfo=user_tz)
                    
                    parsed_events.append(CalendarEvent(
                        uid=event['id'],
                        summary=event.get('summary', 'No title'),
                        start=start_dt,
                        end=end_dt,
                        description=event.get('description'),
                        location=event.get('location'),
                        url=event.get('htmlLink'),  # Google Calendar event URL
                    ))
                except Exception as e:
                    logger.error(f"Error parsing Google event: {e}")
                    continue
            
            return parsed_events
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e}")
            return []
    
    def get_today_events(self) -> List[CalendarEvent]:
        """Get today's events."""
        user_tz = timezone(timedelta(hours=-3))
        now = datetime.now(user_tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_events(start, end)
    
    def get_tomorrow_events(self) -> List[CalendarEvent]:
        """Get tomorrow's events."""
        user_tz = timezone(timedelta(hours=-3))
        now = datetime.now(user_tz)
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_events(start, end)
    
    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        """Get upcoming events for the next N days."""
        user_tz = timezone(timedelta(hours=-3))
        start = datetime.now(user_tz)
        end = start + timedelta(days=days)
        return self.get_events(start, end)


# Singleton instance
google_calendar_service = GoogleCalendarService()
