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


class ChatService:
    """Two-stage chat service: Intent routing -> Response generation."""
    
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
    
    def fetch_health_context(self, message: str) -> str:
        """Fetch Garmin health/activity data."""
        if not self.health_coach:
            return ""
        
        try:
            message_lower = message.lower()
            context_parts = []
            
            # Check if this is a comprehensive daily summary request
            is_daily_summary = any(phrase in message_lower for phrase in [
                'daily health', 'health data', 'health summary', 'daily summary',
                'today\'s health', 'health digest', 'full health'
            ])
            
            # Sleep data
            if is_daily_summary or any(word in message_lower for word in ['sleep', 'slept', 'rest']):
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
                        f"- Resting HR: {sleep['resting_hr']} bpm"
                    )
            
            # Running summary (only show if specifically asking about running stats)
            if not is_daily_summary and any(word in message_lower for word in ['run', 'running']):
                summary = self.health_coach.get_running_summary(days=30)
                if "run_count" in summary:
                    context_parts.append(
                        f"### Running Stats (Last 30 Days)\n"
                        f"- Runs: {summary['run_count']}\n"
                        f"- Total Distance: {summary['total_distance_km']} km\n"
                        f"- Average Pace: {summary['avg_pace_min_km']} min/km\n"
                        f"- Average Heart Rate: {summary['avg_heart_rate']} bpm"
                    )
            
            # Recent activities (always fetch for daily summary or specific activity queries)
            if is_daily_summary or any(word in message_lower for word in ['recent', 'last', 'latest', 'yesterday', 'today', 'activity', 'activities']):
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
                    
                    acts = acts[:5]  # Limit to 5 most recent
                    act_list = []
                    for act in acts:
                        if act['distance_km'] > 0:
                            act_list.append(
                                f"- {act['date']}: {act['name']} - {act['distance_km']}km, "
                                f"{act['duration_min']}min, {act['pace_min_km']} min/km"
                            )
                        else:
                            act_list.append(f"- {act['date']}: {act['name']} ({act['type']}) - {act['duration_min']}min")
                    
                    if act_list:
                        context_parts.append(
                            f"### Recent Activities\n" + "\n".join(act_list)
                        )
            
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
            obsidian_ctx, obsidian_chunks = vector_store.query_obsidian(message)
            if obsidian_ctx:
                context_parts.append("### From your notes\n" + obsidian_ctx)
                used_rag = True
        
        # Memory
        if use_memory:
            memory_ctx, memory_items = vector_store.query_memory(message)
            if memory_ctx:
                context_parts.append("### From your memory\n" + memory_ctx)
        
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
        
        base = f"You are Friday, {settings.authorized_user}'s assistant. Today is {today}."
        
        if action == "web_search":
            return (
                f"{base}\n\n"
                "Use the web search results provided to answer the user's question. "
                "Be direct, concise, and cite information from the results. "
                "Use Markdown formatting: *bold*, `code`, bullets."
            )
        
        elif action == "health_query":
            # Check if this is a daily summary request
            if any(phrase in message.lower() for phrase in ['daily health', 'health data', 'health summary', 'daily summary']):
                return (
                    f"{base}\n\n"
                    "You are a health coach. Analyze the Garmin health data provided and create a comprehensive daily summary:\n"
                    "1. Summarize key metrics (sleep, activities, heart rate)\n"
                    "2. Provide actionable insights and recommendations\n"
                    "3. Highlight any concerns or notable patterns\n"
                    "4. Be encouraging and specific\n"
                    "Use Markdown formatting: *bold*, `code`, bullets."
                )
            else:
                return (
                    f"{base}\n\n"
                    "Answer the user's question using ONLY the Garmin health/activity data provided. "
                    "Be direct and concise. Use Markdown formatting: *bold*, `code`, bullets."
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
        
        intent = intent_router.route(message, last_message=last_user_msg)
        action = intent['action']
        tool = intent.get('tool')
        reminder_data = intent.get('reminder_data')
        reminder_index = intent.get('reminder_index')
        
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
                        post_chat_processor.process_conversation(message, answer)
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
