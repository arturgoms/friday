"""
Proactive Monitor - Friday's anticipatory intelligence system.

Monitors health, calendar, tasks, and context to proactively alert
and assist the user before they need to ask.
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.core.logging import logger


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"           # Informational, can wait
    MEDIUM = "medium"     # Should see soon
    HIGH = "high"         # Important, notify now
    URGENT = "urgent"     # Critical, immediate attention


@dataclass
class ProactiveAlert:
    """A proactive alert/notification."""
    category: str         # health, calendar, task, reminder, context
    title: str
    message: str
    priority: AlertPriority
    data: Optional[Dict] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(settings.user_timezone)
    
    def to_telegram_message(self) -> str:
        """Format alert for Telegram."""
        emoji_map = {
            "health": "🏥",
            "calendar": "📅",
            "task": "✅",
            "reminder": "⏰",
            "context": "💡",
            "weather": "🌤️",
        }
        priority_emoji = {
            AlertPriority.LOW: "",
            AlertPriority.MEDIUM: "",
            AlertPriority.HIGH: "⚠️ ",
            AlertPriority.URGENT: "🚨 ",
        }
        
        emoji = emoji_map.get(self.category, "📢")
        priority = priority_emoji.get(self.priority, "")
        
        return f"{priority}{emoji} **{self.title}**\n{self.message}"


class ProactiveMonitor:
    """
    Monitors various data sources and generates proactive alerts.
    
    Runs periodically to check for conditions that warrant user notification.
    """
    
    def __init__(self):
        """Initialize the proactive monitor."""
        self._health_coach = None
        self._calendar_service = None
        self._notifier = None
        self._last_alerts: Dict[str, datetime] = {}  # Prevent duplicate alerts
        self._alert_cooldown_minutes = 60  # Don't repeat same alert within this time
    
    @property
    def health_coach(self):
        """Lazy load health coach."""
        if self._health_coach is None:
            try:
                from app.services.health_coach import get_health_coach
                self._health_coach = get_health_coach()
            except Exception as e:
                logger.error(f"Failed to load health coach: {e}")
        return self._health_coach
    
    @property
    def calendar_service(self):
        """Lazy load calendar service."""
        if self._calendar_service is None:
            try:
                from app.services.unified_calendar_service import UnifiedCalendarService
                self._calendar_service = UnifiedCalendarService()
            except Exception as e:
                logger.error(f"Failed to load calendar service: {e}")
        return self._calendar_service
    
    @property
    def notifier(self):
        """Lazy load notifier."""
        if self._notifier is None:
            try:
                import sys
                sys.path.insert(0, '/home/artur/friday/src')
                from notify import FridayNotifier
                self._notifier = FridayNotifier()
            except Exception as e:
                logger.error(f"Failed to load notifier: {e}")
        return self._notifier
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if we should send this alert (cooldown check)."""
        now = datetime.now(settings.user_timezone)
        
        if alert_key in self._last_alerts:
            last_sent = self._last_alerts[alert_key]
            if (now - last_sent).total_seconds() < self._alert_cooldown_minutes * 60:
                return False
        
        return True
    
    def _mark_alert_sent(self, alert_key: str):
        """Mark an alert as sent."""
        self._last_alerts[alert_key] = datetime.now(settings.user_timezone)
    
    def check_health_alerts(self) -> List[ProactiveAlert]:
        """Check health metrics for concerning patterns."""
        alerts = []
        
        if not self.health_coach:
            return alerts
        
        try:
            # Get current recovery status
            recovery = self.health_coach.get_recovery_status()
            
            # Body Battery check
            if 'body_battery' in recovery:
                bb = recovery['body_battery']
                
                if bb <= 10:
                    alert_key = "health_bb_critical"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Critical Energy Level",
                            message=f"Your Body Battery is at {bb}/100. You're running on empty.\n\n"
                                   f"**Recommendation:** Stop what you're doing and rest. "
                                   f"Consider a short nap or at minimum, sit down and relax for 15-20 minutes.",
                            priority=AlertPriority.URGENT,
                            data={"body_battery": bb}
                        ))
                        self._mark_alert_sent(alert_key)
                
                elif bb <= 20:
                    alert_key = "health_bb_low"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Low Energy Alert",
                            message=f"Your Body Battery is at {bb}/100.\n\n"
                                   f"**Recommendation:** Take it easy. Avoid intense activities "
                                   f"and prioritize rest when possible.",
                            priority=AlertPriority.HIGH,
                            data={"body_battery": bb}
                        ))
                        self._mark_alert_sent(alert_key)
            
            # Training Readiness check
            if 'training_readiness' in recovery:
                tr = recovery['training_readiness']
                
                if tr < 30:
                    alert_key = "health_tr_low"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Low Training Readiness",
                            message=f"Your Training Readiness is {tr}/100.\n\n"
                                   f"**Recommendation:** Skip intense workouts today. "
                                   f"Light stretching or a gentle walk is okay, but your body needs recovery.",
                            priority=AlertPriority.HIGH,
                            data={"training_readiness": tr}
                        ))
                        self._mark_alert_sent(alert_key)
            
            # Recovery Time check
            if 'recovery_time' in recovery and recovery['recovery_time'] > 48:
                rt = recovery['recovery_time']
                alert_key = "health_recovery_high"
                if self._should_send_alert(alert_key):
                    alerts.append(ProactiveAlert(
                        category="health",
                        title="Extended Recovery Needed",
                        message=f"You have {rt} hours of recovery time remaining.\n\n"
                               f"**Recommendation:** Your body is still recovering from recent activity. "
                               f"Focus on sleep, hydration, and nutrition.",
                        priority=AlertPriority.MEDIUM,
                        data={"recovery_time": rt}
                    ))
                    self._mark_alert_sent(alert_key)
            
            # HRV check (if significantly below 7-day average)
            if 'hrv_latest' in recovery and 'hrv_7day_avg' in recovery:
                hrv = recovery['hrv_latest']
                hrv_avg = recovery['hrv_7day_avg']
                
                if hrv_avg > 0 and hrv < hrv_avg * 0.7:  # 30% below average
                    alert_key = "health_hrv_low"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Stress Indicator",
                            message=f"Your HRV ({hrv}ms) is significantly below your average ({hrv_avg}ms).\n\n"
                                   f"**Recommendation:** This can indicate stress or fatigue. "
                                   f"Consider meditation, deep breathing, or reducing today's demands.",
                            priority=AlertPriority.MEDIUM,
                            data={"hrv": hrv, "hrv_avg": hrv_avg}
                        ))
                        self._mark_alert_sent(alert_key)
            
            # Check last night's sleep
            sleep_data = self.health_coach.get_sleep_data(days=1)
            if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
                sleep = sleep_data["sleep_records"][0]
                
                # Poor sleep score
                if sleep['sleep_score'] < 50:
                    alert_key = "health_sleep_poor"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Poor Sleep Quality",
                            message=f"Last night's sleep score was {sleep['sleep_score']}/100 "
                                   f"({sleep['total_sleep_hours']}h).\n\n"
                                   f"**Recommendation:** Consider a lighter day. "
                                   f"Avoid caffeine after 2pm and try to go to bed earlier tonight.",
                            priority=AlertPriority.HIGH,
                            data={"sleep_score": sleep['sleep_score']}
                        ))
                        self._mark_alert_sent(alert_key)
                
                # Very short sleep
                elif sleep['total_sleep_hours'] < 5:
                    alert_key = "health_sleep_short"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Sleep Deficit",
                            message=f"You only got {sleep['total_sleep_hours']}h of sleep last night.\n\n"
                                   f"**Recommendation:** If possible, take a 20-minute nap today. "
                                   f"Prioritize getting to bed early tonight.",
                            priority=AlertPriority.HIGH,
                            data={"sleep_hours": sleep['total_sleep_hours']}
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking health alerts: {e}", exc_info=True)
        
        return alerts
    
    def check_calendar_alerts(self) -> List[ProactiveAlert]:
        """Check calendar for upcoming events and conflicts."""
        alerts = []
        
        if not self.calendar_service:
            return alerts
        
        try:
            now = datetime.now(settings.user_timezone)
            
            # Get today's events
            today_events = self.calendar_service.get_today_events()
            
            if today_events:
                for event in today_events:
                    event_start = event.start
                    
                    # Skip all-day events (events starting before 6 AM)
                    if event_start.hour < 6:
                        continue
                    
                    # Make timezone-aware if needed
                    if event_start.tzinfo is None:
                        event_start = event_start.replace(tzinfo=settings.user_timezone)
                    
                    time_until = (event_start - now).total_seconds() / 60  # minutes
                    
                    # Upcoming event in 30 minutes
                    if 25 <= time_until <= 35:
                        alert_key = f"calendar_upcoming_{event.summary}_{event_start.isoformat()}"
                        if self._should_send_alert(alert_key):
                            location_str = f"\n📍 {event.location}" if event.location else ""
                            alerts.append(ProactiveAlert(
                                category="calendar",
                                title="Upcoming Event",
                                message=f"**{event.summary}** starts in ~30 minutes "
                                       f"({event_start.strftime('%I:%M %p')}){location_str}",
                                priority=AlertPriority.MEDIUM,
                                data={"event": event.summary, "time": event_start.isoformat()}
                            ))
                            self._mark_alert_sent(alert_key)
                    
                    # Event starting in 5 minutes (urgent reminder)
                    elif 3 <= time_until <= 7:
                        alert_key = f"calendar_imminent_{event.summary}_{event_start.isoformat()}"
                        if self._should_send_alert(alert_key):
                            location_str = f"\n📍 {event.location}" if event.location else ""
                            alerts.append(ProactiveAlert(
                                category="calendar",
                                title="Event Starting Soon!",
                                message=f"**{event.summary}** starts in 5 minutes!{location_str}",
                                priority=AlertPriority.HIGH,
                                data={"event": event.summary, "time": event_start.isoformat()}
                            ))
                            self._mark_alert_sent(alert_key)
                
                # Check for conflicts (overlapping events)
                # Filter out all-day events (events starting before 6 AM are likely all-day)
                real_events = [e for e in today_events if e.start.hour >= 6]
                
                for i, event1 in enumerate(real_events):
                    for event2 in real_events[i+1:]:
                        # Check if events overlap
                        e1_start = event1.start
                        e1_end = event1.end if hasattr(event1, 'end') and event1.end else e1_start + timedelta(hours=1)
                        e2_start = event2.start
                        
                        if e1_start <= e2_start < e1_end:
                            alert_key = f"calendar_conflict_{event1.summary}_{event2.summary}"
                            if self._should_send_alert(alert_key):
                                alerts.append(ProactiveAlert(
                                    category="calendar",
                                    title="Schedule Conflict",
                                    message=f"You have overlapping events:\n"
                                           f"• {event1.summary} ({event1.start.strftime('%I:%M %p')})\n"
                                           f"• {event2.summary} ({event2.start.strftime('%I:%M %p')})\n\n"
                                           f"You may need to reschedule one of them.",
                                    priority=AlertPriority.HIGH,
                                    data={"event1": event1.summary, "event2": event2.summary}
                                ))
                                self._mark_alert_sent(alert_key)
            
            # Check tomorrow for early events (warn in evening)
            current_hour = now.hour
            if 18 <= current_hour <= 23:  # Evening hours
                tomorrow_events = self.calendar_service.get_tomorrow_events()
                if tomorrow_events:
                    # Find earliest real event (after 6am)
                    for event in tomorrow_events:
                        event_hour = event.start.hour
                        if 6 <= event_hour <= 8:  # Early morning event
                            alert_key = f"calendar_early_tomorrow_{event.summary}"
                            if self._should_send_alert(alert_key):
                                alerts.append(ProactiveAlert(
                                    category="calendar",
                                    title="Early Start Tomorrow",
                                    message=f"You have **{event.summary}** at "
                                           f"{event.start.strftime('%I:%M %p')} tomorrow.\n\n"
                                           f"Consider going to bed early tonight!",
                                    priority=AlertPriority.MEDIUM,
                                    data={"event": event.summary}
                                ))
                                self._mark_alert_sent(alert_key)
                            break
        
        except Exception as e:
            logger.error(f"Error checking calendar alerts: {e}", exc_info=True)
        
        return alerts
    
    def check_task_alerts(self) -> List[ProactiveAlert]:
        """Check for overdue or due-soon tasks."""
        alerts = []
        
        try:
            from app.services.task_manager import task_manager
            
            # Get today's tasks
            today_tasks = task_manager.get_tasks_for_today()
            
            # Check for urgent/high priority tasks due today
            urgent_tasks = [t for t in today_tasks if t.priority.value in ['urgent', 'high']]
            
            if urgent_tasks:
                alert_key = "tasks_urgent_today"
                if self._should_send_alert(alert_key):
                    task_list = "\n".join([f"• {t.title}" for t in urgent_tasks[:5]])
                    alerts.append(ProactiveAlert(
                        category="task",
                        title=f"{len(urgent_tasks)} Important Task(s) Due Today",
                        message=f"Don't forget:\n{task_list}",
                        priority=AlertPriority.MEDIUM,
                        data={"count": len(urgent_tasks)}
                    ))
                    self._mark_alert_sent(alert_key)
            
            # Get overdue tasks (tasks scheduled before today that aren't done)
            from app.services.task_manager import TaskStatus
            overdue_tasks = task_manager.list_tasks(status=TaskStatus.TODO)
            now = datetime.now(settings.user_timezone)
            overdue_tasks = [t for t in overdue_tasks 
                           if t.scheduled_for and t.scheduled_for.date() < now.date()]
            
            if overdue_tasks:
                alert_key = f"tasks_overdue_{len(overdue_tasks)}"
                if self._should_send_alert(alert_key):
                    task_list = "\n".join([f"• {t.title}" for t in overdue_tasks[:5]])
                    more_text = f"\n... and {len(overdue_tasks) - 5} more" if len(overdue_tasks) > 5 else ""
                    alerts.append(ProactiveAlert(
                        category="task",
                        title=f"{len(overdue_tasks)} Overdue Task(s)",
                        message=f"These tasks are past due:\n{task_list}{more_text}",
                        priority=AlertPriority.HIGH,
                        data={"count": len(overdue_tasks)}
                    ))
                    self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking task alerts: {e}", exc_info=True)
        
        return alerts
    
    def check_weather_alerts(self) -> List[ProactiveAlert]:
        """Check weather for relevant alerts."""
        alerts = []
        
        try:
            import requests
            
            weather_api_key = os.getenv('WEATHER_API_KEY')
            city = os.getenv('WEATHER_CITY', 'São Paulo')
            
            if not weather_api_key:
                return alerts
            
            # Get forecast
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={weather_api_key}&units=metric"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                forecast = response.json()
                now = datetime.now(settings.user_timezone)
                
                # Check next 6 hours for rain
                for entry in forecast.get('list', [])[:3]:  # Next ~9 hours
                    weather_main = entry['weather'][0]['main'].lower()
                    entry_time = datetime.fromtimestamp(entry['dt'], tz=settings.user_timezone)
                    
                    if 'rain' in weather_main or 'storm' in weather_main:
                        alert_key = f"weather_rain_{entry_time.strftime('%Y%m%d%H')}"
                        if self._should_send_alert(alert_key):
                            alerts.append(ProactiveAlert(
                                category="weather",
                                title="Rain Expected",
                                message=f"Rain is expected around {entry_time.strftime('%I:%M %p')}.\n\n"
                                       f"**Recommendation:** Bring an umbrella if you're going out!",
                                priority=AlertPriority.LOW,
                                data={"time": entry_time.isoformat()}
                            ))
                            self._mark_alert_sent(alert_key)
                        break  # Only one rain alert
        
        except Exception as e:
            logger.error(f"Error checking weather alerts: {e}", exc_info=True)
        
        return alerts
    
    def check_activity_patterns(self) -> List[ProactiveAlert]:
        """Check for unusual activity patterns."""
        alerts = []
        
        if not self.health_coach:
            return alerts
        
        try:
            # Check running frequency
            summary = self.health_coach.get_running_summary(days=14)
            
            if "run_count" in summary:
                runs_in_14_days = summary['run_count']
                
                # If usually runs but hasn't in a while
                if runs_in_14_days == 0:
                    alert_key = "activity_no_runs_14d"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="No Running Activity",
                            message="You haven't logged a run in the past 2 weeks.\n\n"
                                   "Is everything okay? Even a short walk can help maintain fitness.",
                            priority=AlertPriority.LOW,
                            data={"days_since_run": 14}
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking activity patterns: {e}", exc_info=True)
        
        return alerts
    
    def check_dynamic_alerts(self) -> List[ProactiveAlert]:
        """Check user-created dynamic alerts from conversations."""
        alerts = []
        
        try:
            from app.services.alert_store import alert_store
            
            # Get all active alerts
            dynamic_alerts = alert_store.list_active_alerts()
            now = datetime.now(settings.user_timezone)
            
            for dyn_alert in dynamic_alerts:
                if dyn_alert.should_trigger(now):
                    alert_key = f"dynamic_{dyn_alert.alert_id}"
                    if self._should_send_alert(alert_key):
                        # Map priority
                        priority_map = {
                            "low": AlertPriority.LOW,
                            "medium": AlertPriority.MEDIUM,
                            "high": AlertPriority.HIGH,
                            "urgent": AlertPriority.URGENT,
                        }
                        
                        alerts.append(ProactiveAlert(
                            category="context",
                            title=dyn_alert.title,
                            message=dyn_alert.description,
                            priority=priority_map.get(dyn_alert.priority, AlertPriority.MEDIUM),
                            data={"alert_id": dyn_alert.alert_id}
                        ))
                        
                        # Mark as triggered
                        alert_store.mark_triggered(dyn_alert.alert_id)
                        
                        # Deactivate if not recurring
                        if not dyn_alert.recurring_pattern:
                            alert_store.deactivate_alert(dyn_alert.alert_id)
                        
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking dynamic alerts: {e}", exc_info=True)
        
        return alerts
    
    def run_all_checks(self) -> List[ProactiveAlert]:
        """Run all proactive checks and return alerts."""
        all_alerts = []
        
        logger.info("Running proactive monitoring checks...")
        
        # Health checks
        all_alerts.extend(self.check_health_alerts())
        
        # Calendar checks
        all_alerts.extend(self.check_calendar_alerts())
        
        # Task checks
        all_alerts.extend(self.check_task_alerts())
        
        # Weather checks
        all_alerts.extend(self.check_weather_alerts())
        
        # Activity pattern checks
        all_alerts.extend(self.check_activity_patterns())
        
        # Dynamic alerts from conversations (Friday's self-learning)
        all_alerts.extend(self.check_dynamic_alerts())
        
        # Sort by priority
        priority_order = {
            AlertPriority.URGENT: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }
        all_alerts.sort(key=lambda a: priority_order.get(a.priority, 99))
        
        logger.info(f"Proactive check complete: {len(all_alerts)} alert(s) generated")
        
        return all_alerts
    
    def send_alerts(self, alerts: List[ProactiveAlert]):
        """Send alerts via Telegram."""
        if not alerts:
            return
        
        if not self.notifier:
            logger.error("Cannot send alerts: notifier not available")
            return
        
        for alert in alerts:
            try:
                message = alert.to_telegram_message()
                self.notifier.send_message(message, parse_mode="Markdown")
                logger.info(f"Sent proactive alert: {alert.title}")
            except Exception as e:
                logger.error(f"Failed to send alert '{alert.title}': {e}")
    
    def check_and_notify(self):
        """Run all checks and send any alerts."""
        alerts = self.run_all_checks()
        self.send_alerts(alerts)


# Singleton instance
proactive_monitor = ProactiveMonitor()
