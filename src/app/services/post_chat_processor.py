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
            "tasks_created": 0
        }
        
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


# Singleton instance
post_chat_processor = PostChatProcessor()
