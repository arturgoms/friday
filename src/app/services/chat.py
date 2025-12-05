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
from app.services.unified_calendar_service import unified_calendar_service
from app.services.post_chat_processor import post_chat_processor
from app.services.obsidian import obsidian_service
from app.services.conversation_memory import conversation_memory
from app.services.correction_detector import correction_detector
from app.services.obsidian_knowledge import obsidian_knowledge
from app.services.relationship_state import relationship_tracker, opinion_store
from app.services.task_manager import task_manager, TaskStatus, TaskPriority, TaskContext
from app.services.alert_store import alert_store, AlertType
from app.services.memory_store import MemoryStore


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
        
        # Conversation memory - add context from past conversations on this topic
        # This includes corrections I've received, advice I've given, etc.
        conv_memory_ctx = conversation_memory.get_context_for_message(message)
        if conv_memory_ctx:
            context_parts.append(conv_memory_ctx)
        
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
        
        elif tool == "calendar_find_free":
            # This is handled in the main chat flow with free_time_data
            # But we can return a default result if called directly
            free_slots = unified_calendar_service.find_free_slots(days=7, duration_minutes=60)
            if free_slots:
                result = "📅 Free time slots in the next 7 days:\n\n"
                for slot in free_slots[:10]:  # Limit to 10 slots
                    result += f"• {slot['date']}: {slot['start']} - {slot['end']} ({slot['duration_minutes']} min)\n"
                return result
            return "No free slots found in your calendar for the next 7 days."
        
        elif tool == "task_list":
            tasks = task_manager.list_tasks(status=TaskStatus.TODO, limit=20)
            in_progress = task_manager.list_tasks(status=TaskStatus.IN_PROGRESS, limit=10)
            all_tasks = in_progress + tasks
            
            if all_tasks:
                result = "📋 Your tasks:\n\n"
                for task in all_tasks:
                    status_icon = "🔄" if task.status == TaskStatus.IN_PROGRESS else "⬜"
                    priority_icon = {"URGENT": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(task.priority.name, "")
                    due_str = f" (due {task.due_date.strftime('%b %d')})" if task.due_date else ""
                    result += f"{status_icon} {priority_icon} {task.title}{due_str}\n"
                return result
            return "You have no pending tasks."
        
        elif tool == "task_today":
            tasks = task_manager.get_tasks_for_today()
            if tasks:
                result = "📋 Today's tasks:\n\n"
                for task in tasks:
                    status_icon = "🔄" if task.status == TaskStatus.IN_PROGRESS else "⬜"
                    priority_icon = {"URGENT": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(task.priority.name, "")
                    result += f"{status_icon} {priority_icon} {task.title}\n"
                return result
            return "You have no tasks scheduled for today."
        
        elif tool == "alert_list":
            alerts = alert_store.list_active_alerts()
            if alerts:
                result = "🔔 Active alerts:\n\n"
                for alert in alerts:
                    type_icon = {
                        "date_reminder": "📅",
                        "recurring": "🔁",
                        "condition": "⚡",
                        "health_watch": "❤️",
                        "deadline": "⏰",
                    }.get(alert.alert_type.value, "🔔")
                    
                    trigger_info = ""
                    if alert.recurring_pattern:
                        trigger_info = f" ({alert.recurring_pattern})"
                    elif alert.trigger_date:
                        trigger_info = f" ({alert.trigger_date.strftime('%b %d')})"
                    
                    result += f"{type_icon} {alert.title}{trigger_info}\n"
                    result += f"   ID: {alert.alert_id}\n"
                return result
            return "You have no active alerts."
        
        elif tool == "memory_list":
            memory_store = MemoryStore()
            memories = memory_store.list_memories(limit=15)
            if memories:
                result = "🧠 Your memories:\n\n"
                for mem in memories:
                    content_preview = mem['content'][:80] + "..." if len(mem['content']) > 80 else mem['content']
                    result += f"• {content_preview}\n"
                    result += f"  (ID: {mem['id']})\n\n"
                return result
            return "I haven't stored any memories yet."
        
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
            # Add corrections awareness
            corrections_context = conversation_memory.get_all_corrections_context()
            corrections_note = ""
            if corrections_context:
                corrections_note = f"\n\n{corrections_context}\n"
            
            # Add Obsidian knowledge for note-related queries
            obsidian_context = obsidian_knowledge.get_context_for_llm()
            
            # Add relationship context for tone/behavior adjustment
            relationship_context = relationship_tracker.get_context_for_llm()
            
            # Add opinions context - Friday's learned views and patterns
            opinions_context = opinion_store.get_context_for_llm(message)
            
            return (
                f"{base}\n\n"
                f"{corrections_note}"
                f"{relationship_context}\n\n"
                f"{opinions_context}\n\n"
                f"{obsidian_context}\n\n"
                "Rules:\n"
                "• For GREETINGS and SMALL TALK (hey, what's up, how are you): respond naturally and briefly like a friend would. Don't dump information or context.\n"
                "• Use provided context (notes/memory) ONLY if the user is actually asking about something in their notes\n"
                "• If you've been corrected on a topic before, use the CORRECT information\n"
                "• Express your opinions when relevant - you have views based on our interactions\n"
                "• Push back if you think something is a bad idea - be honest\n"
                "• When creating or suggesting notes, follow the Obsidian note system above\n"
                "• Adjust your tone based on relationship context and user's apparent mood\n"
                "• Be concise and conversational, not robotic or overly structured\n"
                "• Use Markdown formatting only when helpful: *bold*, `code`, bullets"
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
        
        # Handle vault health check
        if action == 'vault_health':
            logger.info(f"[Stage 1] Running vault health check")
            try:
                health_result = obsidian_knowledge.run_health_check()
                
                # Format the response
                score = health_result["health_score"]
                status = health_result["status"].replace("_", " ").title()
                
                answer_lines = [f"## Vault Health Check: {status} ({score}/100)\n"]
                
                summary = health_result["summary"]
                answer_lines.append("### Summary")
                answer_lines.append(f"- **Inbox backlog:** {summary['inbox_backlog']} notes")
                answer_lines.append(f"- **Stale notes:** {summary['stale_notes']} (30+ days)")
                answer_lines.append(f"- **Missing tags:** {summary['missing_tags']} notes")
                answer_lines.append(f"- **Misplaced notes:** {summary['misplaced_notes']}")
                answer_lines.append("")
                
                if health_result["recommendations"]:
                    answer_lines.append("### Recommendations")
                    for rec in health_result["recommendations"]:
                        answer_lines.append(f"- {rec}")
                
                answer = "\n".join(answer_lines)
                
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
                logger.error(f"Vault health check error: {e}", exc_info=True)
                answer = f"❌ Failed to run vault health check: {str(e)}"
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
        
        # Handle body_health_check - comprehensive Garmin health assessment
        if action == 'body_health_check':
            logger.info(f"[Stage 1] Running body health check")
            try:
                from app.services.health_coach import get_health_coach
                
                health_coach = get_health_coach()
                if not health_coach:
                    answer = "❌ Health coach is not available. Check InfluxDB connection."
                else:
                    health_result = health_coach.run_health_check()
                    
                    # Format the response
                    score = health_result["health_score"]
                    status = health_result["status"].replace("_", " ").title()
                    emoji = health_result["status_emoji"]
                    
                    answer_lines = [f"## Body Health Check: {status} {emoji} ({score}/100)\n"]
                    
                    # Key metrics
                    details = health_result.get("details", {})
                    if details:
                        answer_lines.append("### Current Metrics")
                        if "body_battery" in details:
                            answer_lines.append(f"- **Body Battery:** {details['body_battery']}/100")
                        if "training_readiness" in details:
                            answer_lines.append(f"- **Training Readiness:** {details['training_readiness']}/100")
                        if "hrv" in details:
                            hrv_avg = details.get('hrv_7day_avg', 'N/A')
                            answer_lines.append(f"- **HRV:** {details['hrv']}ms (7-day avg: {hrv_avg}ms)")
                        if "recovery_time_hours" in details:
                            answer_lines.append(f"- **Recovery Time:** {details['recovery_time_hours']}h")
                        if "last_sleep" in details:
                            sleep = details["last_sleep"]
                            answer_lines.append(f"- **Last Sleep:** {sleep.get('total_sleep', 'N/A')} (score: {sleep.get('sleep_score', 'N/A')})")
                        if "current_stress" in details or "avg_stress_today" in details:
                            current = details.get('current_stress', 'N/A')
                            avg_today = details.get('avg_stress_today', 'N/A')
                            avg_7day = details.get('avg_stress_7day', 'N/A')
                            if current != 'N/A':
                                answer_lines.append(f"- **Stress:** {current}/100 (today avg: {avg_today}, 7-day avg: {avg_7day})")
                            else:
                                answer_lines.append(f"- **Stress (today avg):** {avg_today}/100 (7-day avg: {avg_7day})")
                        answer_lines.append("")
                    
                    # Issues
                    if health_result.get("issues"):
                        answer_lines.append("### Issues Found")
                        for issue in health_result["issues"]:
                            answer_lines.append(f"- ⚠️ {issue}")
                        answer_lines.append("")
                    
                    # Recommendations
                    answer_lines.append("### Recommendations")
                    for rec in health_result.get("recommendations", []):
                        answer_lines.append(f"- {rec}")
                    
                    answer = "\n".join(answer_lines)
                
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
                logger.error(f"Body health check error: {e}", exc_info=True)
                answer = f"❌ Failed to run body health check: {str(e)}"
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
        
        # Handle calendar_find_free - find free time slots with LLM-powered suggestions
        if action == 'calendar_find_free':
            logger.info(f"[Stage 1] Finding free time slots with smart suggestions")
            try:
                import os
                import requests
                
                free_time_data = intent.get('free_time_data', {}) or {}
                days = free_time_data.get('days', 7)
                duration = free_time_data.get('duration_minutes', 60)
                purpose = free_time_data.get('purpose', '')
                start_from_day = free_time_data.get('start_from_day', 0)  # Skip first N days
                
                # Handle "next week" - calculate days until next Monday
                if free_time_data.get('next_week'):
                    user_tz = settings.user_timezone
                    today = datetime.now(user_tz).date()
                    days_until_monday = (7 - today.weekday()) % 7
                    if days_until_monday == 0:  # Today is Monday, so next week is 7 days
                        days_until_monday = 7
                    start_from_day = days_until_monday
                    logger.info(f"'Next week' detected - starting from day {start_from_day} (Monday)")
                
                # Get free slots from calendar
                # If start_from_day is set, we need to fetch enough days to cover that period
                fetch_days = days + start_from_day if start_from_day > 0 else days
                free_slots = unified_calendar_service.find_free_slots(
                    days=fetch_days,
                    duration_minutes=duration
                )
                
                # Filter slots to start from a specific day (for "next week" queries)
                if start_from_day > 0:
                    user_tz = settings.user_timezone
                    start_date = (datetime.now(user_tz) + timedelta(days=start_from_day)).date()
                    free_slots = [s for s in free_slots if s['datetime_start'].date() >= start_date]
                    logger.info(f"Filtered to start from day {start_from_day} ({start_date}), {len(free_slots)} slots remaining")
                
                # Log what we got before filtering
                total_slots_before = len(free_slots)
                logger.info(f"Found {total_slots_before} total free slots before weekend filtering")
                
                # Filter out weekends for activities that require weekdays
                purpose_lower = (purpose or '').lower()
                weekday_only_activities = ['barber', 'haircut', 'hair cut', 'salon', 'bank', 'post office', 'government', 'dmv', 'office']
                
                needs_weekday = any(activity in purpose_lower for activity in weekday_only_activities)
                if needs_weekday:
                    # Filter to only weekdays (Monday=0 to Friday=4)
                    weekend_slots = [slot for slot in free_slots if slot['datetime_start'].weekday() >= 5]
                    free_slots = [
                        slot for slot in free_slots 
                        if slot['datetime_start'].weekday() < 5  # 0-4 are Mon-Fri
                    ]
                    logger.info(f"Filtered to weekdays only for '{purpose}': {len(weekend_slots)} weekend slots removed, {len(free_slots)} weekday slots remaining")
                
                if not free_slots:
                    # Try to explain why there are no slots
                    if needs_weekday and total_slots_before > 0:
                        answer = f"❌ No free weekday slots found for {purpose}. Your weekdays appear to be fully booked. You had {total_slots_before} weekend slots available - would you like me to look further ahead or show weekend options anyway?"
                    else:
                        answer = f"❌ No free slots found in your calendar for the specified period."
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
                
                # Format slots for LLM context
                slots_text = "FREE TIME SLOTS:\n"
                for slot in free_slots[:15]:  # Limit to 15 slots
                    day_name = slot['datetime_start'].strftime("%A")  # Full day name
                    slots_text += f"- {slot['date']} ({day_name}): {slot['start']} - {slot['end']} ({slot['duration_minutes']} min available)\n"
                
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
                
                # Get weather forecast for the next days
                weather_text = ""
                try:
                    weather_api_key = os.getenv('WEATHER_API_KEY')
                    city = os.getenv('WEATHER_CITY', 'São Paulo')
                    
                    if weather_api_key:
                        # Get current weather
                        current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric&lang=en"
                        current_response = requests.get(current_url, timeout=5)
                        
                        # Get forecast
                        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={weather_api_key}&units=metric&lang=en"
                        forecast_response = requests.get(forecast_url, timeout=5)
                        
                        if current_response.status_code == 200:
                            current = current_response.json()
                            weather_text = f"\nWEATHER:\n"
                            weather_text += f"- Current: {current['weather'][0]['description']}, {current['main']['temp']:.0f}°C\n"
                        
                        if forecast_response.status_code == 200:
                            forecast = forecast_response.json()
                            # Get forecast for next few days (one entry per day around midday)
                            seen_dates = set()
                            for entry in forecast['list']:
                                entry_time = datetime.fromtimestamp(entry['dt'], tz=settings.user_timezone)
                                entry_date = entry_time.date()
                                
                                # Skip today, get midday forecasts for next days
                                if entry_date <= datetime.now(settings.user_timezone).date():
                                    continue
                                if entry_date in seen_dates:
                                    continue
                                if entry_time.hour < 11 or entry_time.hour > 14:
                                    continue
                                
                                seen_dates.add(entry_date)
                                day_name = entry_time.strftime("%A, %b %d")
                                desc = entry['weather'][0]['description']
                                temp = entry['main']['temp']
                                
                                # Flag rainy days
                                rain_warning = ""
                                if 'rain' in desc.lower() or 'storm' in desc.lower() or 'shower' in desc.lower():
                                    rain_warning = " ⚠️ RAIN"
                                
                                weather_text += f"- {day_name}: {desc}, {temp:.0f}°C{rain_warning}\n"
                                
                                if len(seen_dates) >= 5:
                                    break
                except Exception as e:
                    logger.debug(f"Weather fetch for scheduling skipped: {e}")
                
                # Get memory context
                from app.services.memory_store import memory_store
                memory_context = memory_store.get_context_string(purpose if purpose else message, limit=3)
                memory_text = ""
                if memory_context:
                    memory_text = f"\nRELEVANT MEMORIES:\n{memory_context}\n"
                
                # Build LLM prompt for smart suggestions
                suggestion_prompt = f"""You are helping the user find the best time for: {purpose if purpose else 'an activity'}

The user asked: "{message}"

Here is the context:

{slots_text}
{events_text}
{reminders_text}
{weather_text}
{memory_text}

TODAY: {datetime.now(settings.user_timezone).strftime("%A, %B %d, %Y")}

IMPORTANT RULES for suggesting times:
1. **Prefer earlier dates**: For simple errands (haircut, shopping, etc.), suggest the EARLIEST available slots first. Don't skip to later dates without a good reason.
2. **Barber shops / hair salons**: ALWAYS suggest WEEKDAYS ONLY (Monday-Friday). Barbers are typically closed on Sundays and often on Saturdays too. NEVER suggest weekend slots for haircuts.
3. **Outdoor activities**: Avoid days with rain in the forecast
4. **Medical appointments**: Suggest morning slots when possible
5. **Errands/shopping**: Consider store hours and avoid rainy days

YOUR RESPONSE MUST INCLUDE:

**Recommended slots (2-3):**
- Suggest specific times (e.g., "Monday at 10:00 AM", not "Monday 9am-5pm")
- Briefly explain WHY each slot is good

**Not recommended (1-2):**
- List any early slots you're SKIPPING and explain WHY
- For example: "I'm not suggesting Monday because..." or "Tuesday morning isn't ideal because..."

This helps the user understand your reasoning. Keep it concise."""

                # Call LLM for smart suggestions
                answer = llm_service.call(
                    system_prompt="You are Friday, a helpful AI assistant. Give practical scheduling suggestions based on the user's calendar and context. Be concise and friendly.",
                    user_content=suggestion_prompt,
                    history=[],
                    stream=False
                )
                
                return {
                    "session_id": session_id,
                    "message": message,
                    "answer": answer,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": True,
                    "used_health": False,
                    "obsidian_chunks": [],
                    "memory_items": [],
                    "extracted_memory": None,
                }
            except Exception as e:
                logger.error(f"Calendar find free error: {e}", exc_info=True)
                answer = f"❌ Failed to find free time: {str(e)}"
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
        
        # Handle calendar_create - create new calendar event
        if action == 'calendar_create':
            logger.info(f"[Stage 1] Creating calendar event")
            try:
                calendar_data = intent.get('calendar_data', {}) or {}
                summary = calendar_data.get('summary', 'New Event')
                date_str = calendar_data.get('date', 'today')
                time_str = calendar_data.get('time', '09:00')
                duration = calendar_data.get('duration_minutes', 60)
                location = calendar_data.get('location')
                
                # Parse date and time
                user_tz = settings.user_timezone
                now = datetime.now(user_tz)
                
                # Parse date
                if date_str.lower() == 'today':
                    event_date = now.date()
                elif date_str.lower() == 'tomorrow':
                    event_date = (now + timedelta(days=1)).date()
                else:
                    # Try to parse day name (e.g., "Friday")
                    import calendar
                    day_names = list(calendar.day_name)
                    day_lower = date_str.lower().capitalize()
                    if day_lower in day_names:
                        target_day = day_names.index(day_lower)
                        days_ahead = target_day - now.weekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        event_date = (now + timedelta(days=days_ahead)).date()
                    else:
                        # Try parsing as date
                        try:
                            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        except ValueError:
                            event_date = now.date()
                
                # Parse time
                import re
                time_match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str.lower())
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    ampm = time_match.group(3)
                    
                    if ampm == 'pm' and hour != 12:
                        hour += 12
                    elif ampm == 'am' and hour == 12:
                        hour = 0
                else:
                    hour, minute = 9, 0
                
                start_dt = datetime.combine(event_date, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=user_tz)
                end_dt = start_dt + timedelta(minutes=duration)
                
                event = unified_calendar_service.create_event(
                    summary=summary,
                    start=start_dt,
                    end=end_dt,
                    location=location
                )
                
                if event:
                    answer = f"✅ Created event: **{summary}**\n"
                    answer += f"📅 {start_dt.strftime('%a, %b %d at %I:%M %p')}\n"
                    answer += f"⏱️ Duration: {duration} minutes"
                    if location:
                        answer += f"\n📍 {location}"
                else:
                    answer = "❌ Failed to create event. Please try again."
                
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
                logger.error(f"Calendar create error: {e}", exc_info=True)
                answer = f"❌ Failed to create event: {str(e)}"
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
        
        # Handle task_create - create new task
        if action == 'task_create':
            logger.info(f"[Stage 1] Creating task")
            try:
                task_data = intent.get('task_data', {}) or {}
                title = task_data.get('title', '')
                priority_str = task_data.get('priority', 'medium').upper()
                context_str = task_data.get('context', 'any').upper()
                due_date_str = task_data.get('due_date')
                
                if not title:
                    answer = "❌ Please specify what task you want to create."
                else:
                    # Parse priority
                    priority = getattr(TaskPriority, priority_str, TaskPriority.MEDIUM)
                    
                    # Parse context
                    context = getattr(TaskContext, context_str, TaskContext.ANY)
                    
                    # Parse due date
                    due_date = None
                    if due_date_str:
                        user_tz = settings.user_timezone
                        now = datetime.now(user_tz)
                        if due_date_str.lower() == 'today':
                            due_date = now.replace(hour=23, minute=59)
                        elif due_date_str.lower() == 'tomorrow':
                            due_date = (now + timedelta(days=1)).replace(hour=23, minute=59)
                    
                    task = task_manager.create_task(
                        title=title,
                        priority=priority,
                        context=context,
                        due_date=due_date
                    )
                    
                    priority_icon = {"URGENT": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority.name, "")
                    answer = f"✅ Created task: {priority_icon} {title}"
                    if due_date:
                        answer += f" (due {due_date.strftime('%b %d')})"
                
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
                logger.error(f"Task create error: {e}", exc_info=True)
                answer = f"❌ Failed to create task: {str(e)}"
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
        
        # Handle task_complete - mark task as done
        if action == 'task_complete':
            logger.info(f"[Stage 1] Completing task")
            try:
                task_data = intent.get('task_data', {}) or {}
                task_id_or_title = task_data.get('task_id', '')
                
                if not task_id_or_title:
                    answer = "❌ Please specify which task to complete."
                else:
                    # First try to find by exact ID
                    task = task_manager.get_task(task_id_or_title)
                    
                    # If not found, search by title
                    if not task:
                        tasks = task_manager.list_tasks(status=TaskStatus.TODO, limit=100)
                        tasks += task_manager.list_tasks(status=TaskStatus.IN_PROGRESS, limit=100)
                        
                        # Find task by partial title match
                        search_lower = task_id_or_title.lower()
                        for t in tasks:
                            if search_lower in t.title.lower():
                                task = t
                                break
                    
                    if task:
                        task_manager.update_task_status(task.id, TaskStatus.DONE)
                        answer = f"✅ Completed: {task.title}"
                    else:
                        answer = f"❌ Task not found: '{task_id_or_title}'"
                
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
                logger.error(f"Task complete error: {e}", exc_info=True)
                answer = f"❌ Failed to complete task: {str(e)}"
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
        
        # Handle alert_create - create new proactive alert
        if action == 'alert_create':
            logger.info(f"[Stage 1] Creating alert")
            try:
                alert_data = intent.get('alert_data', {}) or {}
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
                    user_tz = settings.user_timezone
                    now = datetime.now(user_tz)
                    
                    # Parse day name for recurring
                    import calendar
                    day_names = [d.lower() for d in calendar.day_name]
                    if trigger_date_str.lower() in day_names:
                        target_day = day_names.index(trigger_date_str.lower())
                        days_ahead = target_day - now.weekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        trigger_date = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0)
                
                alert = alert_store.create_alert(
                    title=title,
                    description=description,
                    alert_type=alert_type,
                    trigger_date=trigger_date,
                    trigger_condition=trigger_condition,
                    recurring_pattern=recurring,
                    source_context=f"Created from chat: {message[:200]}"
                )
                
                answer = f"✅ Created alert: **{title}**\n"
                if recurring:
                    answer += f"🔁 Recurring: {recurring}\n"
                if trigger_condition:
                    answer += f"⚡ Condition: {trigger_condition}\n"
                if trigger_date:
                    answer += f"📅 First trigger: {trigger_date.strftime('%a, %b %d at %I:%M %p')}"
                answer += f"\n\nAlert ID: {alert.alert_id}"
                
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
                logger.error(f"Alert create error: {e}", exc_info=True)
                answer = f"❌ Failed to create alert: {str(e)}"
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
        
        # Handle alert_delete - delete/deactivate an alert
        if action == 'alert_delete':
            logger.info(f"[Stage 1] Deleting alert")
            try:
                alert_data = intent.get('alert_data', {}) or {}
                alert_id_or_topic = alert_data.get('alert_id', '')
                
                if not alert_id_or_topic:
                    answer = "❌ Please specify which alert to delete."
                else:
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
                        answer = f"✅ Deactivated alert: {found_alert.title}"
                    else:
                        answer = f"❌ Alert not found: '{alert_id_or_topic}'"
                
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
                logger.error(f"Alert delete error: {e}", exc_info=True)
                answer = f"❌ Failed to delete alert: {str(e)}"
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
        
        # Handle budget_status - show skipped alerts and budget info
        if action == 'budget_status':
            logger.info(f"[Stage 1] Getting budget status")
            try:
                from app.services.proactive_monitor import proactive_monitor
                
                stats = proactive_monitor.get_budget_stats()
                skipped = proactive_monitor.get_skipped_alerts()
                
                # Build response
                lines = [
                    f"📊 **Alert Budget Status** ({stats.get('date', 'today')})",
                    f"",
                    f"• Messages sent: {stats.get('messages_sent', 0)}/{5}",
                    f"• Remaining budget: {stats.get('remaining', 0)}",
                    f"• User responses: {stats.get('user_responses', 0)}",
                    f"• Ignored: {stats.get('ignored', 0)}",
                ]
                
                if skipped:
                    lines.append(f"")
                    lines.append(f"**⏭️ Skipped Alerts ({len(skipped)}):**")
                    for i, alert in enumerate(skipped, 1):
                        lines.append(f"")
                        lines.append(f"{i}. **{alert.get('title', 'Untitled')}** [{alert.get('priority', 'unknown')}]")
                        lines.append(f"   {alert.get('message', '')[:100]}")
                        lines.append(f"   _Skipped at: {alert.get('skipped_at', 'unknown')[:16]}_")
                else:
                    lines.append(f"")
                    lines.append(f"✅ No alerts were skipped today.")
                
                answer = "\n".join(lines)
                
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
                logger.error(f"Budget status error: {e}", exc_info=True)
                answer = f"❌ Failed to get budget status: {str(e)}"
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
        
        # Handle budget_reset - reset the alert budget
        if action == 'budget_reset':
            logger.info(f"[Stage 1] Resetting budget")
            try:
                from app.services.proactive_monitor import proactive_monitor
                
                # Reset by creating a new day state
                proactive_monitor.budget._state = proactive_monitor.budget._new_day_state()
                proactive_monitor.budget._save_state()
                
                answer = "✅ Alert budget has been reset. You now have 5 message slots available for today."
                
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
                logger.error(f"Budget reset error: {e}", exc_info=True)
                answer = f"❌ Failed to reset budget: {str(e)}"
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
        
        # Handle memory_delete - delete/forget a memory
        if action == 'memory_delete':
            logger.info(f"[Stage 1] Deleting memory")
            try:
                memory_data = intent.get('memory_data', {}) or {}
                search_term = memory_data.get('content', '')
                
                if not search_term:
                    answer = "❌ Please specify which memory to delete."
                else:
                    memory_store = MemoryStore()
                    memories = memory_store.search_memories(search_term, limit=5)
                    
                    if memories:
                        # Delete the first matching memory
                        mem_to_delete = memories[0]
                        memory_store.delete_memory(mem_to_delete['id'])
                        answer = f"✅ Deleted memory: \"{mem_to_delete['content'][:100]}...\""
                    else:
                        answer = f"❌ No memory found matching: '{search_term}'"
                
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
                logger.error(f"Memory delete error: {e}", exc_info=True)
                answer = f"❌ Failed to delete memory: {str(e)}"
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
        
        # Check if user is correcting Friday (based on previous exchange)
        # We check if the CURRENT message is correcting the PREVIOUS Friday response
        if history and len(history) >= 2:
            last_friday_response = None
            for msg in reversed(history):
                if msg.get('role') == 'assistant':
                    last_friday_response = msg.get('content', '')
                    break
            
            if last_friday_response:
                # Quick check first (cheap), then LLM analysis if needed
                if correction_detector.quick_check(message):
                    def check_correction_async():
                        try:
                            analysis = correction_detector.analyze(last_friday_response, message)
                            if analysis.is_correction and analysis.confidence > 0.7:
                                if analysis.needs_clarification:
                                    # TODO: Could inject clarification into next response
                                    logger.info(f"Correction detected but needs clarification: {analysis.clarification_question}")
                                else:
                                    # Record the correction
                                    conversation_memory.add_correction(
                                        topic=analysis.topic or "general",
                                        user_message=message,
                                        friday_response=last_friday_response[:500],
                                        what_was_wrong=analysis.what_was_wrong or "Unknown",
                                        correct_answer=analysis.correct_answer or message,
                                        lesson_learned=f"Remember: {analysis.correct_answer}" if analysis.correct_answer else None,
                                    )
                                    logger.info(f"Recorded correction: {analysis.topic}")
                        except Exception as e:
                            logger.error(f"Error in correction detection: {e}")
                    
                    # Run in background to not slow down response
                    thread = threading.Thread(target=check_correction_async, daemon=True)
                    thread.start()
        
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
        
        # Track interaction for relationship state
        try:
            # Detect mood from message
            mood = relationship_tracker.detect_mood(message)
            
            # Determine sentiment (simple heuristic, could be enhanced)
            sentiment = "neutral"
            if mood.value in ["happy", "energetic"]:
                sentiment = "positive"
            elif mood.value in ["frustrated", "sad", "stressed"]:
                sentiment = "negative"
            
            # Record the interaction
            relationship_tracker.record_interaction(
                message=message,
                sentiment=sentiment,
                topic_category=action,
                user_initiated=True,
            )
        except Exception as e:
            logger.error(f"Error tracking interaction: {e}")
        
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
