"""Chat service with two-stage LLM architecture (Intent Router + Response Generator)."""
import uuid
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import RetrievedChunk, MemoryItem
from app.services.vector_store import vector_store
from app.services.web_search import web_search_service
from app.services.llm import llm_service
from app.services.intent.router import intent_router
from app.services.date_tools import date_tools
from app.services.reminders import reminder_service
from app.services.calendar_service import calendar_service
from app.services.post_chat_processor import post_chat_processor
from app.services.obsidian import obsidian_service


class ChatService:
    """Two-stage chat service: Intent routing -> Response generation."""
    
    def __init__(self):
        """Initialize chat service."""
        self.conversation_history: Dict[str, List[dict]] = {}
        self._health_coach = None
        self._personality = None
    
    @property
    def personality(self) -> str:
        """Lazy load Friday's personality from the About file."""
        if self._personality is None:
            self._personality = self._load_personality()
        return self._personality
    
    def _load_personality(self) -> str:
        """Load Friday's personality from 5.0 About/Who is Friday.md"""
        try:
            personality_path = settings.about_path / "Who is Friday.md"
            if personality_path.exists():
                content = personality_path.read_text(encoding="utf-8")
                # Remove frontmatter (between --- markers)
                if content.startswith("---"):
                    end_frontmatter = content.find("---", 3)
                    if end_frontmatter != -1:
                        content = content[end_frontmatter + 3:].strip()
                logger.info(f"Loaded Friday personality from {personality_path}")
                return content
            else:
                logger.warning(f"Personality file not found: {personality_path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load personality: {e}")
            return ""
    
    def reload_personality(self):
        """Force reload personality from file (useful after edits)."""
        self._personality = None
        return self.personality
    
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
    
    def _load_user_profile(self) -> str:
        """Load the user's profile file (Artur Gomes.md) for identity queries."""
        try:
            profile_path = settings.vault_path / settings.user_profile_file
            if profile_path.exists():
                content = profile_path.read_text(encoding="utf-8")
                logger.info(f"Loaded user profile from {profile_path}")
                return content
            else:
                logger.warning(f"User profile not found: {profile_path}")
                return ""
        except Exception as e:
            logger.error(f"Failed to load user profile: {e}")
            return ""
    
    def _personalize_memory(self, content: str) -> str:
        """
        Replace first-person pronouns with the user's name for better searchability.
        
        "my birthday is march 30" -> "Artur's birthday is March 30"
        "I like pizza" -> "Artur likes pizza"
        """
        import re
        
        # Get user's first name from settings
        user_name = "Artur"  # Could be made configurable
        
        # Replace patterns (case-insensitive)
        # "my X" -> "Artur's X"
        content = re.sub(r'\bmy\b', f"{user_name}'s", content, flags=re.IGNORECASE)
        
        # "I am X" -> "Artur is X"
        content = re.sub(r'\bI am\b', f"{user_name} is", content, flags=re.IGNORECASE)
        content = re.sub(r"\bI'm\b", f"{user_name} is", content, flags=re.IGNORECASE)
        
        # "I like X" -> "Artur likes X"
        content = re.sub(r'\bI like\b', f"{user_name} likes", content, flags=re.IGNORECASE)
        
        # "I have X" -> "Artur has X"
        content = re.sub(r'\bI have\b', f"{user_name} has", content, flags=re.IGNORECASE)
        
        # "I use X" -> "Artur uses X"
        content = re.sub(r'\bI use\b', f"{user_name} uses", content, flags=re.IGNORECASE)
        
        # "I work X" -> "Artur works X"
        content = re.sub(r'\bI work\b', f"{user_name} works", content, flags=re.IGNORECASE)
        
        # "I live X" -> "Artur lives X"
        content = re.sub(r'\bI live\b', f"{user_name} lives", content, flags=re.IGNORECASE)
        
        # Generic "I [verb]" -> "Artur [verb]s" (simple verbs)
        # This is a fallback - won't be grammatically perfect but better than "I"
        content = re.sub(r'\bI\b', user_name, content)
        
        # Capitalize first letter
        if content:
            content = content[0].upper() + content[1:]
        
        return content
    
    def fetch_health_context(self, message: str) -> str:
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
    
    def fetch_context_by_intent(self, intent: Dict, message: str) -> Tuple[str, bool, bool, bool, List, List]:
        """
        Fetch appropriate context based on intent.
        
        Returns: (context, used_rag, used_web, used_health, obsidian_chunks, memory_items)
        """
        action = intent['action']
        use_rag = intent.get('use_rag', False)
        use_memory = intent.get('use_memory', False)
        
        context_parts = []
        obsidian_chunks = []
        memory_items = []
        used_rag = False
        used_web = False
        used_health = False
        
        # RAG/Obsidian notes
        if use_rag:
            # Check for identity queries - these need special handling
            message_lower = message.lower()
            is_user_identity_query = any(phrase in message_lower for phrase in [
                'who am i', 'tell me about myself', 'what do you know about me',
                'my profile', 'my information', 'about me'
            ])
            
            if is_user_identity_query:
                # For "Who am I?" queries, always load the user's profile file first
                user_profile_ctx = self._load_user_profile()
                if user_profile_ctx:
                    context_parts.append("### Your profile (from Artur Gomes.md)\n" + user_profile_ctx)
                    used_rag = True
                # Also do regular RAG but with better query
                obsidian_ctx, obsidian_chunks = vector_store.query_obsidian("Artur Gomes personal information")
                if obsidian_ctx:
                    context_parts.append("### Additional notes\n" + obsidian_ctx)
            else:
                obsidian_ctx, obsidian_chunks = vector_store.query_obsidian(message)
                if obsidian_ctx:
                    context_parts.append("### From your notes\n" + obsidian_ctx)
                    used_rag = True
        
        # Memory - search BOTH markdown memories AND user profile (Artur Gomes.md)
        if use_memory:
            from app.services.memory_store import MemoryStore
            memory_store = MemoryStore()
            
            # 1. Always load user profile for personal queries (authoritative source)
            user_profile_ctx = self._load_user_profile()
            if user_profile_ctx:
                context_parts.append("### From your profile (Artur Gomes.md)\n" + user_profile_ctx)
                memory_items.append({"id": "profile", "content": "User profile loaded"})
            
            # 2. Also search memories for recently learned facts
            markdown_memories = memory_store.search_memories(message, limit=5)
            
            if markdown_memories:
                memory_parts = []
                for mem in markdown_memories:
                    # Extract just the content, skip the markdown formatting
                    content = mem.get('full_content', '')
                    # Clean up: remove the header and context sections
                    if content:
                        # Take the main content (between title and Context section)
                        lines = content.split('\n')
                        clean_lines = []
                        for line in lines:
                            if line.strip().startswith('## Context'):
                                break
                            if line.strip() and not line.startswith('#'):
                                clean_lines.append(line.strip())
                        clean_content = ' '.join(clean_lines)
                        if clean_content:
                            memory_parts.append(f"[Memory] {clean_content}")
                            memory_items.append(mem)
                
                if memory_parts:
                    context_parts.append("### From your memories\n" + "\n\n".join(memory_parts))
        
        # Web search
        if action == 'web_search':
            web_ctx = web_search_service.search(message)
            if web_ctx:
                context_parts.append("### Web search results\n" + web_ctx)
                used_web = True
        
        # Health data
        if action == 'health_query':
            health_ctx = self.fetch_health_context(message)
            if health_ctx:
                context_parts.append(health_ctx)
                used_health = True
        
        combined_context = "\n\n".join(context_parts) if context_parts else ""
        
        return combined_context, used_rag, used_web, used_health, obsidian_chunks, memory_items
    
    def execute_tool(self, tool: str) -> str:
        """Execute a tool and return its output."""
        if tool == "current_time":
            return date_tools.get_current_time()
        
        elif tool == "calendar_today":
            events = calendar_service.get_today_events()
            if events:
                result = "📅 Today's calendar:\n"
                for e in events:
                    time_str = e.start.strftime("%I:%M %p")
                    result += f"• {time_str} - {e.summary}\n"
                    if e.location:
                        result += f"  📍 {e.location}\n"
                return result
            return "You have no events today."
        
        elif tool == "calendar_tomorrow":
            events = calendar_service.get_tomorrow_events()
            if events:
                result = "📅 Tomorrow's calendar:\n"
                for e in events:
                    time_str = e.start.strftime("%I:%M %p")
                    result += f"• {time_str} - {e.summary}\n"
                    if e.location:
                        result += f"  📍 {e.location}\n"
                return result
            return "You have no events tomorrow."
        
        elif tool == "calendar_week":
            events = calendar_service.get_upcoming_events(days=7)
            if events:
                result = "📅 This week's calendar:\n"
                for e in events:
                    date_str = e.start.strftime("%a, %b %d at %I:%M %p")
                    result += f"• {date_str} - {e.summary}\n"
                    if e.location:
                        result += f"  📍 {e.location}\n"
                return result
            return "You have no events this week."
        
        elif tool == "calendar_next":
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
                result = f"📅 Your next event is '{next_event.summary}' on {date_str} ({time_text})"
                if next_event.location:
                    result += f"\n📍 {next_event.location}"
                return result
            return "You have no upcoming events in the next 30 days."
        
        elif tool == "reminder_list":
            pending = reminder_service.list_pending_reminders()
            if pending:
                result = "Your pending reminders:\n"
                for idx, r in enumerate(pending, 1):
                    # Format the datetime nicely
                    remind_time = r.remind_at.strftime("%Y-%m-%d at %I:%M %p")
                    result += f"{idx}. {r.message} (at {remind_time})\n"
                result += f"\n💡 To delete: say 'delete reminder 1' or 'cancel reminder 2'"
                return result
            return "You have no pending reminders."
        
        elif tool == "reminder_next":
            pending = reminder_service.list_pending_reminders()
            if pending:
                # Get the next reminder (first in the sorted list)
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
        
        return ""
    
    def generate_system_prompt(self, action: str, message: str = "") -> str:
        """Generate clean system prompt based on action (no tool pollution)."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        
        # Load personality from file (cached)
        personality = self.personality
        
        # Build base prompt with personality and context
        base = f"Today is {today}, {current_time}.\n\n"
        
        if personality:
            # Use the personality from the file
            base += f"{personality}\n\n"
        else:
            # Fallback if file not found
            base += "You are Friday, a personal AI assistant for Artur Gomes.\n\n"
        
        # Always add this critical context
        base += (
            f"CRITICAL: The user speaking to you is Artur Gomes ({settings.authorized_user}). "
            f"All notes in the vault were written by Artur - they are HIS ideas, projects, and knowledge. "
            f"Do NOT confuse Artur with other people mentioned in his notes."
        )
        
        if action == "web_search":
            return (
                f"{base}\n\n"
                "Use the web search results provided to answer the user's question. "
                "Be direct, concise, and cite information from the results. "
                "Use Markdown formatting: *bold*, `code`, bullets."
            )
        
        elif action == "health_query":
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
            if any(phrase in message.lower() for phrase in ['daily health', 'health data', 'health summary', 'daily summary']):
                return (
                    f"{base}\n\n"
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
                    f"{base}\n\n"
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
        
        elif action == "general":
            return (
                f"{base}\n\n"
                "Rules:\n"
                "• Use provided context (notes/memory) ONLY if it helps answer the question\n"
                "• For greetings/small talk: be warm and brief\n"
                "• For questions: answer directly using relevant context\n"
                "• Be concise and helpful\n"
                "• Use Markdown formatting: *bold*, `code`, bullets"
            )
        
        else:
            return f"{base} Be helpful and concise. Use Markdown formatting."
    
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
        """
        Handle chat request with two-stage LLM architecture.
        
        Stage 1: Intent Router determines what to do
        Stage 2: Response Generator creates the answer
        """
        session_id = self.get_or_create_session(session_id)
        
        # STAGE 1: Intent Routing
        logger.info(f"[Stage 1] Routing intent for: {message[:50]}...")
        
        # Get last user message for context (helps with follow-up questions)
        history = self.get_history(session_id)
        last_user_msg = ""
        if history:
            # Find last user message
            for msg in reversed(history):
                if msg.get('role') == 'user':
                    last_user_msg = msg.get('content', '')
                    break
        
        # Check for pending memory conflict resolution
        pending_key = session_id + "_pending_memory"
        if pending_key in self.conversation_history:
            pending = self.conversation_history[pending_key]
            message_lower = message.lower().strip()
            
            if message_lower in ['update', 'yes', '1', 'replace']:
                # Update the existing memory
                from app.services.memory_store import MemoryStore
                memory_store = MemoryStore()
                
                # Delete old conflicting memories
                for conflict in pending['conflicts']:
                    memory_store.delete_memory(conflict['id'])
                
                # Add the new memory
                memory_id, _ = memory_store.add_memory(
                    content=pending['content'],
                    label="explicit_memory",
                    tags=pending['tags'],
                    force=True
                )
                
                del self.conversation_history[pending_key]
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": f"✅ Updated! Old memory replaced with: \"{pending['content']}\"",
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": pending['content'],
                }
            
            elif message_lower in ['add anyway', 'add', '2', 'keep both', 'both']:
                # Add anyway, keeping both
                from app.services.memory_store import MemoryStore
                memory_store = MemoryStore()
                
                memory_id, _ = memory_store.add_memory(
                    content=pending['content'],
                    label="explicit_memory",
                    tags=pending['tags'],
                    force=True
                )
                
                del self.conversation_history[pending_key]
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": f"✅ Added! I now have both memories stored.",
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": pending['content'],
                }
            
            elif message_lower in ['cancel', 'no', 'nevermind', 'forget it']:
                del self.conversation_history[pending_key]
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": "OK, I won't save that memory.",
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        intent = intent_router.route(message, last_message=last_user_msg)
        action = intent['action']
        tool = intent.get('tool')
        reminder_data = intent.get('reminder_data')
        reminder_index = intent.get('reminder_index')
        memory_data = intent.get('memory_data')
        
        # Handle memory_save - store a fact in memory
        if action == 'memory_save' and memory_data:
            logger.info(f"[Stage 1] Saving memory: {memory_data}")
            try:
                from app.services.memory_store import MemoryStore
                memory_store = MemoryStore()
                
                content = memory_data.get('content', '')
                tags = memory_data.get('tags', [])
                
                # Replace "my/I/me" with the user's name for better searchability
                content = self._personalize_memory(content)
                
                # Check for conflicts first
                memory_id, conflicts = memory_store.add_memory(
                    content=content,
                    label="explicit_memory",
                    tags=tags
                )
                
                if conflicts:
                    # Found conflicting memories - ask user what to do
                    conflict_list = "\n".join([
                        f"  • \"{c['content'][:100]}...\"" if len(c['content']) > 100 else f"  • \"{c['content']}\""
                        for c in conflicts[:3]
                    ])
                    
                    answer = (
                        f"⚠️ I found existing memories that might conflict with \"{content}\":\n\n"
                        f"{conflict_list}\n\n"
                        f"Would you like me to:\n"
                        f"1. **Update** the existing memory (replace the old info)\n"
                        f"2. **Add anyway** (keep both memories)\n\n"
                        f"Reply with \"update\" or \"add anyway\""
                    )
                    
                    # Store pending memory in session for follow-up
                    self.conversation_history[session_id + "_pending_memory"] = {
                        "content": content,
                        "tags": tags,
                        "conflicts": conflicts
                    }
                    
                    return {
                        "session_id": session_id,
                        "message": message,
                        "answer": answer,
                        "used_rag": False,
                        "used_web": False,
                        "used_memory": False,
                        "used_health": False,
                        "obsidian_chunks": [],
                        "memory_items": [],
                        "extracted_memory": None,
                    }
                
                answer = f"✅ Got it! I'll remember: \"{content}\""
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": content,
                }
            except Exception as e:
                logger.error(f"Memory save error: {e}", exc_info=True)
                answer = f"❌ Failed to save memory: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle memory_ambiguous - ask for clarification
        if action == 'memory_ambiguous' and memory_data:
            logger.info(f"[Stage 1] Ambiguous memory/reminder: {memory_data}")
            content = memory_data.get('content', '')
            
            answer = (
                f"I'm not sure what you mean by \"remember to {content}\".\n\n"
                f"Did you want me to:\n"
                f"1. **Set a reminder** - I'll notify you at a specific time\n"
                f"   → Say: \"Remind me to {content} in 30 minutes\" or \"at 3pm\"\n\n"
                f"2. **Save to memory** - I'll remember this fact for future conversations\n"
                f"   → Say: \"Remember that I need to {content}\" or \"Save this: {content}\""
            )
            
            return {
                "session_id": session_id,
                "message": message,
                "answer": answer,
                "used_rag": False,
                "used_web": False,
                "used_memory": False,
                "used_health": False,
                "obsidian_chunks": [],
                "memory_items": [],
                "extracted_memory": None,
            }
        
        # Handle reminder deletion
        if action == 'reminder_delete' and reminder_index is not None:
            logger.info(f"[Stage 1] Deleting reminder at index: {reminder_index}")
            try:
                # Get list of pending reminders
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
                        answer = f"✅ Deleted all {deleted_count} reminder(s)"
                    else:
                        answer = "❌ Failed to delete reminders"
                else:
                    # Handle "last" reminder (index -1)
                    if reminder_index == -1:
                        reminder_index = len(pending) - 1
                    
                    # Validate index
                    if reminder_index < 0 or reminder_index >= len(pending):
                        answer = f"❌ Invalid reminder number. You have {len(pending)} reminder(s). Please specify a number between 1 and {len(pending)}."
                    else:
                        # Get the reminder to delete
                        reminder_to_delete = pending[reminder_index]
                        
                        # Cancel it
                        success = reminder_service.cancel_reminder(reminder_to_delete.id)
                        
                        if success:
                            answer = f"✅ Deleted reminder: '{reminder_to_delete.message}'"
                        else:
                            answer = f"❌ Failed to delete reminder"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Reminder deletion error: {e}", exc_info=True)
                answer = f"❌ Failed to delete reminder: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle reminder creation
        if action == 'reminder_create' and reminder_data:
            logger.info(f"[Stage 1] Creating reminder: {reminder_data}")
            try:
                import re
                reminder_msg = reminder_data.get('message', '')
                time_spec = reminder_data.get('time_spec', '').lower()
                
                # Parse time specification
                reminder_obj = None
                
                # Try relative time first (e.g., "30 minutes", "2 hours", "in 30 minutes")
                minutes_match = re.search(r'(\d+)\s*minute', time_spec)
                hours_match = re.search(r'(\d+)\s*hour', time_spec)
                
                if minutes_match:
                    minutes = int(minutes_match.group(1))
                    reminder_obj = reminder_service.create_reminder(reminder_msg, minutes=minutes)
                    user_tz = settings.user_timezone
                    remind_time = (datetime.now(user_tz) + timedelta(minutes=minutes)).strftime("%I:%M %p")
                    answer = f"✅ Reminder set: '{reminder_msg}' at {remind_time} ({minutes} minutes from now)"
                    
                elif hours_match:
                    hours = int(hours_match.group(1))
                    reminder_obj = reminder_service.create_reminder(reminder_msg, hours=hours)
                    user_tz = settings.user_timezone
                    remind_time = (datetime.now(user_tz) + timedelta(hours=hours)).strftime("%I:%M %p")
                    answer = f"✅ Reminder set: '{reminder_msg}' at {remind_time} ({hours} hours from now)"
                    
                else:
                    # Try absolute time (e.g., "15:40", "3pm", "15:40 today", "3pm tomorrow")
                    # Extract time part (HH:MM or H:MMpm format)
                    time_match = re.search(r'(\d{1,2}):(\d{2})|(\d{1,2})\s*(am|pm)', time_spec)
                    
                    if time_match:
                        # Determine date: today, tomorrow, or specific date
                        if 'tomorrow' in time_spec:
                            user_tz = settings.user_timezone
                            target_date = (datetime.now(user_tz) + timedelta(days=1)).strftime("%Y-%m-%d")
                            on_date = target_date
                        else:
                            # Default to today
                            on_date = "today"
                        
                        # Extract time and convert to HH:MM format
                        if time_match.group(1):  # HH:MM format (already correct)
                            at_time = f"{time_match.group(1)}:{time_match.group(2)}"
                            display_time = at_time
                        else:  # H am/pm format - convert to HH:MM
                            hour = int(time_match.group(3))
                            ampm = time_match.group(4).lower()
                            
                            # Convert to 24-hour format
                            if ampm == 'pm' and hour != 12:
                                hour += 12
                            elif ampm == 'am' and hour == 12:
                                hour = 0
                            
                            at_time = f"{hour:02d}:00"
                            display_time = f"{time_match.group(3)}{ampm}"
                        
                        reminder_obj = reminder_service.create_reminder(
                            reminder_msg, 
                            at_time=at_time,
                            on_date=on_date
                        )
                        answer = f"✅ Reminder set: '{reminder_msg}' at {display_time}"
                        if on_date != "today":
                            answer += f" on {on_date}"
                    else:
                        answer = f"❌ Couldn't parse time '{time_spec}'. Try: 'in 30 minutes', 'at 3pm', or 'at 15:40'"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Reminder creation error: {e}", exc_info=True)
                answer = f"❌ Failed to create reminder: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle note operations
        note_data = intent.get('note_data')
        
        # Handle note creation
        if action == 'note_create' and note_data:
            logger.info(f"[Stage 1] Creating note: {note_data}")
            try:
                title = note_data.get('title', 'Untitled')
                content = note_data.get('content', '')
                folder = note_data.get('folder')
                tags = note_data.get('tags', [])
                
                filepath = obsidian_service.create_note(
                    title=title,
                    content=content,
                    folder=folder,
                    tags=tags
                )
                
                # Escape underscores for Telegram markdown
                safe_title = title.replace('_', '\\_')
                answer = f"✅ Created note: {safe_title}"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Note creation error: {e}", exc_info=True)
                answer = f"❌ Failed to create note: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle note update
        if action == 'note_update' and note_data:
            logger.info(f"[Stage 1] Updating note: {note_data}")
            try:
                title = note_data.get('title', '')
                content = note_data.get('content', '')
                append = note_data.get('append', True)
                add_date_header = note_data.get('add_date_header', False)
                
                # Add date header if requested
                if add_date_header:
                    today_str = datetime.now().strftime("%d/%m/%y")
                    content = f"### {today_str}\n\n{content}"
                
                if not title:
                    answer = "❌ Please specify which note to update"
                else:
                    filepath = obsidian_service.update_note(
                        title=title,
                        new_content=content,
                        append=append
                    )
                    
                    if filepath:
                        action_word = "Added to" if append else "Updated"
                        safe_title = title.replace('_', '\\_')
                        answer = f"✅ {action_word} note: {safe_title}"
                    else:
                        answer = f"❌ Note not found: '{title}'"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Note update error: {e}", exc_info=True)
                answer = f"❌ Failed to update note: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle note search
        if action == 'note_search':
            logger.info(f"[Stage 1] Searching notes: {note_data}")
            try:
                query = note_data.get('title', '') if note_data else ''
                
                if query:
                    # Search by query
                    results = obsidian_service.search_notes(query, limit=10)
                    if results:
                        safe_query = query.replace('_', '\\_')
                        answer = f"📝 Found {len(results)} note(s) matching '{safe_query}':\n\n"
                        for i, note in enumerate(results, 1):
                            safe_title = note['title'].replace('_', '\\_')
                            answer += f"{i}. {safe_title}\n"
                            if note.get('preview'):
                                safe_preview = note['preview'][:100].replace('_', '\\_')
                                answer += f"   {safe_preview}...\n"
                    else:
                        answer = f"No notes found matching '{query}'"
                else:
                    # List recent notes
                    results = obsidian_service.list_notes(limit=10)
                    if results:
                        answer = "📝 Recent notes:\n\n"
                        for i, note in enumerate(results, 1):
                            safe_title = note['title'].replace('_', '\\_')
                            answer += f"{i}. {safe_title}\n"
                    else:
                        answer = "No notes found in your vault"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Note search error: {e}", exc_info=True)
                answer = f"❌ Failed to search notes: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle note get (retrieve full note content)
        if action == 'note_get':
            logger.info(f"[Stage 1] Getting note: {note_data}")
            try:
                title = note_data.get('title', '') if note_data else ''
                
                if not title:
                    answer = "❌ Please specify which note you want to see"
                else:
                    result = obsidian_service.get_note(title)
                    if result:
                        content = result['content']
                        # Strip frontmatter for cleaner display
                        if "---" in content:
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                content = parts[2].strip()
                        # Escape underscores for Telegram markdown
                        safe_title = result['title'].replace('_', '\\_')
                        safe_content = content.replace('_', '\\_')
                        answer = f"📝 {safe_title}\n\n{safe_content}"
                    else:
                        answer = f"❌ Note not found: '{title}'"
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Note get error: {e}", exc_info=True)
                answer = f"❌ Failed to get note: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle morning report
        if action == 'morning_report':
            logger.info(f"[Stage 1] Generating morning report")
            try:
                from app.services.morning_report import generate_morning_report
                from app.services.unified_calendar_service import UnifiedCalendarService
                from app.services.llm import LLMService
                
                # Get health coach
                health_coach = self.health_coach
                calendar_service = UnifiedCalendarService()
                llm_svc = LLMService()
                
                answer = generate_morning_report(
                    health_coach=health_coach,
                    calendar_service=calendar_service,
                    llm_service=llm_svc
                )
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": True,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Morning report error: {e}", exc_info=True)
                answer = f"❌ Failed to generate morning report: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # Handle evening report
        if action == 'evening_report':
            logger.info(f"[Stage 1] Generating evening report")
            try:
                from app.services.evening_report import generate_evening_report
                from app.services.unified_calendar_service import UnifiedCalendarService
                from app.services.llm import LLMService
                
                # Get health coach
                health_coach = self.health_coach
                calendar_service = UnifiedCalendarService()
                llm_svc = LLMService()
                
                answer = generate_evening_report(
                    health_coach=health_coach,
                    calendar_service=calendar_service,
                    llm_service=llm_svc
                )
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": True,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Evening report error: {e}", exc_info=True)
                answer = f"❌ Failed to generate evening report: {str(e)}"
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
        
        # If it's a tool query, execute it directly and return
        if tool:
            logger.info(f"[Stage 1] Executing tool: {tool}")
            answer = self.execute_tool(tool)
            
            return {
                "session_id": session_id,
                "message": message,
                "answer": answer,
                "used_rag": False,
                "used_web": False,
                "used_memory": False,
                "used_health": False,
                "obsidian_chunks": [],
                "memory_items": [],
                "extracted_memory": None,
            }
        
        # STAGE 2: Fetch context and generate response
        logger.info(f"[Stage 2] Fetching context for action: {action}")
        context, used_rag, used_web, used_health, obsidian_chunks, memory_items = self.fetch_context_by_intent(
            intent, message
        )
        
        # Generate system prompt (clean, no tool instructions)
        system_prompt = self.generate_system_prompt(action, message)
        
        # Get conversation history
        history = self.get_history(session_id)
        
        # Build user content
        if context:
            user_content = f"User question:\n{message}\n\nContext:\n{context}"
        else:
            user_content = message
        
        # Call LLM to generate response
        logger.info(f"[Stage 2] Generating response...")
        answer = llm_service.call(
            system_prompt=system_prompt,
            user_content=user_content,
            history=history,
            stream=False
        )
        
        # Update conversation history
        self.update_history(session_id, message, answer)
        
        # Post-chat processing: Extract memories and tasks in background thread
        if save_memory and action == 'general':
            # Run async processing in background thread (don't block response)
            def run_async_processor():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        post_chat_processor.process_conversation(message, answer, history)
                    )
                    loop.close()
                except Exception as e:
                    logger.error(f"Post-chat processing error: {e}", exc_info=True)
            
            thread = threading.Thread(target=run_async_processor, daemon=True)
            thread.start()
            logger.info("Started post-chat processing thread (memory & task extraction)")
        
        return {
            "session_id": session_id,
            "message": message,
            "answer": answer,
            "used_rag": used_rag,
            "used_web": used_web,
            "used_memory": len(memory_items) > 0,
            "used_health": used_health,
            "obsidian_chunks": obsidian_chunks,
            "memory_items": memory_items,
            "extracted_memory": None,  # Deprecated - now handled by post_chat_processor
        }


# Singleton instance
chat_service = ChatService()
