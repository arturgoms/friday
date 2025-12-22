"""
Awareness Engine - Friday's anticipatory intelligence system.

An evolution of ProactiveMonitor that adds:
- Fusion checks (cross-domain analysis)
- Behavioral pattern recognition
- Infrastructure monitoring
- Anticipatory intelligence

This is the brain that makes Friday truly proactive.
"""
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import logger

# Import existing classes from proactive_monitor
from app.services.proactive_monitor import (
    ProactiveMonitor,
    ProactiveAlert,
    AlertPriority,
    ReachOutBudget,
)


@dataclass
class PatternData:
    """Stores behavioral pattern data."""
    # Sleep patterns
    avg_bedtime_hour: float = 23.0
    avg_bedtime_minute: float = 0.0
    avg_wake_hour: float = 7.0
    avg_wake_minute: float = 0.0
    sleep_consistency_score: float = 0.0  # 0-100, how consistent sleep schedule is
    
    # Workout patterns
    avg_workouts_per_week: float = 0.0
    typical_workout_days: List[int] = field(default_factory=list)  # 0=Mon, 6=Sun
    days_since_last_workout: int = 0
    last_workout_date: Optional[str] = None
    
    # Activity patterns
    avg_daily_steps: int = 0
    avg_active_minutes: int = 0
    
    # Last updated
    last_updated: Optional[str] = None


