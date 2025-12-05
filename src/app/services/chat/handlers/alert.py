"""Alert intent handlers - create, list, delete alerts."""
import calendar as cal_module
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.alert_store import alert_store, AlertType


class AlertCreateHandler(IntentHandler):
    """Handle alert_create intent - create proactive alerts."""
    
    actions = ['alert_create']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Create a new proactive alert."""
        alert_data = context.alert_data
        
        if not alert_data:
            return self._error_response(context, "No alert data provided")
        
        try:
            title = alert_data.get('title', 'New Alert')
            description = alert_data.get('description', '')
            trigger_condition = alert_data.get('trigger_condition')
            trigger_date_str = alert_data.get('trigger_date')
            recurring = alert_data.get('recurring')
            
            # Determine alert type
            if trigger_condition:
                alert_type = AlertType.CONDITION
            elif recurring:
                alert_type = AlertType.RECURRING
            else:
                alert_type = AlertType.DATE_REMINDER
            
            # Parse trigger date if provided
            trigger_date = None
            if trigger_date_str:
                trigger_date = self._parse_trigger_date(trigger_date_str)
            
            alert = alert_store.create_alert(
                title=title,
                description=description,
                alert_type=alert_type,
                trigger_date=trigger_date,
                trigger_condition=trigger_condition,
                recurring_pattern=recurring,
                source_context=f"Created from chat: {context.message[:200]}"
            )
            
            answer = f"Created alert: **{title}**\n"
            if recurring:
                answer += f"Recurring: {recurring}\n"
            if trigger_condition:
                answer += f"Condition: {trigger_condition}\n"
            if trigger_date:
                answer += f"First trigger: {trigger_date.strftime('%a, %b %d at %I:%M %p')}"
            answer += f"\n\nAlert ID: {alert.alert_id}"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Alert create error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to create alert: {str(e)}")
    
    def _parse_trigger_date(self, trigger_date_str: str) -> Optional[datetime]:
        """Parse trigger date string to datetime."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        
        # Parse day name for recurring
        day_names = [d.lower() for d in cal_module.day_name]
        if trigger_date_str.lower() in day_names:
            target_day = day_names.index(trigger_date_str.lower())
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=9, minute=0)
        
        return None


class AlertListHandler(IntentHandler):
    """Handle alert_list intent - list active alerts."""
    
    actions = ['alert_list']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """List all active alerts."""
        try:
            alerts = alert_store.list_active_alerts()
            
            if alerts:
                result = "Active alerts:\n\n"
                for alert in alerts:
                    type_icon = {
                        "date_reminder": "Date",
                        "recurring": "Recurring",
                        "condition": "Condition",
                        "health_watch": "Health",
                        "deadline": "Deadline",
                    }.get(alert.alert_type.value, "Alert")
                    
                    trigger_info = ""
                    if alert.recurring_pattern:
                        trigger_info = f" ({alert.recurring_pattern})"
                    elif alert.trigger_date:
                        trigger_info = f" ({alert.trigger_date.strftime('%b %d')})"
                    
                    result += f"- [{type_icon}] {alert.title}{trigger_info}\n"
                    result += f"  ID: {alert.alert_id}\n\n"
                answer = result
            else:
                answer = "You have no active alerts."
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Alert list error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to list alerts: {str(e)}")


class AlertDeleteHandler(IntentHandler):
    """Handle alert_delete intent - delete/deactivate alerts."""
    
    actions = ['alert_delete']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Delete/deactivate an alert."""
        alert_data = context.alert_data
        
        if not alert_data:
            return self._error_response(context, "No alert data provided")
        
        try:
            alert_id_or_topic = alert_data.get('alert_id', '')
            
            if not alert_id_or_topic:
                return self._error_response(context, "Please specify which alert to delete.")
            
            # Try to find by ID or topic
            alerts = alert_store.list_active_alerts()
            found_alert = None
            
            search_lower = alert_id_or_topic.lower()
            for alert in alerts:
                if alert.alert_id == alert_id_or_topic or search_lower in alert.title.lower():
                    found_alert = alert
                    break
            
            if found_alert:
                alert_store.deactivate_alert(found_alert.alert_id)
                answer = f"Deactivated alert: {found_alert.title}"
            else:
                answer = f"Alert not found: '{alert_id_or_topic}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Alert delete error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to delete alert: {str(e)}")
