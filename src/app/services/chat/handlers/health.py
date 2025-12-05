"""Health query intent handler."""
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.llm import llm_service


class HealthQueryHandler(IntentHandler):
    """Handle health_query intent - fetch Garmin data and analyze it."""
    
    actions = ['health_query']
    
    def __init__(self):
        self._health_coach = None
    
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
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Fetch health data and use LLM to synthesize response."""
        try:
            # Fetch health context based on the message
            health_context = self._fetch_health_context(context.message)
            
            if not health_context:
                return ChatResponse(
                    session_id=context.session_id,
                    message=context.message,
                    answer="I couldn't fetch any health data. Make sure your Garmin data is synced.",
                    used_health=True,
                    is_final=True,
                )
            
            # Generate system prompt for health analysis
            system_prompt = self._generate_system_prompt(context.message)
            
            # Build user content with health data
            user_content = f"User question:\n{context.message}\n\nHealth data:\n{health_context}"
            
            # Call LLM to synthesize
            answer = llm_service.call(
                system_prompt=system_prompt,
                user_content=user_content,
                history=context.history,
                stream=False,
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_health=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Health query error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to fetch health data: {str(e)}")
    
    def _fetch_health_context(self, message: str) -> str:
        """
        Fetch comprehensive Garmin health/activity data.
        
        Strategy: Provide ALL available data to the LLM and let it analyze/filter
        based on the user's question. Don't pre-filter or limit data.
        """
        if not self.health_coach:
            return ""
        
        try:
            message_lower = message.lower()
            context_parts = []
            
            # Determine what data categories are relevant
            wants_sleep = any(word in message_lower for word in [
                'sleep', 'slept', 'rest', 'tired', 'fatigue', 'night', 'bed', 'wake', 'woke'
            ])
            wants_recovery = any(word in message_lower for word in [
                'recovery', 'recover', 'ready', 'readiness', 'train', 'workout', 
                'battery', 'energy', 'hrv', 'stress', 'rested'
            ])
            wants_running = any(word in message_lower for word in [
                'run', 'running', 'jog', 'pace', 'distance', 'km', 'mile'
            ])
            wants_activity = any(word in message_lower for word in [
                'activity', 'activities', 'exercise', 'workout', 'pilates', 'yoga',
                'recent', 'last', 'yesterday', 'today', 'week'
            ])
            wants_daily_summary = any(phrase in message_lower for phrase in [
                'daily health', 'health data', 'health summary', 'daily summary',
                'today\'s health', 'health digest', 'full health', 'how am i doing'
            ])
            
            # For daily summary, include everything
            if wants_daily_summary:
                wants_sleep = wants_recovery = wants_running = wants_activity = True
            
            # === SLEEP DATA ===
            if wants_sleep:
                sleep_data = self.health_coach.get_sleep_data(days=1)
                if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
                    sleep = sleep_data["sleep_records"][0]
                    context_parts.append(
                        f"### Last Night's Sleep ({sleep['date']})\n"
                        f"**Duration:**\n"
                        f"- Total Sleep: {sleep['total_sleep']}\n"
                        f"- Deep Sleep: {sleep['deep_sleep']}\n"
                        f"- Light Sleep: {sleep['light_sleep']}\n"
                        f"- REM Sleep: {sleep['rem_sleep']}\n"
                        f"**Quality Metrics:**\n"
                        f"- Sleep Score: {sleep['sleep_score']}/100 ({sleep['quality']})\n"
                        f"- Times Woken Up: {sleep['awake_count']}\n"
                        f"- Total Time Awake: {sleep['awake_time_min']} minutes\n"
                        f"- Restless Moments: {sleep['restless_moments']}\n"
                        f"**Recovery Metrics:**\n"
                        f"- Resting Heart Rate: {sleep['resting_hr']} bpm\n"
                        f"- HRV (Heart Rate Variability): {sleep['hrv']} ms\n"
                        f"- Sleep Stress Level: {sleep['avg_sleep_stress']}/100\n"
                        f"- Body Battery Recharged: +{sleep['body_battery_change']} points\n"
                        f"**Breathing:**\n"
                        f"- Average SpO2: {sleep['avg_spo2']}%\n"
                        f"- Lowest SpO2: {sleep['lowest_spo2']}%\n"
                        f"- Average Respiration: {sleep['avg_respiration']} breaths/min"
                    )
            
            # === RECOVERY & READINESS DATA ===
            if wants_recovery or wants_daily_summary:
                recovery = self.health_coach.get_recovery_status()
                if recovery:
                    recovery_lines = ["### Current Recovery Status"]
                    
                    if 'training_readiness' in recovery:
                        recovery_lines.append(f"- Training Readiness: {recovery['training_readiness']}/100")
                    if 'readiness_level' in recovery:
                        recovery_lines.append(f"- Readiness Level: {recovery['readiness_level']}")
                    if 'recovery_time' in recovery and recovery['recovery_time'] > 0:
                        recovery_lines.append(f"- Recovery Time Needed: {recovery['recovery_time']} hours")
                    if 'body_battery' in recovery:
                        recovery_lines.append(f"- Current Body Battery: {recovery['body_battery']}/100")
                    if 'body_battery_wake' in recovery:
                        recovery_lines.append(f"- Body Battery at Wake: {recovery['body_battery_wake']}/100")
                    if 'hrv_7day_avg' in recovery:
                        recovery_lines.append(f"- HRV 7-Day Average: {recovery['hrv_7day_avg']} ms")
                    if 'hrv_latest' in recovery:
                        recovery_lines.append(f"- Latest HRV: {recovery['hrv_latest']} ms")
                    if 'last_sleep' in recovery:
                        recovery_lines.append(f"- Last Sleep Duration: {recovery['last_sleep']}")
                    
                    if len(recovery_lines) > 1:
                        context_parts.append("\n".join(recovery_lines))
            
            # === RUNNING STATS ===
            if wants_running:
                summary = self.health_coach.get_running_summary(days=30)
                if "run_count" in summary:
                    context_parts.append(
                        f"### Running Stats (Last 30 Days)\n"
                        f"- Total Runs: {summary['run_count']}\n"
                        f"- Total Distance: {summary['total_distance_km']} km\n"
                        f"- Total Time: {summary.get('total_time', 'N/A')}\n"
                        f"- Average Pace: {summary['avg_pace_min_km']} min/km\n"
                        f"- Average Heart Rate: {summary['avg_heart_rate']} bpm\n"
                        f"- Total Calories: {summary['total_calories']}"
                    )
            
            # === RECENT ACTIVITIES ===
            if wants_activity or wants_running:
                activities = self.health_coach.get_recent_activities(limit=10)
                if "activities" in activities and activities["activities"]:
                    acts = activities["activities"]
                    
                    # Filter by specific activity type if mentioned
                    if 'pilates' in message_lower:
                        acts = [a for a in acts if 'pilates' in a['type'].lower() or 'pilates' in a['name'].lower()]
                    elif any(word in message_lower for word in ['yoga', 'stretch']):
                        acts = [a for a in acts if any(w in a['type'].lower() or w in a['name'].lower() for w in ['yoga', 'stretch'])]
                    elif wants_running and not wants_activity:
                        acts = [a for a in acts if 'running' in a['type'].lower() or 'run' in a['name'].lower()]
                    
                    if acts:
                        act_lines = ["### Recent Activities"]
                        for act in acts[:10]:  # Show up to 10
                            duration_str = act.get('duration') or f"{act['duration_min']}min"
                            if act['distance_km'] > 0:
                                act_lines.append(
                                    f"- {act['date']}: {act['name']} ({act['type']}) - "
                                    f"{act['distance_km']}km, {duration_str}, "
                                    f"Pace: {act['pace_min_km']} min/km, HR: {act['avg_hr']} bpm"
                                )
                            else:
                                act_lines.append(
                                    f"- {act['date']}: {act['name']} ({act['type']}) - "
                                    f"{duration_str}, Calories: {act['calories']}"
                                )
                        context_parts.append("\n".join(act_lines))
            
            return "\n\n".join(context_parts) if context_parts else ""
        
        except Exception as e:
            logger.error(f"Error getting health context: {e}")
            return ""
    
    def _generate_system_prompt(self, message: str) -> str:
        """Generate system prompt for health analysis."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        
        base = f"Today is {today}, {current_time}.\n\n"
        base += f"You are Friday, a personal AI assistant and health coach for Artur Gomes ({settings.authorized_user}).\n\n"
        
        # Calibration guidelines for health metrics interpretation
        calibration = """
## Metric Interpretation Guide:

**Sleep Score:** 80+ excellent | 70-79 good | 60-69 fair | <60 poor
**Sleep Duration:** 7-9h optimal | 6-7h adequate | <6h sleep deprived
**Awakenings:** 0-2 good | 3-4 moderate | 5+ fragmented sleep
**Time Awake:** <20min good | 20-40min moderate | >40min significant
**Restless Moments:** <30 calm | 30-60 moderate | >60 very restless (red flag)
**HRV:** >60ms high | 40-59ms normal | <40ms low (user baseline: ~50ms)
**Resting HR:** <50 excellent | 50-60 good | 61-70 average | >70 elevated (user baseline: ~49bpm)
**Body Battery Wake:** 80+ excellent | 60-79 good | 40-59 fair | <40 poor recovery
**Training Readiness:** 80+ prime | 60-79 ready | 40-59 fair | <40 rest day
**Sleep Stress:** <15 restful | 15-25 calm | 26-40 moderate | >40 high stress
**SpO2:** 95-100% normal | 90-94% low | <90% concerning
**Lowest SpO2:** >90% normal | 85-89% may indicate sleep apnea | <85% consult doctor
"""
        
        # Check if this is a daily summary request
        message_lower = message.lower()
        if any(phrase in message_lower for phrase in ['daily health', 'health data', 'health summary', 'daily summary']):
            return (
                f"{base}"
                "You are a health coach analyzing Garmin data. Create a comprehensive daily summary.\n"
                f"{calibration}\n"
                "**Response Guidelines:**\n"
                "- Start directly with insights (never 'Based on the data...')\n"
                "- Lead with the most important finding (good or bad)\n"
                "- Flag any concerning metrics with specific numbers\n"
                "- Provide 1-2 actionable suggestions if issues found\n"
                "- Be honest about poor metrics, don't sugar-coat"
            )
        else:
            return (
                f"{base}"
                "Answer the user's health question using the Garmin data provided.\n"
                f"{calibration}\n"
                "**Response Guidelines:**\n"
                "- Start directly with the answer (never 'Based on...', 'According to...', 'I can see...')\n"
                "- State the metric value AND its interpretation (e.g., 'Sleep score: 68/100 (fair)')\n"
                "- Highlight concerning metrics with specific numbers\n"
                "- Consider ALL data when assessing (not just the main metric)\n"
                "- Give actionable suggestions if quality is fair/poor\n"
                "- Be honest - don't say 'good' when data shows 'fair' or 'poor'"
            )
