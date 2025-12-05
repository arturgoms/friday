"""
Proactive Monitor - Friday's anticipatory intelligence system.

Monitors health, calendar, tasks, and context to proactively alert
and assist the user before they need to ask.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
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
    alert_key: Optional[str] = None  # Unique key for tracking ack status
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


class ReachOutBudget:
    """
    Self-regulation system to prevent Friday from being annoying.
    
    Tracks proactive message count and limits reach-outs per day.
    """
    
    def __init__(self, budget_file: Path = None):
        """Initialize reach-out budget tracker."""
        self.budget_file = budget_file or (settings.paths.data / "reach_out_budget.json")
        self.daily_limit = settings.awareness.daily_message_limit
        self.urgent_exempt = settings.awareness.urgent_exempt
        
        # Load current state
        self._state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load budget state from file."""
        try:
            if self.budget_file.exists():
                import json
                with open(self.budget_file, 'r') as f:
                    state = json.load(f)
                
                # Reset if it's a new day
                last_date = state.get("date")
                today = datetime.now().strftime("%Y-%m-%d")
                if last_date != today:
                    return self._new_day_state()
                return state
        except Exception as e:
            logger.error(f"Error loading budget state: {e}")
        
        return self._new_day_state()
    
    def _new_day_state(self) -> Dict[str, Any]:
        """Create fresh state for a new day."""
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "messages_sent": 0,
            "messages_by_priority": {
                "urgent": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "user_responses": 0,  # Track if user responds to proactive messages
            "ignored_count": 0,   # Messages that got no response
            "skipped_alerts": [],  # Alerts skipped due to budget exhaustion
        }
    
    def _save_state(self):
        """Save budget state to file."""
        try:
            import json
            self.budget_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.budget_file, 'w') as f:
                json.dump(self._state, f)
        except Exception as e:
            logger.error(f"Error saving budget state: {e}")
    
    def can_send(self, priority: AlertPriority) -> bool:
        """
        Check if we can send a proactive message.
        
        Args:
            priority: Priority of the alert
            
        Returns:
            True if we should send, False if we've hit the budget.
        """
        # Always allow urgent messages
        if self.urgent_exempt and priority == AlertPriority.URGENT:
            return True
        
        # Check if we need to reset for new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            self._state = self._new_day_state()
            self._save_state()
        
        # Count non-urgent messages
        non_urgent_count = (
            self._state["messages_by_priority"].get("high", 0) +
            self._state["messages_by_priority"].get("medium", 0) +
            self._state["messages_by_priority"].get("low", 0)
        )
        
        # Adaptive budget: if user has been ignoring messages, reduce budget
        ignored = self._state.get("ignored_count", 0)
        responses = self._state.get("user_responses", 0)
        
        if ignored > 3 and responses == 0:
            # User is ignoring us, back off significantly
            effective_limit = 1
            logger.info(f"User seems busy/ignoring - reducing budget to {effective_limit}")
        elif ignored > responses and (ignored + responses) > 2:
            # More ignores than responses, reduce slightly
            effective_limit = max(2, self.daily_limit - 2)
        else:
            effective_limit = self.daily_limit
        
        return non_urgent_count < effective_limit
    
    def record_sent(self, priority: AlertPriority):
        """Record that we sent a proactive message."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            self._state = self._new_day_state()
        
        self._state["messages_sent"] += 1
        priority_key = priority.value
        self._state["messages_by_priority"][priority_key] = (
            self._state["messages_by_priority"].get(priority_key, 0) + 1
        )
        self._save_state()
        
        logger.info(f"Budget: sent {priority_key} message, total today: {self._state['messages_sent']}")
    
    def record_user_response(self):
        """Record that user responded to a proactive message."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            self._state = self._new_day_state()
        
        self._state["user_responses"] = self._state.get("user_responses", 0) + 1
        self._save_state()
    
    def record_ignored(self):
        """Record that a proactive message was ignored."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            self._state = self._new_day_state()
        
        self._state["ignored_count"] = self._state.get("ignored_count", 0) + 1
        self._save_state()
    
    def get_remaining_budget(self) -> int:
        """Get remaining proactive message budget for today."""
        non_urgent_count = (
            self._state["messages_by_priority"].get("high", 0) +
            self._state["messages_by_priority"].get("medium", 0) +
            self._state["messages_by_priority"].get("low", 0)
        )
        return max(0, self.daily_limit - non_urgent_count)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current budget statistics."""
        return {
            "date": self._state.get("date"),
            "messages_sent": self._state.get("messages_sent", 0),
            "remaining": self.get_remaining_budget(),
            "user_responses": self._state.get("user_responses", 0),
            "ignored": self._state.get("ignored_count", 0),
            "skipped_count": len(self._state.get("skipped_alerts", [])),
        }
    
    def record_skipped(self, title: str, message: str, priority: str, category: str):
        """Record an alert that was skipped due to budget exhaustion."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            self._state = self._new_day_state()
        
        # Initialize skipped_alerts if not present (for backward compat)
        if "skipped_alerts" not in self._state:
            self._state["skipped_alerts"] = []
        
        self._state["skipped_alerts"].append({
            "title": title,
            "message": message,
            "priority": priority,
            "category": category,
            "skipped_at": datetime.now().isoformat(),
        })
        self._save_state()
    
    def get_skipped_alerts(self) -> List[Dict[str, Any]]:
        """Get list of alerts skipped today due to budget exhaustion."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._state.get("date") != today:
            return []  # New day, no skipped alerts yet
        
        return self._state.get("skipped_alerts", [])


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
        self._alert_cooldown_minutes = settings.awareness.alert_cooldown_minutes
        self._cooldown_file = settings.paths.data / "alert_cooldowns.json"
        self._acked_file = settings.paths.data / "alert_acked.json"
        self._last_alerts: Dict[str, datetime] = self._load_cooldowns()
        self._acked_alerts: Dict[str, datetime] = self._load_acked()
        
        # Self-regulation: reach-out budget
        self.budget = ReachOutBudget()
    
    def _load_cooldowns(self) -> Dict[str, datetime]:
        """Load alert cooldowns from file to survive restarts."""
        try:
            if self._cooldown_file.exists():
                import json
                with open(self._cooldown_file, 'r') as f:
                    data = json.load(f)
                # Convert ISO strings back to datetime
                cooldowns = {}
                for key, value in data.items():
                    try:
                        cooldowns[key] = datetime.fromisoformat(value)
                    except:
                        pass
                return cooldowns
        except Exception as e:
            logger.error(f"Error loading cooldowns: {e}")
        return {}
    
    def _load_acked(self) -> Dict[str, datetime]:
        """Load acknowledged alerts from file."""
        try:
            if self._acked_file.exists():
                import json
                with open(self._acked_file, 'r') as f:
                    data = json.load(f)
                acked = {}
                for key, value in data.items():
                    try:
                        acked[key] = datetime.fromisoformat(value)
                    except:
                        pass
                return acked
        except Exception as e:
            logger.error(f"Error loading acked alerts: {e}")
        return {}
    
    def _save_cooldowns(self):
        """Save alert cooldowns to file."""
        try:
            import json
            # Convert datetime to ISO strings
            data = {k: v.isoformat() for k, v in self._last_alerts.items()}
            
            # Ensure directory exists
            self._cooldown_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._cooldown_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving cooldowns: {e}")
    
    def _save_acked(self):
        """Save acknowledged alerts to file."""
        try:
            import json
            data = {k: v.isoformat() for k, v in self._acked_alerts.items()}
            self._acked_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._acked_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving acked alerts: {e}")
    
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
                sys.path.insert(0, str(settings.paths.root / "src"))
                from notify import FridayNotifier
                self._notifier = FridayNotifier()
            except Exception as e:
                logger.error(f"Failed to load notifier: {e}")
        return self._notifier
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """
        Check if we should send this alert.
        
        Logic:
        - If already acknowledged today, don't send
        - If not acknowledged and cooldown passed, send again
        - If never sent, send
        """
        # Reload acked alerts from disk (in case user acked via Telegram)
        self._acked_alerts = self._load_acked()
        
        now = datetime.now(settings.user_timezone)
        today = now.date()
        
        # Check if already acknowledged today
        if alert_key in self._acked_alerts:
            acked_time = self._acked_alerts[alert_key]
            if acked_time.date() == today:
                return False  # Already acked today, don't resend
        
        # Check cooldown (only resend after cooldown if not acked)
        if alert_key in self._last_alerts:
            last_sent = self._last_alerts[alert_key]
            # Handle timezone-naive datetimes from storage
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=settings.user_timezone)
            if (now - last_sent).total_seconds() < self._alert_cooldown_minutes * 60:
                return False  # Cooldown not passed yet
        
        return True
    
    def _mark_alert_sent(self, alert_key: str):
        """Mark an alert as sent."""
        self._last_alerts[alert_key] = datetime.now(settings.user_timezone)
        self._save_cooldowns()
    
    def acknowledge_alert(self, alert_key: str):
        """Mark an alert as acknowledged by user."""
        self._acked_alerts[alert_key] = datetime.now(settings.user_timezone)
        self._save_acked()
        logger.info(f"Alert acknowledged: {alert_key}")
    
    def is_alert_acked(self, alert_key: str) -> bool:
        """Check if alert was acknowledged today."""
        if alert_key not in self._acked_alerts:
            return False
        acked_time = self._acked_alerts[alert_key]
        today = datetime.now(settings.user_timezone).date()
        return acked_time.date() == today
    
    def cleanup_old_acks(self):
        """Remove acks older than 24 hours."""
        now = datetime.now(settings.user_timezone)
        cutoff = now - timedelta(hours=24)
        
        old_keys = []
        for k, v in self._acked_alerts.items():
            # Handle timezone-naive datetimes from storage
            ack_time = v if v.tzinfo else v.replace(tzinfo=settings.user_timezone)
            if ack_time < cutoff:
                old_keys.append(k)
        
        for key in old_keys:
            del self._acked_alerts[key]
        
        if old_keys:
            self._save_acked()
            logger.info(f"Cleaned up {len(old_keys)} old alert acks")
    
    def check_health_alerts(self) -> List[ProactiveAlert]:
        """Check health metrics for concerning patterns using comprehensive health check."""
        alerts = []
        
        if not self.health_coach:
            return alerts
        
        try:
            # Run comprehensive health check
            health_check = self.health_coach.run_health_check()
            score = health_check["health_score"]
            status = health_check["status"]
            issues = health_check.get("issues", [])
            recommendations = health_check.get("recommendations", [])
            
            logger.info(f"Health check: score={score}, status={status}, issues={len(issues)}")
            
            # Alert based on overall health score
            if score < 40:
                alert_key = "health_score_critical"
                if self._should_send_alert(alert_key):
                    recs = "\n".join(f"• {r}" for r in recommendations[:3])
                    alerts.append(ProactiveAlert(
                        category="health",
                        title=f"Health Alert: Needs Rest ({score}/100)",
                        message=f"Your health score is low. Issues detected:\n"
                               f"{chr(10).join('• ' + i for i in issues[:3])}\n\n"
                               f"**Recommendations:**\n{recs}",
                        priority=AlertPriority.HIGH,
                        alert_key=alert_key,
                        data={"health_score": score, "status": status}
                    ))
                    self._mark_alert_sent(alert_key)
            
            elif score < 60:
                alert_key = "health_score_low"
                if self._should_send_alert(alert_key):
                    recs = "\n".join(f"• {r}" for r in recommendations[:2])
                    alerts.append(ProactiveAlert(
                        category="health",
                        title=f"Health Check: Needs Attention ({score}/100)",
                        message=f"Your health could use some attention.\n\n"
                               f"**Top Recommendation:**\n{recommendations[0] if recommendations else 'Take it easy today.'}",
                        priority=AlertPriority.MEDIUM,
                        alert_key=alert_key,
                        data={"health_score": score, "status": status}
                    ))
                    self._mark_alert_sent(alert_key)
            
            # Still do individual critical checks for urgent situations
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
                            alert_key=alert_key,
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
                            alert_key=alert_key,
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
                            alert_key=alert_key,
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
                        alert_key=alert_key,
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
                            alert_key=alert_key,
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
                            alert_key=alert_key,
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
                            alert_key=alert_key,
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
                                alert_key=alert_key,
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
                                alert_key=alert_key,
                                data={"event": event.summary, "time": event_start.isoformat()}
                            ))
                            self._mark_alert_sent(alert_key)
                
                # Check for conflicts (overlapping events)
                # Filter out all-day events (events starting before 6 AM are likely all-day)
                real_events = [e for e in today_events if e.start.hour >= 6]
                
                # Deduplicate events with same name and time (same event in multiple calendars)
                seen_events = set()
                unique_events = []
                for event in real_events:
                    event_key = (event.summary.lower().strip(), event.start.hour, event.start.minute)
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        unique_events.append(event)
                
                for i, event1 in enumerate(unique_events):
                    for event2 in unique_events[i+1:]:
                        # Skip if events have similar names (likely same event in different calendars)
                        name1 = event1.summary.lower().strip()
                        name2 = event2.summary.lower().strip()
                        if name1 in name2 or name2 in name1:
                            continue
                        
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
                                    alert_key=alert_key,
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
                                    alert_key=alert_key,
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
                        alert_key=alert_key,
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
                        alert_key=alert_key,
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
                
                # Collect all rain times in next 6 hours
                rain_times = []
                for entry in forecast.get('list', [])[:3]:  # Next ~9 hours
                    weather_main = entry['weather'][0]['main'].lower()
                    entry_time = datetime.fromtimestamp(entry['dt'], tz=settings.user_timezone)
                    
                    if 'rain' in weather_main or 'storm' in weather_main:
                        rain_times.append(entry_time)
                
                if rain_times:
                    # Use date-based alert key - only ONE rain alert per day
                    alert_key = f"weather_rain_{now.strftime('%Y%m%d')}"
                    
                    if self._should_send_alert(alert_key):
                        # Format the rain times
                        if len(rain_times) == 1:
                            time_str = f"around {rain_times[0].strftime('%I:%M %p')}"
                        else:
                            times = [t.strftime('%I:%M %p') for t in rain_times]
                            time_str = f"around {times[0]} and later"
                        
                        alerts.append(ProactiveAlert(
                            category="weather",
                            title="Rain Expected Today",
                            message=f"Rain is expected {time_str}.\n\n"
                                   f"**Recommendation:** Bring an umbrella if you're going out!",
                            priority=AlertPriority.LOW,
                            alert_key=alert_key,
                            data={"times": [t.isoformat() for t in rain_times]}
                        ))
                        self._mark_alert_sent(alert_key)
        
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
                            alert_key=alert_key,
                            data={"days_since_run": 14}
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking activity patterns: {e}", exc_info=True)
        
        return alerts
    
    def check_vault_health(self) -> List[ProactiveAlert]:
        """Check Obsidian vault health and alert if issues found."""
        alerts = []
        
        try:
            from app.services.obsidian_knowledge import obsidian_knowledge
            
            health = obsidian_knowledge.run_health_check()
            score = health["health_score"]
            summary = health["summary"]
            
            # Alert if health score drops below 50 (needs work)
            if score < 50:
                alert_key = f"vault_health_low_{datetime.now().strftime('%Y%m%d')}"
                if self._should_send_alert(alert_key):
                    issues = []
                    if summary["inbox_backlog"] > 0:
                        issues.append(f"{summary['inbox_backlog']} notes in Inbox need processing")
                    if summary["stale_notes"] > 5:
                        issues.append(f"{summary['stale_notes']} notes haven't been touched in 30+ days")
                    if summary["misplaced_notes"] > 0:
                        issues.append(f"{summary['misplaced_notes']} notes may be in the wrong folder")
                    
                    issue_list = "\n".join([f"• {i}" for i in issues]) if issues else "Your vault needs attention."
                    
                    alerts.append(ProactiveAlert(
                        category="context",
                        title="Vault Health Check",
                        message=f"Your Obsidian vault health score is {score}/100.\n\n"
                               f"**Issues found:**\n{issue_list}\n\n"
                               f"Say 'vault health' for details.",
                        priority=AlertPriority.LOW,
                        alert_key=alert_key,
                        data={"health_score": score, "summary": summary}
                    ))
                    self._mark_alert_sent(alert_key)
            
            # Alert specifically about inbox backlog (separate from overall health)
            if summary["inbox_backlog"] >= 5:
                alert_key = f"vault_inbox_backlog_{datetime.now().strftime('%Y%m%d')}"
                if self._should_send_alert(alert_key):
                    alerts.append(ProactiveAlert(
                        category="context",
                        title="Inbox Backlog",
                        message=f"You have {summary['inbox_backlog']} notes sitting in your Inbox.\n\n"
                               f"**Recommendation:** Take 10 minutes to process and move them to their proper home.",
                        priority=AlertPriority.LOW,
                        alert_key=alert_key,
                        data={"inbox_count": summary["inbox_backlog"]}
                    ))
                    self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking vault health: {e}", exc_info=True)
        
        return alerts
    
    def check_commitment_follow_ups(self) -> List[ProactiveAlert]:
        """Check for commitments Friday made that need follow-up."""
        alerts = []
        
        try:
            from app.services.conversation_memory import conversation_memory
            
            # Get pending follow-ups
            pending = conversation_memory.get_pending_follow_ups()
            
            now = datetime.now(settings.user_timezone)
            
            for item in pending:
                # Check if follow-up date has passed
                if item.follow_up_date:
                    follow_up_dt = datetime.fromisoformat(str(item.follow_up_date))
                    if follow_up_dt.tzinfo is None:
                        follow_up_dt = follow_up_dt.replace(tzinfo=settings.user_timezone)
                    
                    if follow_up_dt <= now:
                        alert_key = f"commitment_followup_{item.id}"
                        if self._should_send_alert(alert_key):
                            alerts.append(ProactiveAlert(
                                category="context",
                                title="Follow-up Reminder",
                                message=f"I committed to follow up on: **{item.topic}**\n\n"
                                       f"Context: {item.context or 'No additional context'}",
                                priority=AlertPriority.MEDIUM,
                                alert_key=alert_key,
                                data={"commitment_id": item.id, "topic": item.topic}
                            ))
                            self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking commitment follow-ups: {e}", exc_info=True)
        
        return alerts
    
    def check_conversation_staleness(self) -> List[ProactiveAlert]:
        """Check if user hasn't talked to Friday in a while and reach out."""
        alerts = []
        
        try:
            # Check last interaction time from conversation memory or other sources
            from app.services.conversation_memory import conversation_memory
            
            stats = conversation_memory.get_stats()
            
            # Get the most recent interaction timestamp
            # We'll check the conversation memory files for modification time
            conv_path = settings.conversations_path
            
            if conv_path.exists():
                # Get the most recent file modification in conversations folder
                latest_mod = None
                for f in conv_path.glob("*.json"):
                    mod_time = datetime.fromtimestamp(f.stat().st_mtime)
                    if latest_mod is None or mod_time > latest_mod:
                        latest_mod = mod_time
                
                if latest_mod:
                    now = datetime.now()
                    hours_since = (now - latest_mod).total_seconds() / 3600
                    
                    # If more than 48 hours since last meaningful interaction
                    # and it's a reasonable time (9am-9pm)
                    current_hour = datetime.now(settings.user_timezone).hour
                    if hours_since > 48 and 9 <= current_hour <= 21:
                        alert_key = f"conversation_stale_{now.strftime('%Y%m%d')}"
                        if self._should_send_alert(alert_key):
                            # Choose a friendly check-in message
                            messages = [
                                "Hey! Just checking in. Anything on your mind today?",
                                "Hi there! It's been a couple days. How are things going?",
                                "Hey! Noticed we haven't chatted in a bit. Everything alright?",
                            ]
                            import random
                            msg = random.choice(messages)
                            
                            alerts.append(ProactiveAlert(
                                category="context",
                                title="Check-in",
                                message=msg,
                                priority=AlertPriority.LOW,
                                alert_key=alert_key,
                                data={"hours_since_last": hours_since}
                            ))
                            self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking conversation staleness: {e}", exc_info=True)
        
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
                            alert_key=alert_key,
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
        
        # Vault health checks
        all_alerts.extend(self.check_vault_health())
        
        # Commitment follow-ups (things Friday promised to do)
        all_alerts.extend(self.check_commitment_follow_ups())
        
        # Conversation staleness (check-in if user hasn't talked in a while)
        all_alerts.extend(self.check_conversation_staleness())
        
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
        """Send alerts via Telegram with Ack button, respecting reach-out budget."""
        if not alerts:
            return
        
        if not self.notifier:
            logger.error("Cannot send alerts: notifier not available")
            return
        
        sent_count = 0
        skipped_count = 0
        
        for alert in alerts:
            try:
                # Check reach-out budget before sending
                if not self.budget.can_send(alert.priority):
                    logger.info(f"Skipping alert '{alert.title}' - reach-out budget exhausted")
                    # Record the skipped alert for later viewing
                    self.budget.record_skipped(
                        title=alert.title,
                        message=alert.message,
                        priority=alert.priority.value if hasattr(alert.priority, 'value') else str(alert.priority),
                        category=alert.category
                    )
                    skipped_count += 1
                    continue
                
                # Use send_proactive_alert which includes the Ack button
                self.notifier.send_proactive_alert(
                    title=alert.title,
                    message=alert.message,
                    alert_key=alert.alert_key,
                    category=alert.category
                )
                
                # Record in budget
                self.budget.record_sent(alert.priority)
                sent_count += 1
                
                logger.info(f"Sent proactive alert: {alert.title} (key: {alert.alert_key})")
            except Exception as e:
                logger.error(f"Failed to send alert '{alert.title}': {e}")
    
    def check_and_notify(self):
        """Run all checks and send any alerts."""
        alerts = self.run_all_checks()
        self.send_alerts(alerts)
    
    def record_user_engagement(self, responded: bool = True):
        """
        Record user engagement with proactive messages.
        
        Call this from telegram_bot when user responds to Friday.
        """
        if responded:
            self.budget.record_user_response()
        else:
            self.budget.record_ignored()
    
    def get_budget_stats(self) -> Dict[str, Any]:
        """Get current reach-out budget statistics."""
        return self.budget.get_stats()
    
    def get_skipped_alerts(self) -> List[Dict[str, Any]]:
        """Get list of alerts skipped today due to budget exhaustion."""
        return self.budget.get_skipped_alerts()


# Singleton instance
proactive_monitor = ProactiveMonitor()
