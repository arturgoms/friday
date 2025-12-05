"""Reminder intent handlers - create, list, delete reminders."""
import re
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.reminders import reminder_service


class ReminderCreateHandler(IntentHandler):
    """Handle reminder_create intent - create time-based reminders."""
    
    actions = ['reminder_create']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Create a reminder with parsed time specification."""
        reminder_data = context.reminder_data
        
        if not reminder_data:
            return self._error_response(context, "No reminder data provided")
        
        try:
            reminder_msg = reminder_data.get('message', '')
            time_spec = reminder_data.get('time_spec', '').lower()
            
            if not reminder_msg:
                return self._error_response(context, "No reminder message provided")
            
            if not time_spec:
                return self._error_response(context, "No time specified for reminder")
            
            # Parse time specification
            answer = self._create_reminder(reminder_msg, time_spec)
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Reminder creation error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to create reminder: {str(e)}")
    
    def _create_reminder(self, message: str, time_spec: str) -> str:
        """Parse time spec and create reminder. Returns response message."""
        user_tz = settings.user_timezone
        
        # Try relative time first (e.g., "30 minutes", "2 hours", "in 30 minutes")
        minutes_match = re.search(r'(\d+)\s*minute', time_spec)
        hours_match = re.search(r'(\d+)\s*hour', time_spec)
        
        if minutes_match:
            minutes = int(minutes_match.group(1))
            reminder_service.create_reminder(message, minutes=minutes)
            remind_time = (datetime.now(user_tz) + timedelta(minutes=minutes)).strftime("%I:%M %p")
            return f"Reminder set: '{message}' at {remind_time} ({minutes} minutes from now)"
        
        elif hours_match:
            hours = int(hours_match.group(1))
            reminder_service.create_reminder(message, hours=hours)
            remind_time = (datetime.now(user_tz) + timedelta(hours=hours)).strftime("%I:%M %p")
            return f"Reminder set: '{message}' at {remind_time} ({hours} hours from now)"
        
        else:
            # Try absolute time (e.g., "15:40", "3pm", "15:40 today", "3pm tomorrow")
            time_match = re.search(r'(\d{1,2}):(\d{2})|(\d{1,2})\s*(am|pm)', time_spec)
            
            if time_match:
                # Determine date: today, tomorrow, or specific date
                if 'tomorrow' in time_spec:
                    target_date = (datetime.now(user_tz) + timedelta(days=1)).strftime("%Y-%m-%d")
                    on_date = target_date
                else:
                    on_date = "today"
                
                # Extract time and convert to HH:MM format
                if time_match.group(1):  # HH:MM format
                    at_time = f"{time_match.group(1)}:{time_match.group(2)}"
                    display_time = at_time
                else:  # H am/pm format
                    hour = int(time_match.group(3))
                    ampm = time_match.group(4).lower()
                    
                    # Convert to 24-hour format
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0
                    
                    at_time = f"{hour:02d}:00"
                    display_time = f"{time_match.group(3)}{ampm}"
                
                reminder_service.create_reminder(message, at_time=at_time, on_date=on_date)
                
                answer = f"Reminder set: '{message}' at {display_time}"
                if on_date != "today":
                    answer += f" on {on_date}"
                return answer
            
            else:
                return f"Couldn't parse time '{time_spec}'. Try: 'in 30 minutes', 'at 3pm', or 'at 15:40'"


class ReminderQueryHandler(IntentHandler):
    """Handle reminder_query intent - list or query reminders."""
    
    actions = ['reminder_query']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Handle reminder query - list pending reminders."""
        tool = context.tool
        
        try:
            if tool == "reminder_next":
                answer = self._get_next_reminder()
            else:
                answer = self._list_reminders()
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Reminder query error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to query reminders: {str(e)}")
    
    def _list_reminders(self) -> str:
        """List all pending reminders."""
        pending = reminder_service.list_pending_reminders()
        
        if pending:
            result = "Your pending reminders:\n"
            for idx, r in enumerate(pending, 1):
                remind_time = r.remind_at.strftime("%Y-%m-%d at %I:%M %p")
                result += f"{idx}. {r.message} (at {remind_time})\n"
            result += f"\nTo delete: say 'delete reminder 1' or 'cancel reminder 2'"
            return result
        
        return "You have no pending reminders."
    
    def _get_next_reminder(self) -> str:
        """Get the next upcoming reminder."""
        pending = reminder_service.list_pending_reminders()
        
        if pending:
            next_r = pending[0]
            user_tz = settings.user_timezone
            now = datetime.now(user_tz)
            
            # Handle timezone-aware comparison
            remind_time = next_r.remind_at
            if remind_time.tzinfo is None:
                remind_time = remind_time.replace(tzinfo=user_tz)
            
            time_diff = remind_time - now
            
            minutes = int(time_diff.total_seconds() // 60)
            hours = minutes // 60
            mins = minutes % 60
            
            if hours > 0:
                time_text = f"{hours} hour(s) and {mins} minute(s)"
            else:
                time_text = f"{mins} minute(s)"
            
            return f"Your next reminder is '{next_r.message}' in {time_text}"
        
        return "You have no pending reminders."


class ReminderDeleteHandler(IntentHandler):
    """Handle reminder_delete intent - delete/cancel reminders."""
    
    actions = ['reminder_delete']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Delete a reminder by index."""
        reminder_index = context.reminder_index
        
        if reminder_index is None:
            return self._error_response(context, "Please specify which reminder to delete.")
        
        try:
            pending = reminder_service.list_pending_reminders()
            
            if not pending:
                answer = "You have no pending reminders to delete."
            
            elif reminder_index == -999:
                # Delete ALL reminders
                deleted_count = 0
                for reminder in pending:
                    if reminder_service.cancel_reminder(reminder.id):
                        deleted_count += 1
                
                if deleted_count > 0:
                    answer = f"Deleted all {deleted_count} reminder(s)"
                else:
                    answer = "Failed to delete reminders"
            
            else:
                # Handle "last" reminder (index -1)
                if reminder_index == -1:
                    reminder_index = len(pending) - 1
                
                # Validate index
                if reminder_index < 0 or reminder_index >= len(pending):
                    answer = (
                        f"Invalid reminder number. You have {len(pending)} reminder(s). "
                        f"Please specify a number between 1 and {len(pending)}."
                    )
                else:
                    reminder_to_delete = pending[reminder_index]
                    success = reminder_service.cancel_reminder(reminder_to_delete.id)
                    
                    if success:
                        answer = f"Deleted reminder: '{reminder_to_delete.message}'"
                    else:
                        answer = "Failed to delete reminder"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Reminder deletion error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to delete reminder: {str(e)}")
