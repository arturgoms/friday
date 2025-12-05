"""Post-chat processing for automatic memory and task extraction."""
import asyncio
from typing import List, Dict, Any
from pathlib import Path
import re
from datetime import datetime, timedelta
from app.core.logging import logger
from app.core.config import settings


class PostChatProcessor:
    """Processes conversations for automatic memory and task extraction."""
    
    def __init__(self):
        self._vector_store = None
        self._memory_extractor = None
        self._task_manager = None
        self._alert_store = None
        self._llm_service = None
    
    @property
    def alert_store(self):
        """Lazy load alert store."""
        if self._alert_store is None:
            from app.services.alert_store import alert_store
            self._alert_store = alert_store
        return self._alert_store
    
    @property
    def llm_service(self):
        """Lazy load LLM service."""
        if self._llm_service is None:
            from app.services.llm import llm_service
            self._llm_service = llm_service
        return self._llm_service
    
    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            from app.services.vector_store import vector_store
            self._vector_store = vector_store
        return self._vector_store
    
    @property
    def memory_extractor(self):
        """Lazy load memory extractor."""
        if self._memory_extractor is None:
            from app.services.memory_extractor import memory_extractor
            self._memory_extractor = memory_extractor
        return self._memory_extractor
    
    @property
    def task_manager(self):
        """Lazy load task manager."""
        if self._task_manager is None:
            from app.services.task_manager import task_manager
            self._task_manager = task_manager
        return self._task_manager
    
    def _is_internal_or_system_message(self, message: str) -> bool:
        """Check if a message looks like an internal/system prompt (e.g., from OpenWebUI)."""
        if not message:
            return True
        
        internal_patterns = [
            "generate 1-3 broad tags",
            "suggest 3-5 relevant follow-up",
            "categorizing the main themes",
            "### task:",
            "high-level domains",
            "as a **user**",
            "based on the chat history",
            "help continue or deepen the discussion",
        ]
        
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in internal_patterns)
    
    async def process_conversation(
        self,
        user_message: str,
        assistant_response: str,
        conversation_history: List[Dict],
        save_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Process a conversation turn for automatic extraction.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            conversation_history: Recent conversation context
            save_memory: Whether to automatically save memories
            
        Returns:
            Dict with extraction results
        """
        results = {
            "memories_extracted": 0,
            "memories_saved": 0,
            "tasks_extracted": 0,
            "tasks_created": 0,
            "alerts_created": 0,
        }
        
        # Skip processing for internal/system messages (e.g., OpenWebUI tag generation)
        if self._is_internal_or_system_message(user_message):
            logger.debug(f"Skipping post-processing for internal message: {user_message[:50]}...")
            return results
        
        try:
            # Extract memories
            if save_memory:
                memory_results = await self._extract_and_save_memories(
                    user_message,
                    assistant_response,
                    conversation_history
                )
                results.update(memory_results)
            
            # Extract tasks
            task_results = await self._extract_and_create_tasks(
                user_message,
                assistant_response
            )
            results.update(task_results)
            
            # Extract potential alerts (proactive opportunities)
            alert_results = await self._extract_and_create_alerts(
                user_message,
                assistant_response,
                conversation_history
            )
            results.update(alert_results)
            
        except Exception as e:
            logger.error(f"Error in post-chat processing: {e}")
        
        return results
    
    async def _extract_and_save_memories(
        self,
        user_message: str,
        assistant_response: str,
        conversation_history: List[Dict]
    ) -> Dict[str, int]:
        """Extract and save memories from conversation."""
        results = {"memories_extracted": 0, "memories_saved": 0}
        
        try:
            # Extract memories
            extractions = await self.memory_extractor.extract_from_conversation(
                user_message,
                assistant_response,
                conversation_history
            )
            
            results["memories_extracted"] = len(extractions)
            
            # Save high-confidence extractions
            for extraction in extractions:
                if self.memory_extractor.should_save_extraction(extraction):
                    await self._save_memory(extraction)
                    results["memories_saved"] += 1
            
            if results["memories_saved"] > 0:
                logger.info(f"Auto-saved {results['memories_saved']} memories from conversation")
        
        except Exception as e:
            logger.error(f"Error extracting/saving memories: {e}")
        
        return results
    
    async def _save_memory(self, extraction: Any):
        """Save extracted memory as Obsidian note."""
        try:
            note_data = self.memory_extractor.format_as_obsidian_note(extraction)
            
            # Create the file
            memory_path = Path("/home/artur/friday/data/memory")
            memory_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now(settings.user_timezone).strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\s-]', '', note_data["title"])[:50]
            filename = f"{safe_title}_{timestamp}.md"
            filepath = memory_path / filename
            
            # Write file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(note_data["content"])
            
            # Index in vector store (if method exists)
            if hasattr(self.vector_store, 'index_memory_file'):
                await asyncio.to_thread(
                    self.vector_store.index_memory_file,
                    str(filepath)
                )
            
            logger.info(f"Auto-saved memory: {filepath}")
        
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    async def _extract_and_create_tasks(
        self,
        user_message: str,
        assistant_response: str
    ) -> Dict[str, int]:
        """Extract and create tasks from conversation."""
        results = {"tasks_extracted": 0, "tasks_created": 0}
        
        try:
            # Look for task indicators in user message
            task_indicators = [
                r"(?:i need to|i have to|i should|i must|remind me to|todo:|task:)\s+(.+?)(?:\.|$|by|before)",
                r"(?:finish|complete|work on|start)\s+(.+?)(?:\s+(?:by|before|until)\s+(.+?))?(?:\.|$)",
            ]
            
            tasks = []
            for pattern in task_indicators:
                matches = re.finditer(pattern, user_message.lower(), re.IGNORECASE)
                for match in matches:
                    task_title = match.group(1).strip()
                    due_text = match.group(2) if len(match.groups()) > 1 else None
                    
                    if task_title and len(task_title) > 3:
                        tasks.append({
                            "title": task_title,
                            "due_text": due_text
                        })
            
            results["tasks_extracted"] = len(tasks)
            
            # Create tasks
            for task_data in tasks:
                task = self._create_task_from_extraction(task_data)
                if task:
                    results["tasks_created"] += 1
            
            if results["tasks_created"] > 0:
                logger.info(f"Auto-created {results['tasks_created']} tasks from conversation")
        
        except Exception as e:
            logger.error(f"Error extracting/creating tasks: {e}")
        
        return results
    
    def _create_task_from_extraction(self, task_data: Dict) -> Any:
        """Create a task from extracted data."""
        try:
            from app.services.task_manager import TaskPriority
            
            # Parse due date if present
            due_date = None
            if task_data.get("due_text"):
                due_date = self._parse_due_date(task_data["due_text"])
            
            # Infer priority from keywords
            priority = TaskPriority.MEDIUM
            title_lower = task_data["title"].lower()
            if any(word in title_lower for word in ["urgent", "asap", "immediately"]):
                priority = TaskPriority.URGENT
            elif any(word in title_lower for word in ["important", "critical"]):
                priority = TaskPriority.HIGH
            
            # Create task
            task = self.task_manager.create_task(
                title=task_data["title"].capitalize(),
                priority=priority,
                due_date=due_date,
                tags=["auto-extracted"]
            )
            
            return task
        
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None
    
    def _parse_due_date(self, due_text: str) -> datetime:
        """Parse due date from natural language."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        due_text_lower = due_text.lower().strip()
        
        # Common patterns
        if "today" in due_text_lower:
            return now.replace(hour=23, minute=59)
        elif "tomorrow" in due_text_lower:
            return (now + timedelta(days=1)).replace(hour=23, minute=59)
        elif "this week" in due_text_lower or "end of week" in due_text_lower:
            days_until_sunday = 6 - now.weekday()
            return (now + timedelta(days=days_until_sunday)).replace(hour=23, minute=59)
        elif "next week" in due_text_lower:
            days_until_next_sunday = 13 - now.weekday()
            return (now + timedelta(days=days_until_next_sunday)).replace(hour=23, minute=59)
        elif "friday" in due_text_lower:
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0 and now.hour > 17:  # After 5 PM Friday
                days_until_friday = 7
            return (now + timedelta(days=days_until_friday)).replace(hour=23, minute=59)
        
        # Try to parse specific dates
        try:
            from app.services.date_tools import date_tools
            date_str = date_tools.parse_date_from_text(due_text)
            return datetime.strptime(date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, tzinfo=user_tz
            )
        except:
            pass
        
        # Default: 1 week from now
        return now + timedelta(days=7)
    
    async def _extract_and_create_alerts(
        self,
        user_message: str,
        assistant_response: str,
        conversation_history: List[Dict]
    ) -> Dict[str, int]:
        """
        Extract proactive alert opportunities from conversation.
        
        Uses LLM to identify things Friday should proactively monitor or remind about.
        """
        results = {"alerts_created": 0}
        
        try:
            # Build conversation context
            recent_context = ""
            for msg in conversation_history[-4:]:  # Last 2 exchanges
                role = msg.get("role", "")
                content = msg.get("content", "")
                recent_context += f"{role}: {content}\n"
            
            recent_context += f"user: {user_message}\nassistant: {assistant_response}"
            
            # Ask LLM to identify proactive opportunities
            extraction_prompt = """Analyze this conversation and identify if Friday (the AI assistant) should create any proactive alerts or reminders.

Look for:
1. **Upcoming dates/events** mentioned (appointments, birthdays, deadlines)
2. **Health concerns** the user mentioned (stress, tiredness, pain)
3. **Important people** mentioned who Friday should remember
4. **Commitments** the user made (meetings, calls, tasks)
5. **Patterns to watch** (user mentioned wanting to improve something)

Respond with a JSON array. Each alert should have:
- "type": "date_reminder" | "health_watch" | "follow_up" | "birthday" | "deadline"
- "title": Short title for the alert
- "description": What to alert about and why
- "trigger_date": ISO date string if date-specific, or null
- "recurring": "daily" | "weekly" | null
- "priority": "low" | "medium" | "high"
- "reason": Why this alert would help the user

If no alerts are needed, return an empty array: []

Only create alerts for SIGNIFICANT things. Don't create alerts for:
- Casual mentions or hypotheticals
- Things already handled as reminders
- Trivial conversation topics

CONVERSATION:
{context}

Respond ONLY with valid JSON array:"""

            response = self.llm_service.call(
                system_prompt="You extract proactive alert opportunities from conversations. Respond only with valid JSON.",
                user_content=extraction_prompt.format(context=recent_context),
                history=[],
                stream=False
            )
            
            # Parse response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            import json
            alerts_data = json.loads(response.strip())
            
            if not isinstance(alerts_data, list):
                alerts_data = []
            
            # Create alerts
            from app.services.alert_store import AlertType
            
            type_map = {
                "date_reminder": AlertType.DATE_REMINDER,
                "health_watch": AlertType.HEALTH_WATCH,
                "follow_up": AlertType.FOLLOW_UP,
                "birthday": AlertType.BIRTHDAY,
                "deadline": AlertType.DEADLINE,
                "recurring": AlertType.RECURRING,
                "condition": AlertType.CONDITION,
            }
            
            for alert_data in alerts_data[:3]:  # Max 3 alerts per conversation
                try:
                    alert_type = type_map.get(
                        alert_data.get("type", "follow_up"),
                        AlertType.FOLLOW_UP
                    )
                    
                    trigger_date = None
                    if alert_data.get("trigger_date"):
                        try:
                            trigger_date = datetime.fromisoformat(
                                alert_data["trigger_date"].replace("Z", "+00:00")
                            )
                        except:
                            # Try to parse natural language date
                            trigger_date = self._parse_due_date(alert_data["trigger_date"])
                    
                    self.alert_store.create_alert(
                        title=alert_data.get("title", "Proactive Alert"),
                        description=alert_data.get("description", ""),
                        alert_type=alert_type,
                        trigger_date=trigger_date,
                        recurring_pattern=alert_data.get("recurring"),
                        priority=alert_data.get("priority", "medium"),
                        source_context=f"Extracted from conversation:\n\nUser: {user_message}\n\nReason: {alert_data.get('reason', 'Proactive monitoring')}",
                    )
                    
                    results["alerts_created"] += 1
                    logger.info(f"Created proactive alert: {alert_data.get('title')}")
                    
                except Exception as e:
                    logger.error(f"Error creating alert: {e}")
                    continue
            
            if results["alerts_created"] > 0:
                logger.info(f"Auto-created {results['alerts_created']} proactive alerts from conversation")
        
        except json.JSONDecodeError as e:
            logger.debug(f"No valid alert JSON extracted: {e}")
        except Exception as e:
            logger.error(f"Error extracting alerts: {e}")
        
        return results


# Singleton instance
post_chat_processor = PostChatProcessor()
