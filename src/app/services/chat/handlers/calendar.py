"""Calendar intent handlers - query, create, find free time."""
import os
import re
import calendar as cal_module
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.calendar_service import calendar_service
from app.services.unified_calendar_service import unified_calendar_service
from app.services.reminders import reminder_service
from app.services.llm import llm_service


class CalendarQueryHandler(IntentHandler):
    """Handle calendar_query intent - query existing calendar events."""
    
    actions = ['calendar_query']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Query calendar events based on tool type."""
        tool = context.tool
        
        try:
            if tool == "calendar_today":
                answer = self._get_today_events()
            elif tool == "calendar_tomorrow":
                answer = self._get_tomorrow_events()
            elif tool == "calendar_week":
                answer = self._get_week_events()
            elif tool == "calendar_next":
                answer = self._get_next_event()
            else:
                # Default to today's events
                answer = self._get_today_events()
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Calendar query error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to query calendar: {str(e)}")
    
    def _get_today_events(self) -> str:
        """Get today's calendar events."""
        events = calendar_service.get_today_events()
        if events:
            result = "Today's calendar:\n"
            for e in events:
                time_str = e.start.strftime("%I:%M %p")
                result += f"- {time_str} - {e.summary}\n"
                if e.location:
                    result += f"  Location: {e.location}\n"
            return result
        return "You have no events today."
    
    def _get_tomorrow_events(self) -> str:
        """Get tomorrow's calendar events."""
        events = calendar_service.get_tomorrow_events()
        if events:
            result = "Tomorrow's calendar:\n"
            for e in events:
                time_str = e.start.strftime("%I:%M %p")
                result += f"- {time_str} - {e.summary}\n"
                if e.location:
                    result += f"  Location: {e.location}\n"
            return result
        return "You have no events tomorrow."
    
    def _get_week_events(self) -> str:
        """Get this week's calendar events."""
        events = calendar_service.get_upcoming_events(days=7)
        if events:
            result = "This week's calendar:\n"
            for e in events:
                date_str = e.start.strftime("%a, %b %d at %I:%M %p")
                result += f"- {date_str} - {e.summary}\n"
                if e.location:
                    result += f"  Location: {e.location}\n"
            return result
        return "You have no events this week."
    
    def _get_next_event(self) -> str:
        """Get the next upcoming event."""
        events = calendar_service.get_upcoming_events(days=30)
        if events:
            next_event = events[0]
            user_tz = settings.user_timezone
            now = datetime.now(user_tz)
            time_diff = next_event.start.replace(tzinfo=user_tz) - now
            
            days = time_diff.days
            hours = (int(time_diff.total_seconds()) // 3600) % 24
            minutes = (int(time_diff.total_seconds()) % 3600) // 60
            
            if days > 0:
                time_text = f"in {days} day(s) and {hours} hour(s)"
            elif hours > 0:
                time_text = f"in {hours} hour(s) and {minutes} minute(s)"
            else:
                time_text = f"in {minutes} minute(s)"
            
            date_str = next_event.start.strftime("%a, %b %d at %I:%M %p")
            result = f"Your next event is '{next_event.summary}' on {date_str} ({time_text})"
            if next_event.location:
                result += f"\nLocation: {next_event.location}"
            return result
        return "You have no upcoming events in the next 30 days."


class CalendarCreateHandler(IntentHandler):
    """Handle calendar_create intent - create new calendar events."""
    
    actions = ['calendar_create']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Create a new calendar event."""
        calendar_data = context.calendar_data
        
        if not calendar_data:
            return self._error_response(context, "No calendar data provided")
        
        try:
            summary = calendar_data.get('summary', 'New Event')
            date_str = calendar_data.get('date', 'today')
            time_str = calendar_data.get('time', '09:00')
            duration = calendar_data.get('duration_minutes', 60)
            location = calendar_data.get('location')
            
            # Parse date and time
            user_tz = settings.user_timezone
            now = datetime.now(user_tz)
            
            # Parse date
            event_date = self._parse_date(date_str, now)
            
            # Parse time
            hour, minute = self._parse_time(time_str)
            
            start_dt = datetime.combine(
                event_date, 
                datetime.min.time().replace(hour=hour, minute=minute),
                tzinfo=user_tz
            )
            end_dt = start_dt + timedelta(minutes=duration)
            
            event = unified_calendar_service.create_event(
                summary=summary,
                start=start_dt,
                end=end_dt,
                location=location
            )
            
            if event:
                answer = f"Created event: **{summary}**\n"
                answer += f"Date: {start_dt.strftime('%a, %b %d at %I:%M %p')}\n"
                answer += f"Duration: {duration} minutes"
                if location:
                    answer += f"\nLocation: {location}"
            else:
                answer = "Failed to create event. Please try again."
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Calendar create error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to create event: {str(e)}")
    
    def _parse_date(self, date_str: str, now: datetime):
        """Parse date string to date object."""
        date_lower = date_str.lower()
        
        if date_lower == 'today':
            return now.date()
        elif date_lower == 'tomorrow':
            return (now + timedelta(days=1)).date()
        else:
            # Try to parse day name (e.g., "Friday")
            day_names = list(cal_module.day_name)
            day_title = date_str.capitalize()
            if day_title in day_names:
                target_day = day_names.index(day_title)
                days_ahead = target_day - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).date()
            else:
                # Try parsing as date
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    return now.date()
    
    def _parse_time(self, time_str: str) -> tuple:
        """Parse time string to hour, minute tuple."""
        time_match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str.lower())
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            return hour, minute
        return 9, 0


class CalendarFindFreeHandler(IntentHandler):
    """Handle calendar_find_free intent - find free time slots with smart suggestions."""
    
    actions = ['calendar_find_free']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Find free time slots with LLM-powered suggestions."""
        try:
            free_time_data = context.free_time_data or {}
            days = free_time_data.get('days', 7)
            duration = free_time_data.get('duration_minutes', 60)
            purpose = free_time_data.get('purpose', '')
            start_from_day = free_time_data.get('start_from_day', 0)
            
            # Handle "next week" - calculate days until next Monday
            if free_time_data.get('next_week'):
                user_tz = settings.user_timezone
                today = datetime.now(user_tz).date()
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                start_from_day = days_until_monday
                logger.info(f"'Next week' detected - starting from day {start_from_day}")
            
            # Get free slots
            fetch_days = days + start_from_day if start_from_day > 0 else days
            free_slots = unified_calendar_service.find_free_slots(
                days=fetch_days,
                duration_minutes=duration
            )
            
            # Filter slots to start from a specific day
            if start_from_day > 0:
                user_tz = settings.user_timezone
                start_date = (datetime.now(user_tz) + timedelta(days=start_from_day)).date()
                free_slots = [s for s in free_slots if s['datetime_start'].date() >= start_date]
            
            # Filter out weekends for activities that require weekdays
            total_slots_before = len(free_slots)
            purpose_lower = (purpose or '').lower()
            weekday_only_activities = [
                'barber', 'haircut', 'hair cut', 'salon', 'bank', 
                'post office', 'government', 'dmv', 'office'
            ]
            
            needs_weekday = any(activity in purpose_lower for activity in weekday_only_activities)
            if needs_weekday:
                free_slots = [s for s in free_slots if s['datetime_start'].weekday() < 5]
            
            if not free_slots:
                if needs_weekday and total_slots_before > 0:
                    answer = (
                        f"No free weekday slots found for {purpose}. "
                        f"Your weekdays appear to be fully booked. "
                        f"You had {total_slots_before} weekend slots available - "
                        f"would you like me to look further ahead or show weekend options anyway?"
                    )
                else:
                    answer = "No free slots found in your calendar for the specified period."
                
                return ChatResponse(
                    session_id=context.session_id,
                    message=context.message,
                    answer=answer,
                    is_final=True,
                )
            
            # Build context for LLM suggestions
            answer = self._generate_smart_suggestions(
                context.message,
                free_slots,
                purpose,
                days
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_memory=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Calendar find free error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to find free time: {str(e)}")
    
    def _generate_smart_suggestions(
        self, 
        message: str, 
        free_slots: List[Dict],
        purpose: str,
        days: int
    ) -> str:
        """Generate smart scheduling suggestions using LLM."""
        user_tz = settings.user_timezone
        
        # Format slots for LLM
        slots_text = "FREE TIME SLOTS:\n"
        for slot in free_slots[:15]:
            day_name = slot['datetime_start'].strftime("%A")
            slots_text += (
                f"- {slot['date']} ({day_name}): {slot['start']} - {slot['end']} "
                f"({slot['duration_minutes']} min available)\n"
            )
        
        # Get upcoming events for context
        upcoming_events = unified_calendar_service.get_upcoming_events(days=days)
        events_text = "\nUPCOMING EVENTS:\n"
        for event in upcoming_events[:10]:
            event_day = event.start.strftime("%a, %b %d")
            event_time = event.start.strftime("%I:%M %p")
            events_text += f"- {event_day} at {event_time}: {event.summary}\n"
        
        # Get reminders for context
        pending_reminders = reminder_service.list_pending_reminders()
        reminders_text = ""
        if pending_reminders:
            reminders_text = "\nPENDING REMINDERS:\n"
            for r in pending_reminders[:5]:
                reminders_text += f"- {r.message} (at {r.remind_at.strftime('%a %I:%M %p')})\n"
        
        # Get weather forecast
        weather_text = self._get_weather_forecast()
        
        # Get memory context
        memory_text = self._get_memory_context(purpose or message)
        
        # Build LLM prompt
        suggestion_prompt = f"""You are helping the user find the best time for: {purpose if purpose else 'an activity'}

The user asked: "{message}"

Here is the context:

{slots_text}
{events_text}
{reminders_text}
{weather_text}
{memory_text}

TODAY: {datetime.now(user_tz).strftime("%A, %B %d, %Y")}

IMPORTANT RULES for suggesting times:
1. **Prefer earlier dates**: For simple errands (haircut, shopping, etc.), suggest the EARLIEST available slots first.
2. **Barber shops / hair salons**: ALWAYS suggest WEEKDAYS ONLY (Monday-Friday).
3. **Outdoor activities**: Avoid days with rain in the forecast
4. **Medical appointments**: Suggest morning slots when possible
5. **Errands/shopping**: Consider store hours and avoid rainy days

YOUR RESPONSE MUST INCLUDE:

**Recommended slots (2-3):**
- Suggest specific times (e.g., "Monday at 10:00 AM", not "Monday 9am-5pm")
- Briefly explain WHY each slot is good

**Not recommended (1-2):**
- List any early slots you're SKIPPING and explain WHY

Keep it concise."""

        return llm_service.call(
            system_prompt=(
                "You are Friday, a helpful AI assistant. "
                "Give practical scheduling suggestions based on the user's calendar and context. "
                "Be concise and friendly."
            ),
            user_content=suggestion_prompt,
            history=[],
            stream=False
        )
    
    def _get_weather_forecast(self) -> str:
        """Get weather forecast for scheduling context."""
        try:
            weather_api_key = os.getenv('WEATHER_API_KEY')
            city = os.getenv('WEATHER_CITY', 'São Paulo')
            
            if not weather_api_key:
                return ""
            
            weather_text = "\nWEATHER:\n"
            
            # Get current weather
            current_url = (
                f"http://api.openweathermap.org/data/2.5/weather"
                f"?q={city}&appid={weather_api_key}&units=metric&lang=en"
            )
            current_response = requests.get(current_url, timeout=5)
            
            if current_response.status_code == 200:
                current = current_response.json()
                weather_text += (
                    f"- Current: {current['weather'][0]['description']}, "
                    f"{current['main']['temp']:.0f}°C\n"
                )
            
            # Get forecast
            forecast_url = (
                f"http://api.openweathermap.org/data/2.5/forecast"
                f"?q={city}&appid={weather_api_key}&units=metric&lang=en"
            )
            forecast_response = requests.get(forecast_url, timeout=5)
            
            if forecast_response.status_code == 200:
                forecast = forecast_response.json()
                user_tz = settings.user_timezone
                seen_dates = set()
                
                for entry in forecast['list']:
                    entry_time = datetime.fromtimestamp(entry['dt'], tz=user_tz)
                    entry_date = entry_time.date()
                    
                    if entry_date <= datetime.now(user_tz).date():
                        continue
                    if entry_date in seen_dates:
                        continue
                    if entry_time.hour < 11 or entry_time.hour > 14:
                        continue
                    
                    seen_dates.add(entry_date)
                    day_name = entry_time.strftime("%A, %b %d")
                    desc = entry['weather'][0]['description']
                    temp = entry['main']['temp']
                    
                    rain_warning = ""
                    if any(w in desc.lower() for w in ['rain', 'storm', 'shower']):
                        rain_warning = " - RAIN"
                    
                    weather_text += f"- {day_name}: {desc}, {temp:.0f}°C{rain_warning}\n"
                    
                    if len(seen_dates) >= 5:
                        break
            
            return weather_text
            
        except Exception as e:
            logger.debug(f"Weather fetch for scheduling skipped: {e}")
            return ""
    
    def _get_memory_context(self, query: str) -> str:
        """Get relevant memory context for scheduling."""
        try:
            from app.services.memory_store import memory_store
            memory_context = memory_store.get_context_string(query, limit=3)
            if memory_context:
                return f"\nRELEVANT MEMORIES:\n{memory_context}\n"
        except Exception as e:
            logger.debug(f"Memory context fetch skipped: {e}")
        return ""


class TimeQueryHandler(IntentHandler):
    """Handle time_query intent - get current time."""
    
    actions = ['time_query']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Return the current time."""
        from app.services.date_tools import date_tools
        
        try:
            answer = date_tools.get_current_time()
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Time query error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to get time: {str(e)}")
