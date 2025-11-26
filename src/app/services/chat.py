"""Chat orchestration service with health coach integration."""
import uuid
from datetime import datetime
from typing import Dict, List, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import RetrievedChunk, MemoryItem
from app.services.vector_store import vector_store
from app.services.web_search import web_search_service
from app.services.llm import llm_service
from app.services.date_tools import date_tools
from app.services.reminders import reminder_service
from app.services.calendar_service import calendar_service

# Health keywords that trigger health data lookup
HEALTH_KEYWORDS = [
    'run', 'running', 'race', 'marathon', 'jog', 'jogging',
    'workout', 'exercise', 'training', 'fitness',
    'pace', 'distance', 'kilometer', 'km', 'mile',
    'heart rate', 'hr', 'bpm', 'cardio',
    'calories', 'calorie', 'burn',
    'sleep', 'slept', 'rest', 'recovery', 'recovered', 'tired', 'fatigue',
    'vo2', 'endurance', 'stamina',
    'health', 'wellness', 'body',
    'activity', 'activities', 'garmin',
    'coach', 'coaching', 'advice', 'improve',
    'progress', 'performance', 'personal record', 'pr',
    'pilates', 'yoga', 'stretch', 'stretching', 'flexibility'
]


class ChatService:
    """Service for chat orchestration."""
    
    def __init__(self):
        """Initialize chat service."""
        self.conversation_history: Dict[str, List[dict]] = {}
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
    
    def should_use_health_data(self, message: str) -> bool:
        """Determine if message should include health data."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in HEALTH_KEYWORDS)
    
    def get_health_context(self, message: str) -> str:
        """Get relevant health data based on the message."""
        if not self.health_coach:
            return ""
        
        try:
            message_lower = message.lower()
            context_parts = []
            
            # Check for sleep queries first (most specific)
            if any(word in message_lower for word in ['sleep', 'slept', 'rest']):
                sleep_data = self.health_coach.get_sleep_data(days=1)
                if "sleep_records" in sleep_data and sleep_data["sleep_records"]:
                    sleep = sleep_data["sleep_records"][0]
                    context_parts.append(
                        f"### Last Night's Sleep ({sleep['date']})\n"
                        f"- Total Sleep: {sleep['total_sleep_hours']} hours\n"
                        f"- Deep Sleep: {sleep['deep_sleep_hours']} hours\n"
                        f"- Light Sleep: {sleep['light_sleep_hours']} hours\n"
                        f"- REM Sleep: {sleep['rem_sleep_hours']} hours\n"
                        f"- Sleep Score: {sleep['sleep_score']}/100\n"
                        f"- Resting HR: {sleep['resting_hr']} bpm\n"
                        f"- HRV: {sleep['hrv']}\n"
                        f"- Times Awake: {sleep['awake_count']}"
                    )
            
            # Include running summary if asking about running/exercise
            if any(word in message_lower for word in ['run', 'running', 'exercise', 'workout', 'training']):
                summary = self.health_coach.get_running_summary(days=30)
                if "run_count" in summary:
                    context_parts.append(
                        f"### Your Running Stats (Last 30 Days)\n"
                        f"- Runs: {summary['run_count']}\n"
                        f"- Total Distance: {summary['total_distance_km']} km\n"
                        f"- Total Time: {summary['total_time_hours']} hours\n"
                        f"- Average Pace: {summary['avg_pace_min_km']} min/km\n"
                        f"- Average Heart Rate: {summary['avg_heart_rate']} bpm\n"
                        f"- Calories Burned: {summary['total_calories']}"
                    )
            
            # Include recent activities if asking about recent workouts
            if any(word in message_lower for word in ['recent', 'last', 'latest', 'yesterday', 'today']):
                activities = self.health_coach.get_recent_activities(limit=10)
                if "activities" in activities and activities["activities"]:
                    acts = activities["activities"]
                    
                    # Filter by activity type if specific activity mentioned
                    if 'pilates' in message_lower:
                        acts = [a for a in acts if 'pilates' in a['type'].lower() or 'pilates' in a['name'].lower()]
                    elif any(word in message_lower for word in ['yoga', 'stretch']):
                        acts = [a for a in acts if any(w in a['type'].lower() or w in a['name'].lower() for w in ['yoga', 'stretch'])]
                    elif any(word in message_lower for word in ['run', 'running', 'jog']):
                        acts = [a for a in acts if 'running' in a['type'].lower() or 'run' in a['name'].lower()]
                    
                    acts = acts[:3]  # Limit to 3 most recent
                    act_list = []
                    for act in acts:
                        if act['distance_km'] > 0:
                            act_list.append(
                                f"- {act['date']}: {act['name']} - {act['distance_km']}km, "
                                f"{act['duration_min']}min, {act['pace_min_km']} min/km, HR: {act['avg_hr']}"
                            )
                        else:
                            act_list.append(f"- {act['date']}: {act['name']} ({act['type']}) - {act['duration_min']}min, HR: {act['avg_hr']}")
                    
                    if act_list:
                        context_parts.append(
                            f"### Recent Activities\n" + "\n".join(act_list)
                        )
            
            # Include recovery/readiness if asking about being ready or recovered
            if any(word in message_lower for word in ['recovery', 'recovered', 'ready', 'tired', 'fatigue']):
                recovery = self.health_coach.get_recovery_status()
                if recovery:
                    rec_items = []
                    for key, value in recovery.items():
                        rec_items.append(f"- {key.replace('_', ' ').title()}: {value}")
                    context_parts.append(
                        f"### Recovery Metrics\n" + "\n".join(rec_items)
                    )
            
            return "\n\n".join(context_parts) if context_parts else ""
        
        except Exception as e:
            logger.error(f"Error getting health context: {e}")
            return ""
    
    def build_context(
        self,
        message: str,
        use_rag: bool,
        use_web: bool,
        use_memory: bool,
    ) -> Tuple[str, bool, bool, bool, bool, List[RetrievedChunk], List[MemoryItem]]:
        """Build context from various sources."""
        obsidian_ctx = ""
        obsidian_chunks: List[RetrievedChunk] = []
        
        if use_rag:
            obsidian_ctx, obsidian_chunks = vector_store.query_obsidian(message)
        
        memory_ctx = ""
        memory_items: List[MemoryItem] = []
        if use_memory:
            memory_ctx, memory_items = vector_store.query_memory(message)
        
        web_ctx = ""
        if use_web:
            web_ctx = web_search_service.search(message)
        
        # Check for health data
        health_ctx = ""
        used_health = False
        if self.should_use_health_data(message):
            health_ctx = self.get_health_context(message)
            used_health = bool(health_ctx)
        
        parts = []
        used_rag = False
        used_web = False
        used_memory = False
        
        # Order matters: Memory first (most important for personal facts)
        if memory_ctx:
            parts.append("### From your personal memory\n" + memory_ctx)
            used_memory = True
        
        if health_ctx:
            parts.append("### From your health data (Garmin)\n" + health_ctx)
        
        if obsidian_ctx:
            parts.append("### From my notes\n" + obsidian_ctx)
            used_rag = True
        
        if web_ctx:
            parts.append("### From the web\n" + web_ctx)
            used_web = True
        
        combined = "\n\n====================\n\n".join(parts) if parts else ""
        
        return combined, used_rag, used_web, used_memory, used_health, obsidian_chunks, memory_items
    
    def get_system_prompt(self, has_web: bool = False, has_health: bool = False, message: str = "") -> str:
        """Generate system prompt based on context."""
        from datetime import timezone, timedelta
        user_tz = timezone(timedelta(hours=-3))
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        
        base = f"You are Friday, {settings.authorized_user}'s assistant. Today is {today}."
        formatting = "Use Markdown: *bold*, `code`, bullets."
        
        # Only include tool instructions if query is about tools (time/calendar/reminders)
        message_lower = message.lower()
        is_tool_related = any(kw in message_lower for kw in [
            'time', 'calendar', 'remind', 'schedule', 'event', 'appointment',
            'what time', 'when is my', 'do i have'
        ])
        
        tool_instructions = ""
        if is_tool_related:
            # Date/time calculation and reminder instructions
            tool_instructions = (
                "\n\nCRITICAL - Time/Date Queries:\n"
                "• You do NOT know the current time - you will be wrong!\n"
                "• When asked 'what time', MUST respond: 'The current time is <CALCULATE>current_time()</CALCULATE>'\n"
                "• For date calculations: <CALCULATE>days_until_birthday(month, day)</CALCULATE>\n"
                "• NEVER say times like '10:30 AM' without using <CALCULATE> tags\n"
                "\n\nCRITICAL - Calendar Queries:\n"
                "• You do NOT know calendar events - you will be wrong!\n"
                "• When asked 'calendar today': respond ONLY: <CALENDAR_TODAY/> and STOP\n"
                "• When asked 'calendar tomorrow': respond ONLY: <CALENDAR_TOMORROW/> and STOP\n"
                "• When asked 'next calendar event' or 'next event': respond ONLY: <CALENDAR_NEXT/> and STOP\n"
                "• When asked 'calendar this week': respond ONLY: <CALENDAR_WEEK/> and STOP\n"
                "• Do NOT make up events - always use tags\n"
                "\n\nCRITICAL - Reminder Queries:\n"
                "• You do NOT know what reminders exist - you will be wrong!\n"
                "• When asked 'do I have reminders', respond ONLY: <REMINDER_LIST/> and STOP\n"
                "• When asked 'time until reminder', respond ONLY: <REMINDER_NEXT/> and STOP\n"
                "• Do NOT add any text after these tags - the system will fill in the details\n"
                "\n\nCreate Reminders:\n"
                "• For reminder requests, use: <REMINDER>message|minutes</REMINDER>\n"
                "• Example: 'remind me to take trash out in 40 min' -> <REMINDER>take trash out|40</REMINDER>\n"
                "• For hours: <REMINDER>message|hours=2</REMINDER>\n"
                "• For specific time: <REMINDER>message|at=14:30</REMINDER>"
            )
        
        if has_health:
            return (
                f"{base} Answer using ONLY their Garmin health/activity data provided below. "
                f"IGNORE reminders, calendar events, and conversation history when answering health/activity questions. "
                f"Use the 'Recent Activities' section to find specific workouts (pilates, running, yoga, etc.). "
                f"Be direct and brief. {formatting}{tool_instructions}"
            )
        elif has_web:
            return (
                f"{base} Use web search results to answer the user's question. "
                f"Answer directly based on what you find. "
                f"Be direct and brief. {formatting}"
            )
        else:
            return (
                f"{base}\n\n"
                "Rules:\n"
                "• Use provided context (notes/memory) ONLY if it helps answer the question\n"
                "• For greetings/small talk: be warm and brief, don't dump facts\n"
                "• For questions: answer directly using relevant context\n"
                "• Never volunteer unrequested information\n"
                f"• {formatting}{tool_instructions}"
            )
        
        if has_health:
            return (
                f"{base} Answer using ONLY their Garmin health/activity data provided below. "
                f"IGNORE reminders, calendar events, and conversation history when answering health/activity questions. "
                f"Use the 'Recent Activities' section to find specific workouts (pilates, running, yoga, etc.). "
                f"Be direct and brief. {formatting}{tool_instructions}"
            )
        elif has_web:
            return (
                f"{base} Use web results to answer. "
                f"Be direct and brief. {formatting}{tool_instructions}"
            )
        else:
            return (
                f"{base}\n\n"
                "Rules:\n"
                "• Use provided context (notes/memory) ONLY if it helps answer the question\n"
                "• For greetings/small talk: be warm and brief, don't dump facts\n"
                "• For questions: answer directly using relevant context\n"
                "• Never volunteer unrequested information\n"
                f"• {formatting}{tool_instructions}"
            )
    
    def get_or_create_session(self, session_id: str = None) -> str:
        """Get or create conversation session."""
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        return session_id
    
    def get_history(self, session_id: str) -> List[dict]:
        """Get conversation history for session."""
        return self.conversation_history.get(session_id, [])
    
    def update_history(self, session_id: str, user_msg: str, assistant_msg: str):
        """Update conversation history."""
        history = self.conversation_history.get(session_id, [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        
        if len(history) > settings.max_conversation_history * 2:
            history[:] = history[-(settings.max_conversation_history * 2):]
        
        self.conversation_history[session_id] = history
    
    def process_date_calculations(self, answer: str) -> str:
        """Process <CALCULATE>, <REMINDER>, and reminder query tags in the answer."""
        import re
        from datetime import timezone, timedelta
        
        # Process CALENDAR tags
        if '<CALENDAR_TODAY/>' in answer:
            events = calendar_service.get_today_events()
            if events:
                calendar_text = "📅 Today's calendar:\n"
                for e in events:
                    time_str = e.start.strftime("%I:%M %p")
                    calendar_text += f"• {time_str} - {e.summary}\n"
                    if e.location:
                        calendar_text += f"  📍 {e.location}\n"
            else:
                calendar_text = "You have no events today."
            answer = calendar_text
        
        if '<CALENDAR_TOMORROW/>' in answer:
            events = calendar_service.get_tomorrow_events()
            if events:
                calendar_text = "📅 Tomorrow's calendar:\n"
                for e in events:
                    time_str = e.start.strftime("%I:%M %p")
                    calendar_text += f"• {time_str} - {e.summary}\n"
                    if e.location:
                        calendar_text += f"  📍 {e.location}\n"
            else:
                calendar_text = "You have no events tomorrow."
            answer = calendar_text
        
        if '<CALENDAR_NEXT/>' in answer:
            events = calendar_service.get_upcoming_events(days=30)
            if events:
                # Get next event (first in the sorted list)
                next_event = events[0]
                user_tz = timezone(timedelta(hours=-3))
                now = datetime.now(user_tz)
                
                # Calculate time until
                time_diff = next_event.start.replace(tzinfo=user_tz) - now
                days = time_diff.days
                hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                hours = hours % 24
                minutes = (remainder // 60)
                
                if days > 0:
                    time_text = f"in {days} day(s) and {hours} hour(s)"
                elif hours > 0:
                    time_text = f"in {hours} hour(s) and {minutes} minute(s)"
                else:
                    time_text = f"in {minutes} minute(s)"
                
                date_str = next_event.start.strftime("%a, %b %d at %I:%M %p")
                calendar_text = f"📅 Your next event is '{next_event.summary}' on {date_str} ({time_text})"
                if next_event.location:
                    calendar_text += f"\n📍 {next_event.location}"
            else:
                calendar_text = "You have no upcoming events in the next 30 days."
            answer = calendar_text
        
        if '<CALENDAR_WEEK/>' in answer:
            events = calendar_service.get_upcoming_events(days=7)
            if events:
                calendar_text = "📅 This week's calendar:\n"
                for e in events:
                    date_str = e.start.strftime("%a, %b %d at %I:%M %p")
                    calendar_text += f"• {date_str} - {e.summary}\n"
                    if e.location:
                        calendar_text += f"  📍 {e.location}\n"
            else:
                calendar_text = "You have no events this week."
            answer = calendar_text
        
        # Process REMINDER_LIST tags
        if '<REMINDER_LIST/>' in answer:
            pending = reminder_service.list_pending_reminders()
            if pending:
                reminder_text = "Your pending reminders:\n"
                for r in pending:
                    time_str = r.remind_at.strftime("%I:%M %p on %B %d")
                    reminder_text += f"• {r.message} - at {time_str}\n"
            else:
                reminder_text = "You have no pending reminders."
            # Replace entire answer with just the reminder list
            answer = reminder_text
        
        # Process REMINDER_NEXT tags
        if '<REMINDER_NEXT/>' in answer:
            pending = reminder_service.list_pending_reminders()
            if pending:
                # Sort by time
                pending.sort(key=lambda r: r.remind_at)
                next_reminder = pending[0]
                
                user_tz = timezone(timedelta(hours=-3))
                now = datetime.now(user_tz)
                time_diff = next_reminder.remind_at.replace(tzinfo=user_tz) - now
                
                hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                minutes = remainder // 60
                
                if hours > 0:
                    time_text = f"{hours} hour(s) and {minutes} minute(s)"
                else:
                    time_text = f"{minutes} minute(s)"
                
                result_text = f"Your next reminder is '{next_reminder.message}' in {time_text}."
            else:
                result_text = "You have no pending reminders."
            # Replace entire answer with just the next reminder info
            answer = result_text
        
        # Process CALCULATE tags
        calc_pattern = r'<CALCULATE>(.*?)</CALCULATE>'
        calc_matches = re.findall(calc_pattern, answer)
        
        for calc_expr in calc_matches:
            try:
                if 'current_time()' in calc_expr:
                    from datetime import timezone, timedelta
                    user_tz = timezone(timedelta(hours=-3))
                    now = datetime.now(user_tz)
                    time_str = now.strftime("%I:%M %p")  # 03:55 PM format
                    answer = answer.replace(
                        f'<CALCULATE>{calc_expr}</CALCULATE>',
                        time_str
                    )
                
                elif 'days_until_birthday' in calc_expr:
                    match = re.search(r'days_until_birthday\((\d+),\s*(\d+)\)', calc_expr)
                    if match:
                        month, day = int(match.group(1)), int(match.group(2))
                        result = date_tools.days_until_birthday(month, day)
                        answer = answer.replace(
                            f'<CALCULATE>{calc_expr}</CALCULATE>',
                            str(result)
                        )
                
                elif 'days_until' in calc_expr:
                    match = re.search(r'days_until\(["\'](.+?)["\']\)', calc_expr)
                    if match:
                        date_str = match.group(1)
                        result = date_tools.days_until(date_str)
                        answer = answer.replace(
                            f'<CALCULATE>{calc_expr}</CALCULATE>',
                            str(result)
                        )
                
            except Exception as e:
                logger.error(f"Date calculation failed: {e}")
        
        # Process REMINDER tags
        reminder_pattern = r'<REMINDER>(.*?)\|(.*?)</REMINDER>'
        reminder_matches = re.findall(reminder_pattern, answer)
        
        for message, time_spec in reminder_matches:
            try:
                # Parse time specification
                if time_spec.startswith('hours='):
                    hours = int(time_spec.split('=')[1])
                    reminder = reminder_service.create_reminder(message, hours=hours)
                    answer = answer.replace(
                        f'<REMINDER>{message}|{time_spec}</REMINDER>',
                        f'✅ Reminder set for {hours} hour(s) from now'
                    )
                elif time_spec.startswith('at='):
                    at_time = time_spec.split('=')[1]
                    reminder = reminder_service.create_reminder(message, at_time=at_time)
                    answer = answer.replace(
                        f'<REMINDER>{message}|{time_spec}</REMINDER>',
                        f'✅ Reminder set for {at_time}'
                    )
                else:
                    # Assume minutes
                    minutes = int(time_spec)
                    reminder = reminder_service.create_reminder(message, minutes=minutes)
                    answer = answer.replace(
                        f'<REMINDER>{message}|{time_spec}</REMINDER>',
                        f'✅ Reminder set for {minutes} minute(s) from now'
                    )
                
            except Exception as e:
                logger.error(f"Reminder creation failed: {e}")
        
        return answer
    
    def extract_memory(self, user_msg: str, assistant_msg: str) -> str | None:
        """Extract important facts from conversation for explicit memory."""
        # Skip extraction for reminder/time/health queries (ephemeral information)
        skip_keywords = [
            'remind', 'reminder', 'what time', 'current time', 'how much time',
            'latest', 'last', 'recent', 'when was', 'how many', 'how much',
            'pilates', 'run', 'workout', 'sleep', 'activity', 'session',
            'calendar', 'event', 'meeting', 'appointment', 'schedule'
        ]
        user_lower = user_msg.lower()
        matched_keywords = [kw for kw in skip_keywords if kw in user_lower]
        if matched_keywords:
            logger.debug(f"Skipped memory extraction (matched keywords: {matched_keywords})")
            return None
        
        # Use LLM to determine if there's something worth remembering
        extraction_prompt = (
            "Review this conversation and extract ONLY new factual information about the user "
            "that should be permanently remembered (preferences, facts, relationships, etc.).\n\n"
            "DO NOT extract:\n"
            "- Ephemeral information (reminders, current time, dates, temporary states)\n"
            "- Time-based queries (when was, latest, last, recent, how long ago)\n"
            "- Health/activity data (workouts, sessions, runs, sleep - these change daily)\n"
            "- Questions being asked (only extract statements of fact)\n"
            "- Answers to queries about current state\n\n"
            "ONLY extract permanent facts the user explicitly states about themselves.\n\n"
            "If there's nothing new to remember, respond with 'NONE'.\n"
            "If there is something to remember, respond with ONLY the core fact, no explanation.\n\n"
            "Examples:\n"
            "- USER: 'My favorite color is blue' -> 'Favorite color is blue'\n"
            "- USER: 'I work at Google' -> 'Works at Google'\n"
            "- USER: 'Remind me to call mom' -> 'NONE'\n"
            "- USER: 'When was my latest pilates session?' ASSISTANT: 'It was today' -> 'NONE'\n"
            "- USER: 'What time is it?' -> 'NONE'\n"
            "- USER: 'I have a meeting at 3pm' -> 'NONE'\n\n"
            f"Conversation:\nUSER: {user_msg}\nASSISTANT: {assistant_msg}\n\n"
            "Extract memorable fact:"
        )
        
        try:
            result = llm_service.call(
                system_prompt="You are a fact extraction assistant. Extract only permanent facts about the user.",
                user_content=extraction_prompt,
                history=[],
                stream=False
            )
            
            result = result.strip()
            
            # Don't save if no useful info
            if result == "NONE" or len(result) < 5 or "nothing" in result.lower():
                return None
            
            # Post-extraction validation: reject if contains ephemeral indicators
            reject_patterns = [
                'latest', 'last', 'recent', 'today', 'yesterday', 'tomorrow',
                'was at', 'was on', 'session', 'time is', 'remind',
                'pm', 'am', ':', 'o\'clock', 'minutes', 'hours',
                'calendar', 'event', 'meeting', 'appointment'
            ]
            
            result_lower = result.lower()
            if any(pattern in result_lower for pattern in reject_patterns):
                logger.info(f"Rejected memory extraction (ephemeral): {result[:100]}")
                return None
            
            return result
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return None
    
    def is_tool_query(self, message: str) -> bool:
        """Check if message is a tool query that should ignore history."""
        tool_keywords = [
            'what time', 'current time', 'time is it',
            'how many minutes', 'how much time', 'time until', 'time remaining',
            'do i have remind', 'pending remind', 'show remind', 'list remind',
            'next remind', 'countdown',
            'calendar', 'what\'s on my calendar', 'events today', 'events tomorrow', 'events this week',
            'appointments', 'schedule', 'tomorrow', 'next event', 'next appointment'
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in tool_keywords)
    
    def chat(
        self,
        message: str,
        session_id: str = None,
        use_rag: bool = True,
        use_web: bool = False,
        use_memory: bool = True,
        save_memory: bool = True,
        stream: bool = False,
    ):
        """Handle chat request."""
        session_id = self.get_or_create_session(session_id)
        
        # For tool queries, use empty history to avoid interference
        if self.is_tool_query(message):
            history = []
        else:
            history = self.get_history(session_id)
        
        ctx, used_rag, used_web, used_memory, used_health, obsidian_chunks, memory_items = self.build_context(
            message, use_rag, use_web, use_memory
        )
        
        system_prompt = self.get_system_prompt(has_web=used_web, has_health=used_health)
        
        if ctx:
            user_content = (
                f"User question:\n{message}\n\n"
                f"Context (from notes, memory, health data, and/or web):\n\n{ctx}"
            )
        else:
            user_content = message
        
        if stream:
            return {
                "stream": llm_service.call(
                    system_prompt, user_content, history=history, stream=True
                ),
                "session_id": session_id,
                "message": message,
                "save_memory": save_memory,
                "used_rag": used_rag,
                "used_web": used_web,
                "used_memory": used_memory,
                "used_health": used_health,
                "obsidian_chunks": obsidian_chunks,
                "memory_items": memory_items,
            }
        else:
            answer = llm_service.call(
                system_prompt, user_content, history=history, stream=False
            )
            
            # Process date calculations if present
            answer = self.process_date_calculations(answer)
            
            self.update_history(session_id, message, answer)
            
            # Automatic memory extraction
            extracted_memory = None
            if save_memory:
                # Save chat history
                mem_text = f"USER: {message}\nASSISTANT: {answer}"
                vector_store.add_memory(mem_text, label="chat")
                
                # Try to extract important facts for explicit memory
                logger.debug(f"Attempting memory extraction for: USER: {message[:50]}...")
                extracted_memory = self.extract_memory(message, answer)
                if extracted_memory:
                    vector_store.add_memory(extracted_memory, label="explicit_memory")
                    logger.info(f"✅ Auto-extracted memory: {extracted_memory[:100]}")
                else:
                    logger.debug(f"❌ No memory extracted (skipped or rejected)")
            
            return {
                "session_id": session_id,
                "message": message,
                "answer": answer,
                "used_rag": used_rag,
                "used_web": used_web,
                "used_memory": used_memory,
                "used_health": used_health,
                "obsidian_chunks": obsidian_chunks,
                "memory_items": memory_items,
                "extracted_memory": extracted_memory,
            }


# Singleton instance
chat_service = ChatService()