class AwarenessEngine(ProactiveMonitor):
    """
    Enhanced proactive monitoring with fusion checks and pattern recognition.
    
    Extends ProactiveMonitor with:
    - Cross-domain fusion analysis
    - Behavioral pattern tracking
    - Infrastructure health monitoring
    - Anticipatory intelligence
    """
    
    def __init__(self):
        """Initialize the awareness engine."""
        super().__init__()
        
        # Pattern data storage
        self._patterns_file = settings.paths.data / "awareness_patterns.json"
        self._patterns = self._load_patterns()
        
        # Infrastructure check cache
        self._last_infra_check: Optional[datetime] = None
        self._infra_check_interval = timedelta(minutes=15)
        
        # Lazy-loaded services
        self._obsidian_service = None
        self._task_manager = None
        self._vector_store = None
    
    # =========================================================================
    # Pattern Storage
    # =========================================================================
    
    def _load_patterns(self) -> PatternData:
        """Load pattern data from file."""
        try:
            if self._patterns_file.exists():
                with open(self._patterns_file, 'r') as f:
                    data = json.load(f)
                return PatternData(**data)
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
        return PatternData()
    
    def _save_patterns(self):
        """Save pattern data to file."""
        try:
            self._patterns_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'avg_bedtime_hour': self._patterns.avg_bedtime_hour,
                'avg_bedtime_minute': self._patterns.avg_bedtime_minute,
                'avg_wake_hour': self._patterns.avg_wake_hour,
                'avg_wake_minute': self._patterns.avg_wake_minute,
                'sleep_consistency_score': self._patterns.sleep_consistency_score,
                'avg_workouts_per_week': self._patterns.avg_workouts_per_week,
                'typical_workout_days': self._patterns.typical_workout_days,
                'days_since_last_workout': self._patterns.days_since_last_workout,
                'last_workout_date': self._patterns.last_workout_date,
                'avg_daily_steps': self._patterns.avg_daily_steps,
                'avg_active_minutes': self._patterns.avg_active_minutes,
                'last_updated': datetime.now().isoformat(),
            }
            with open(self._patterns_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")
    
    # =========================================================================
    # Lazy-loaded Services
    # =========================================================================
    
    @property
    def obsidian_service(self):
        """Lazy load obsidian service."""
        if self._obsidian_service is None:
            try:
                from app.services.obsidian import obsidian_service
                self._obsidian_service = obsidian_service
            except Exception as e:
                logger.error(f"Failed to load obsidian service: {e}")
        return self._obsidian_service
    
    @property
    def task_manager(self):
        """Lazy load task manager."""
        if self._task_manager is None:
            try:
                from app.services.task_manager import task_manager
                self._task_manager = task_manager
            except Exception as e:
                logger.error(f"Failed to load task manager: {e}")
        return self._task_manager
    
    @property
    def vector_store(self):
        """Lazy load vector store for semantic search."""
        if self._vector_store is None:
            try:
                from app.services.vector_store import vector_store
                self._vector_store = vector_store
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}")
        return self._vector_store
    
    # =========================================================================
    # FUSION CHECKS: Health + Calendar
    # =========================================================================
    
    def check_workout_readiness(self) -> List[ProactiveAlert]:
        """
        Check if upcoming calendar events look like workouts and assess readiness.
        
        Before a workout event, checks Training Readiness and Body Battery.
        If metrics are low, suggests rescheduling or a lighter alternative.
        """
        alerts = []
        
        if not self.health_coach or not self.calendar_service:
            return alerts
        
        try:
            now = datetime.now(settings.user_timezone)
            today_events = self.calendar_service.get_today_events()
            
            # Keywords that suggest a workout
            workout_keywords = [
                'gym', 'workout', 'run', 'running', 'leg day', 'arm day', 
                'chest day', 'back day', 'push', 'pull', 'crossfit', 'hiit',
                'pilates', 'yoga', 'swim', 'cycling', 'bike', 'training',
                'exercise', 'cardio', 'strength', 'lift', 'squats', 'deadlift'
            ]
            
            for event in today_events:
                event_name = event.summary.lower()
                event_start = event.start
                
                # Make timezone-aware if needed
                if event_start.tzinfo is None:
                    event_start = event_start.replace(tzinfo=settings.user_timezone)
                
                # Check if this looks like a workout
                is_workout = any(kw in event_name for kw in workout_keywords)
                if not is_workout:
                    continue
                
                # Check if workout is upcoming (within next 3 hours)
                time_until = (event_start - now).total_seconds() / 3600  # hours
                if not (0.5 <= time_until <= 3):
                    continue
                
                # Get health metrics
                recovery = self.health_coach.get_recovery_status()
                body_battery = recovery.get('body_battery', 100)
                training_readiness = recovery.get('training_readiness', 100)
                recovery_time = recovery.get('recovery_time', 0)
                
                # Generate alert if metrics are concerning
                alert_key = f"fusion_workout_readiness_{event.summary}_{event_start.date()}"
                
                if training_readiness < 30 or body_battery < 25:
                    # Critical - suggest rescheduling
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title=f"Workout Advisory: {event.summary}",
                            message=f"Your **{event.summary}** is in {time_until:.1f} hours, but:\n"
                                   f"• Training Readiness: {training_readiness}/100\n"
                                   f"• Body Battery: {body_battery}/100\n"
                                   f"• Recovery Time: {recovery_time}h remaining\n\n"
                                   f"**Recommendation:** Consider rescheduling or doing a very light session. "
                                   f"Your body needs more recovery.",
                            priority=AlertPriority.HIGH,
                            alert_key=alert_key,
                            data={
                                "event": event.summary,
                                "training_readiness": training_readiness,
                                "body_battery": body_battery
                            }
                        ))
                        self._mark_alert_sent(alert_key)
                
                elif training_readiness < 50 or body_battery < 40:
                    # Moderate concern - suggest lighter workout
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title=f"Workout Check: {event.summary}",
                            message=f"Heads up for **{event.summary}** in {time_until:.1f} hours:\n"
                                   f"• Training Readiness: {training_readiness}/100\n"
                                   f"• Body Battery: {body_battery}/100\n\n"
                                   f"**Recommendation:** You can still work out, but consider "
                                   f"reducing intensity or duration. Listen to your body.",
                            priority=AlertPriority.MEDIUM,
                            alert_key=alert_key,
                            data={
                                "event": event.summary,
                                "training_readiness": training_readiness,
                                "body_battery": body_battery
                            }
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error in workout readiness check: {e}", exc_info=True)
        
        return alerts
    
    def check_post_workout_recovery(self) -> List[ProactiveAlert]:
        """
        Monitor recovery after workouts and suggest optimal next session.
        
        Checks recovery time after activities and recommends when to work out again.
        """
        alerts = []
        
        if not self.health_coach:
            return alerts
        
        try:
            recovery = self.health_coach.get_recovery_status()
            recovery_time = recovery.get('recovery_time', 0)
            
            # Only alert if significant recovery time
            if recovery_time >= 24:
                # Check if there's a workout scheduled tomorrow
                if self.calendar_service:
                    tomorrow_events = self.calendar_service.get_tomorrow_events()
                    workout_keywords = ['gym', 'workout', 'run', 'training', 'exercise']
                    
                    tomorrow_workouts = [
                        e for e in tomorrow_events 
                        if any(kw in e.summary.lower() for kw in workout_keywords)
                    ]
                    
                    if tomorrow_workouts and recovery_time > 36:
                        alert_key = f"fusion_recovery_warning_{datetime.now().strftime('%Y%m%d')}"
                        if self._should_send_alert(alert_key):
                            workout_names = ", ".join([w.summary for w in tomorrow_workouts[:2]])
                            alerts.append(ProactiveAlert(
                                category="health",
                                title="Recovery vs. Tomorrow's Workout",
                                message=f"You have {recovery_time}h of recovery time remaining, "
                                       f"but **{workout_names}** is scheduled for tomorrow.\n\n"
                                       f"**Recommendation:** Consider a rest day or very light activity tomorrow "
                                       f"to allow full recovery.",
                                priority=AlertPriority.MEDIUM,
                                alert_key=alert_key,
                                data={"recovery_time": recovery_time, "workouts": workout_names}
                            ))
                            self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error in post-workout recovery check: {e}", exc_info=True)
        
        return alerts
    
    # =========================================================================
    # FUSION CHECKS: Notes + Calendar
    # =========================================================================
    
    def check_meeting_preparedness(self) -> List[ProactiveAlert]:
        """
        For upcoming meetings, search notes for attendee context.
        
        Generates a brief summary of past discussions and key points
        to help with meeting preparation.
        """
        alerts = []
        
        if not self.calendar_service or not self.vector_store:
            return alerts
        
        try:
            now = datetime.now(settings.user_timezone)
            today_events = self.calendar_service.get_today_events()
            
            # Keywords suggesting a meeting
            meeting_keywords = [
                'meeting', 'call', 'sync', '1:1', '1-1', 'standup', 'review',
                'interview', 'discussion', 'catch up', 'check-in', 'presentation'
            ]
            
            for event in today_events:
                event_name = event.summary.lower()
                event_start = event.start
                
                if event_start.tzinfo is None:
                    event_start = event_start.replace(tzinfo=settings.user_timezone)
                
                # Check if this looks like a meeting
                is_meeting = any(kw in event_name for kw in meeting_keywords)
                if not is_meeting:
                    continue
                
                # Check if meeting is upcoming (30 mins to 2 hours)
                time_until = (event_start - now).total_seconds() / 60  # minutes
                if not (30 <= time_until <= 120):
                    continue
                
                # Extract potential person names from meeting title
                # Simple heuristic: words that start with capital letter and aren't common words
                common_words = {'meeting', 'call', 'sync', 'with', 'the', 'and', 'for', 'about'}
                words = event.summary.split()
                potential_names = [
                    w for w in words 
                    if w[0].isupper() and w.lower() not in common_words and len(w) > 2
                ]
                
                if potential_names:
                    # Search notes for context about these people
                    search_query = " ".join(potential_names)
                    context, chunks = self.vector_store.query_obsidian(search_query)
                    
                    if context and len(context) > 100:  # Meaningful context found
                        alert_key = f"fusion_meeting_prep_{event.summary}_{event_start.date()}"
                        if self._should_send_alert(alert_key):
                            # Summarize the context (take first 500 chars)
                            context_preview = context[:500] + "..." if len(context) > 500 else context
                            
                            alerts.append(ProactiveAlert(
                                category="calendar",
                                title=f"Meeting Prep: {event.summary}",
                                message=f"Your meeting **{event.summary}** starts in ~{int(time_until)} mins.\n\n"
                                       f"**From your notes about {', '.join(potential_names)}:**\n"
                                       f"{context_preview}",
                                priority=AlertPriority.LOW,
                                alert_key=alert_key,
                                data={
                                    "event": event.summary,
                                    "names": potential_names,
                                    "sources": [c.path if hasattr(c, 'path') else str(c) for c in chunks]
                                }
                            ))
                            self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error in meeting preparedness check: {e}", exc_info=True)
        
        return alerts
    
    # =========================================================================
    # FUSION CHECKS: Tasks + Calendar
    # =========================================================================
    
    def check_errand_opportunities(self) -> List[ProactiveAlert]:
        """
        When leaving the house for an event, check for errands that could be done.
        
        Matches tasks tagged with locations to upcoming calendar events
        that involve going out.
        """
        alerts = []
        
        if not self.calendar_service or not self.task_manager:
            return alerts
        
        try:
            now = datetime.now(settings.user_timezone)
            today_events = self.calendar_service.get_today_events()
            
            # Keywords suggesting going out
            out_keywords = [
                'dentist', 'doctor', 'appointment', 'clinic', 'hospital',
                'meeting', 'lunch', 'dinner', 'coffee', 'gym', 'mall',
                'store', 'shop', 'market', 'pickup', 'visit'
            ]
            
            # Location-based task contexts
            errand_contexts = ['errands', 'shopping', 'outside', 'store']
            
            for event in today_events:
                event_name = event.summary.lower()
                event_start = event.start
                
                if event_start.tzinfo is None:
                    event_start = event_start.replace(tzinfo=settings.user_timezone)
                
                # Check if this involves going out
                is_outing = any(kw in event_name for kw in out_keywords)
                if not is_outing:
                    continue
                
                # Check if event is upcoming (1-4 hours)
                time_until = (event_start - now).total_seconds() / 3600  # hours
                if not (1 <= time_until <= 4):
                    continue
                
                # Get pending tasks that could be errands
                from app.services.task_manager import TaskStatus
                pending_tasks = self.task_manager.list_tasks(status=TaskStatus.TODO)
                
                # Filter for errand-like tasks
                errand_tasks = []
                for task in pending_tasks:
                    task_text = f"{task.title} {task.description or ''}".lower()
                    # Check if task mentions shopping, buying, picking up, etc.
                    errand_words = ['buy', 'pick up', 'get', 'shop', 'return', 'drop off']
                    if any(word in task_text for word in errand_words):
                        errand_tasks.append(task)
                    elif task.context and task.context.value in errand_contexts:
                        errand_tasks.append(task)
                
                if errand_tasks:
                    alert_key = f"fusion_errands_{event.summary}_{event_start.date()}"
                    if self._should_send_alert(alert_key):
                        task_list = "\n".join([f"• {t.title}" for t in errand_tasks[:5]])
                        more_text = f"\n... and {len(errand_tasks) - 5} more" if len(errand_tasks) > 5 else ""
                        
                        alerts.append(ProactiveAlert(
                            category="task",
                            title=f"Errands: You're going out!",
                            message=f"Since you have **{event.summary}** in ~{time_until:.1f} hours, "
                                   f"consider knocking out these errands:\n\n"
                                   f"{task_list}{more_text}",
                            priority=AlertPriority.LOW,
                            alert_key=alert_key,
                            data={
                                "event": event.summary,
                                "errands": [t.title for t in errand_tasks[:5]]
                            }
                        ))
                        self._mark_alert_sent(alert_key)
                    break  # Only one errand alert per day
        
        except Exception as e:
            logger.error(f"Error in errand opportunities check: {e}", exc_info=True)
        
        return alerts
    
    # =========================================================================
    # BEHAVIORAL PATTERN RECOGNITION
    # =========================================================================
    
    def update_patterns(self):
        """
        Update behavioral patterns based on recent data.
        
        Should be called periodically (e.g., once per day).
        """
        try:
            self._update_sleep_patterns()
            self._update_workout_patterns()
            self._patterns.last_updated = datetime.now().isoformat()
            self._save_patterns()
            logger.info("Updated behavioral patterns")
        except Exception as e:
            logger.error(f"Error updating patterns: {e}", exc_info=True)
    
    def _update_sleep_patterns(self):
        """Update sleep pattern data from recent sleep records."""
        if not self.health_coach:
            return
        
        try:
            # Get last 14 days of sleep data
            sleep_data = self.health_coach.get_sleep_data(days=14)
            
            if "sleep_records" not in sleep_data or not sleep_data["sleep_records"]:
                return
            
            records = sleep_data["sleep_records"]
            
            # For now, we don't have bedtime/wake time in the data
            # But we can track sleep consistency via sleep score variance
            sleep_scores = [r.get('sleep_score', 0) for r in records if r.get('sleep_score')]
            
            if sleep_scores:
                avg_score = sum(sleep_scores) / len(sleep_scores)
                variance = sum((s - avg_score) ** 2 for s in sleep_scores) / len(sleep_scores)
                std_dev = variance ** 0.5
                
                # Consistency score: 100 = very consistent, 0 = highly variable
                # If std_dev is 0-5, score is 80-100; if std_dev is 20+, score is ~40
                consistency = max(0, min(100, 100 - (std_dev * 3)))
                self._patterns.sleep_consistency_score = consistency
        
        except Exception as e:
            logger.error(f"Error updating sleep patterns: {e}")
    
    def _update_workout_patterns(self):
        """Update workout pattern data from recent activities."""
        if not self.health_coach:
            return
        
        try:
            # Get recent activities
            activities = self.health_coach.get_recent_activities(limit=30)
            
            if "activities" not in activities:
                return
            
            acts = activities["activities"]
            
            # Filter for workout-like activities
            workout_types = ['running', 'strength', 'cycling', 'walking', 'hiit', 'pilates', 'yoga']
            workouts = [
                a for a in acts 
                if any(wt in a.get('type', '').lower() for wt in workout_types)
            ]
            
            if workouts:
                # Days since last workout
                last_workout_date = workouts[0].get('date')
                if last_workout_date:
                    self._patterns.last_workout_date = last_workout_date
                    last_dt = datetime.strptime(last_workout_date, '%Y-%m-%d')
                    self._patterns.days_since_last_workout = (datetime.now() - last_dt).days
                
                # Average workouts per week (from last 30 activities, estimate)
                # Count workouts with dates in last 14 days
                two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
                recent_workouts = [w for w in workouts if w.get('date', '') >= two_weeks_ago]
                self._patterns.avg_workouts_per_week = len(recent_workouts) / 2
                
                # Typical workout days
                workout_days = []
                for w in workouts[:14]:  # Last 14 workouts
                    date_str = w.get('date')
                    if date_str:
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                        workout_days.append(dt.weekday())
                
                if workout_days:
                    # Find most common days
                    from collections import Counter
                    day_counts = Counter(workout_days)
                    # Days that appear at least twice
                    typical_days = [d for d, c in day_counts.items() if c >= 2]
                    self._patterns.typical_workout_days = sorted(typical_days)
        
        except Exception as e:
            logger.error(f"Error updating workout patterns: {e}")
    
    def check_sleep_consistency(self) -> List[ProactiveAlert]:
        """
        Alert on significant deviations from sleep baseline.
        """
        alerts = []
        
        if not self.health_coach:
            return alerts
        
        try:
            # Get last night's sleep
            sleep_data = self.health_coach.get_sleep_data(days=1)
            
            if "sleep_records" not in sleep_data or not sleep_data["sleep_records"]:
                return alerts
            
            last_sleep = sleep_data["sleep_records"][0]
            sleep_score = last_sleep.get('sleep_score', 0)
            
            # Compare to consistency baseline
            if self._patterns.sleep_consistency_score > 70:
                # User usually has consistent sleep
                # Alert if last night was significantly worse
                if sleep_score < 50:
                    alert_key = f"pattern_sleep_deviation_{datetime.now().strftime('%Y%m%d')}"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="health",
                            title="Sleep Pattern Break",
                            message=f"Last night's sleep score ({sleep_score}) was lower than your usual pattern.\n\n"
                                   f"Your sleep is typically consistent (score: {self._patterns.sleep_consistency_score:.0f}/100). "
                                   f"Consider what might have disrupted your sleep and try to get back on track tonight.",
                            priority=AlertPriority.MEDIUM,
                            alert_key=alert_key,
                            data={"sleep_score": sleep_score, "baseline": self._patterns.sleep_consistency_score}
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error in sleep consistency check: {e}", exc_info=True)
        
        return alerts
    
    def check_workout_frequency(self) -> List[ProactiveAlert]:
        """
        Alert if workout frequency drops below baseline.
        """
        alerts = []
        
        try:
            # Check if user typically works out
            if self._patterns.avg_workouts_per_week < 1:
                return alerts  # User doesn't have a workout pattern
            
            # Alert if days since last workout exceeds typical interval
            typical_interval = 7 / max(1, self._patterns.avg_workouts_per_week)  # days
            
            if self._patterns.days_since_last_workout > typical_interval * 1.5:
                alert_key = f"pattern_workout_gap_{datetime.now().strftime('%Y%m%d')}"
                if self._should_send_alert(alert_key):
                    days_str = f"{self._patterns.days_since_last_workout} days"
                    typical_str = f"{typical_interval:.1f} days"
                    
                    alerts.append(ProactiveAlert(
                        category="health",
                        title="Workout Pattern Break",
                        message=f"It's been {days_str} since your last workout.\n\n"
                               f"You typically work out every {typical_str}. "
                               f"Is everything okay? Even a short walk counts!",
                        priority=AlertPriority.LOW,
                        alert_key=alert_key,
                        data={
                            "days_since": self._patterns.days_since_last_workout,
                            "typical_interval": typical_interval
                        }
                    ))
                    self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error in workout frequency check: {e}", exc_info=True)
        
        return alerts
    
    # =========================================================================
    # INFRASTRUCTURE MONITORING
    # =========================================================================
    
    def check_infrastructure(self) -> List[ProactiveAlert]:
        """
        Check infrastructure health including:
        - Server metrics (CPU temp, disk space, memory)
        - Service status (Friday services, homelab services)
        """
        alerts = []
        
        # Rate limit infra checks
        now = datetime.now()
        if self._last_infra_check:
            if now - self._last_infra_check < self._infra_check_interval:
                return alerts
        self._last_infra_check = now
        
        try:
            # Check disk space
            alerts.extend(self._check_disk_space())
            
            # Check systemd services
            alerts.extend(self._check_services())
            
            # Check CPU temperature (if available)
            alerts.extend(self._check_cpu_temperature())
            
        except Exception as e:
            logger.error(f"Error in infrastructure check: {e}", exc_info=True)
        
        return alerts
    
    def _check_disk_space(self) -> List[ProactiveAlert]:
        """Check disk space usage."""
        alerts = []
        
        try:
            import shutil
            
            # Check main filesystem
            total, used, free = shutil.disk_usage("/")
            percent_used = (used / total) * 100
            free_gb = free / (1024 ** 3)
            
            if percent_used > 90:
                alert_key = "infra_disk_critical"
                if self._should_send_alert(alert_key):
                    alerts.append(ProactiveAlert(
                        category="context",
                        title="Critical: Disk Space Low",
                        message=f"Main disk is {percent_used:.1f}% full ({free_gb:.1f} GB free).\n\n"
                               f"**Immediate action needed** to prevent system issues.",
                        priority=AlertPriority.URGENT,
                        alert_key=alert_key,
                        data={"percent_used": percent_used, "free_gb": free_gb}
                    ))
                    self._mark_alert_sent(alert_key)
            
            elif percent_used > 80:
                alert_key = "infra_disk_warning"
                if self._should_send_alert(alert_key):
                    alerts.append(ProactiveAlert(
                        category="context",
                        title="Disk Space Warning",
                        message=f"Main disk is {percent_used:.1f}% full ({free_gb:.1f} GB free).\n\n"
                               f"Consider cleaning up old files or logs.",
                        priority=AlertPriority.MEDIUM,
                        alert_key=alert_key,
                        data={"percent_used": percent_used, "free_gb": free_gb}
                    ))
                    self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
        
        return alerts
    
    def _check_services(self) -> List[ProactiveAlert]:
        """Check critical systemd services."""
        alerts = []
        
        # Services to monitor
        services = [
            ('friday.service', 'Friday API'),
            ('telegram-bot.service', 'Telegram Bot'),
            ('vllm.service', 'LLM Server'),
        ]
        
        for service_name, display_name in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                status = result.stdout.strip()
                
                if status != 'active':
                    alert_key = f"infra_service_{service_name}"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="context",
                            title=f"Service Down: {display_name}",
                            message=f"The **{display_name}** service is not running (status: {status}).\n\n"
                                   f"Run `sudo systemctl restart {service_name}` to fix.",
                            priority=AlertPriority.HIGH,
                            alert_key=alert_key,
                            data={"service": service_name, "status": status}
                        ))
                        self._mark_alert_sent(alert_key)
            
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout checking service {service_name}")
            except Exception as e:
                logger.error(f"Error checking service {service_name}: {e}")
        
        return alerts
    
    def _check_cpu_temperature(self) -> List[ProactiveAlert]:
        """Check CPU temperature (Linux only)."""
        alerts = []
        
        try:
            # Try to read CPU temperature from thermal zone
            temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
            
            if temp_file.exists():
                temp_millidegrees = int(temp_file.read_text().strip())
                temp_c = temp_millidegrees / 1000
                
                if temp_c > 85:
                    alert_key = "infra_cpu_temp_critical"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="context",
                            title="Critical: CPU Overheating",
                            message=f"CPU temperature is {temp_c:.1f}°C - this is dangerously high!\n\n"
                                   f"Check cooling system immediately.",
                            priority=AlertPriority.URGENT,
                            alert_key=alert_key,
                            data={"temp_c": temp_c}
                        ))
                        self._mark_alert_sent(alert_key)
                
                elif temp_c > 75:
                    alert_key = "infra_cpu_temp_warning"
                    if self._should_send_alert(alert_key):
                        alerts.append(ProactiveAlert(
                            category="context",
                            title="CPU Temperature Warning",
                            message=f"CPU temperature is {temp_c:.1f}°C.\n\n"
                                   f"Consider improving ventilation or reducing load.",
                            priority=AlertPriority.MEDIUM,
                            alert_key=alert_key,
                            data={"temp_c": temp_c}
                        ))
                        self._mark_alert_sent(alert_key)
        
        except Exception as e:
            logger.debug(f"Could not read CPU temperature: {e}")
        
        return alerts
    
    def get_infrastructure_status(self) -> Dict[str, Any]:
        """Get current infrastructure status for CLI display."""
        status = {
            "checked_at": datetime.now().isoformat(),
            "disk": {},
            "services": {},
            "cpu_temp": None,
        }
        
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            status["disk"] = {
                "total_gb": total / (1024 ** 3),
                "used_gb": used / (1024 ** 3),
                "free_gb": free / (1024 ** 3),
                "percent_used": (used / total) * 100,
            }
        except Exception as e:
            status["disk"]["error"] = str(e)
        
        # Services
        services = ['friday.service', 'telegram-bot.service', 'vllm.service']
        for svc in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', svc],
                    capture_output=True, text=True, timeout=5
                )
                status["services"][svc] = result.stdout.strip()
            except:
                status["services"][svc] = "unknown"
        
        # CPU temp
        try:
            temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_file.exists():
                temp_millidegrees = int(temp_file.read_text().strip())
                status["cpu_temp"] = temp_millidegrees / 1000
        except:
            pass
        
        return status
    
    # =========================================================================
    # MAIN CHECK RUNNER (Override)
    # =========================================================================
    
    def run_all_checks(self) -> List[ProactiveAlert]:
        """Run all proactive checks including fusion and pattern checks."""
        all_alerts = []
        
        logger.info("Running awareness engine checks...")
        
        # Original ProactiveMonitor checks
        all_alerts.extend(self.check_health_alerts())
        all_alerts.extend(self.check_calendar_alerts())
        all_alerts.extend(self.check_task_alerts())
        all_alerts.extend(self.check_weather_alerts())
        all_alerts.extend(self.check_activity_patterns())
        all_alerts.extend(self.check_dynamic_alerts())
        all_alerts.extend(self.check_vault_health())
        all_alerts.extend(self.check_commitment_follow_ups())
        all_alerts.extend(self.check_conversation_staleness())
        
        # NEW: Fusion checks
        all_alerts.extend(self.check_workout_readiness())
        all_alerts.extend(self.check_post_workout_recovery())
        all_alerts.extend(self.check_meeting_preparedness())
        all_alerts.extend(self.check_errand_opportunities())
        
        # NEW: Pattern-based checks
        all_alerts.extend(self.check_sleep_consistency())
        all_alerts.extend(self.check_workout_frequency())
        
        # NEW: Infrastructure checks
        all_alerts.extend(self.check_infrastructure())
        
        # Sort by priority
        priority_order = {
            AlertPriority.URGENT: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }
        all_alerts.sort(key=lambda a: priority_order.get(a.priority, 99))
        
        logger.info(f"Awareness check complete: {len(all_alerts)} alert(s) generated")
        
        return all_alerts
    
    def get_patterns(self) -> Dict[str, Any]:
        """Get current pattern data for CLI display."""
        return {
            "sleep": {
                "consistency_score": self._patterns.sleep_consistency_score,
            },
            "workouts": {
                "avg_per_week": self._patterns.avg_workouts_per_week,
                "typical_days": [
                    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] 
                    for d in self._patterns.typical_workout_days
                ],
                "days_since_last": self._patterns.days_since_last_workout,
                "last_workout_date": self._patterns.last_workout_date,
            },
            "last_updated": self._patterns.last_updated,
        }
    
    # ===== Alert Feedback Tracking =====
    
    def record_alert_feedback(self, alert_key: str, feedback_type: str, title: str = None) -> None:
        """
        Record feedback on a proactive alert.
        
        This data is used to adjust:
        - Which alert types get priority
        - The daily reach-out budget
        - Which checks might need adjustment
        - Whether to suppress similar alerts
        
        Args:
            alert_key: The unique key of the alert (e.g., "health_20251205_123456")
            feedback_type: 'up' (helpful) or 'down' (not helpful)
            title: Optional alert title for suppression matching
        """
        # Update budget state with feedback
        state = self.budget._state
        
        # Initialize alert feedback tracking if not present
        if "alert_feedback" not in state:
            state["alert_feedback"] = {
                "thumbs_up": 0,
                "thumbs_down": 0,
                "by_category": {}
            }
        
        feedback_data = state["alert_feedback"]
        
        if feedback_type == "up":
            feedback_data["thumbs_up"] = feedback_data.get("thumbs_up", 0) + 1
        else:
            feedback_data["thumbs_down"] = feedback_data.get("thumbs_down", 0) + 1
            
            # If thumbs down, suppress this alert pattern for a while
            # Use title if available, otherwise use category from alert_key
            suppress_pattern = title if title else alert_key.split("_")[0]
            if suppress_pattern:
                # Suppress for 7 days on first thumbs down
                # This gives time for legitimate alerts while preventing spam
                self.budget.suppress_alert(
                    suppress_pattern, 
                    days=7, 
                    reason=f"User thumbs down on alert: {alert_key}"
                )
        
        # Track by category (extracted from alert_key)
        category = alert_key.split("_")[0] if "_" in alert_key else "unknown"
        if category not in feedback_data["by_category"]:
            feedback_data["by_category"][category] = {"up": 0, "down": 0}
        
        if feedback_type == "up":
            feedback_data["by_category"][category]["up"] += 1
        else:
            feedback_data["by_category"][category]["down"] += 1
        
        # Save updated state
        self.budget._save_state()
        
        logger.info(f"Alert feedback recorded: {feedback_type} for {alert_key}")
    
    def get_alert_quality_score(self) -> float:
        """
        Calculate overall alert quality score based on feedback.
        
        Returns a score from 0.0 to 1.0, where:
        - 1.0 = all alerts received thumbs up
        - 0.5 = neutral (equal up/down or no feedback)
        - 0.0 = all alerts received thumbs down
        """
        state = self.budget._state
        feedback_data = state.get("alert_feedback", {})
        
        thumbs_up = feedback_data.get("thumbs_up", 0)
        thumbs_down = feedback_data.get("thumbs_down", 0)
        total = thumbs_up + thumbs_down
        
        if total == 0:
            return 0.5  # Neutral if no feedback
        
        return thumbs_up / total
    
    def get_alert_feedback_stats(self) -> Dict[str, Any]:
        """Get detailed alert feedback statistics."""
        state = self.budget._state
        feedback_data = state.get("alert_feedback", {})
        
        thumbs_up = feedback_data.get("thumbs_up", 0)
        thumbs_down = feedback_data.get("thumbs_down", 0)
        total = thumbs_up + thumbs_down
        
        return {
            "total_feedback": total,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "quality_score": self.get_alert_quality_score(),
            "by_category": feedback_data.get("by_category", {}),
        }


# Singleton instance - replaces proactive_monitor
awareness_engine = AwarenessEngine()

# Backwards compatibility alias
proactive_monitor = awareness_engine
