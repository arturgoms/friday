"""Memory intent handlers - save, list, delete memories."""
import re
from typing import Dict, Any, List, Optional

from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.memory_store import MemoryStore


class MemorySaveHandler(IntentHandler):
    """Handle memory_save intent - store facts in memory."""
    
    actions = ['memory_save']
    
    def __init__(self):
        self._pending_memories: Dict[str, Dict[str, Any]] = {}
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Save a memory (fact) to the memory store."""
        memory_data = context.memory_data
        
        if not memory_data:
            return self._error_response(context, "No memory data provided")
        
        try:
            memory_store = MemoryStore()
            
            content = memory_data.get('content', '')
            tags = memory_data.get('tags', [])
            
            if not content:
                return self._error_response(context, "No content to remember")
            
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
                    f"  - \"{c['content'][:100]}...\"" if len(c['content']) > 100 else f"  - \"{c['content']}\""
                    for c in conflicts[:3]
                ])
                
                answer = (
                    f"I found existing memories that might conflict with \"{content}\":\n\n"
                    f"{conflict_list}\n\n"
                    f"Would you like me to:\n"
                    f"1. **Update** the existing memory (replace the old info)\n"
                    f"2. **Add anyway** (keep both memories)\n\n"
                    f"Reply with \"update\" or \"add anyway\""
                )
                
                # Store pending memory for follow-up handling
                # Note: This is stored in the handler instance, not session
                # The orchestrator should handle session-based pending state
                self._pending_memories[context.session_id] = {
                    "content": content,
                    "tags": tags,
                    "conflicts": conflicts
                }
                
                return ChatResponse(
                    session_id=context.session_id,
                    message=context.message,
                    answer=answer,
                    is_final=True,
                )
            
            answer = f"Got it! I'll remember: \"{content}\""
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                extracted_memory=content,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Memory save error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to save memory: {str(e)}")
    
    def _personalize_memory(self, content: str) -> str:
        """Replace first-person pronouns with the user's name for better searchability."""
        user_name = "Artur"  # Could be made configurable via settings
        
        # Replace patterns (case-insensitive)
        content = re.sub(r'\bmy\b', f"{user_name}'s", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI am\b', f"{user_name} is", content, flags=re.IGNORECASE)
        content = re.sub(r"\bI'm\b", f"{user_name} is", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI like\b', f"{user_name} likes", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI have\b', f"{user_name} has", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI use\b', f"{user_name} uses", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI work\b', f"{user_name} works", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI live\b', f"{user_name} lives", content, flags=re.IGNORECASE)
        content = re.sub(r'\bI\b', user_name, content)
        
        # Capitalize first letter
        if content:
            content = content[0].upper() + content[1:]
        
        return content
    
    def has_pending_memory(self, session_id: str) -> bool:
        """Check if there's a pending memory conflict for this session."""
        return session_id in self._pending_memories
    
    def resolve_conflict(self, session_id: str, action: str) -> Optional[ChatResponse]:
        """Resolve a pending memory conflict."""
        if session_id not in self._pending_memories:
            return None
        
        pending = self._pending_memories[session_id]
        memory_store = MemoryStore()
        
        if action == 'update':
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
            
            del self._pending_memories[session_id]
            
            return ChatResponse(
                session_id=session_id,
                message="",
                answer=f"Updated! Old memory replaced with: \"{pending['content']}\"",
                extracted_memory=pending['content'],
                is_final=True,
            )
        
        elif action == 'add':
            # Add anyway, keeping both
            memory_id, _ = memory_store.add_memory(
                content=pending['content'],
                label="explicit_memory",
                tags=pending['tags'],
                force=True
            )
            
            del self._pending_memories[session_id]
            
            return ChatResponse(
                session_id=session_id,
                message="",
                answer="Added! I now have both memories stored.",
                extracted_memory=pending['content'],
                is_final=True,
            )
        
        elif action == 'cancel':
            del self._pending_memories[session_id]
            
            return ChatResponse(
                session_id=session_id,
                message="",
                answer="OK, I won't save that memory.",
                is_final=True,
            )
        
        return None


class MemoryAmbiguousHandler(IntentHandler):
    """Handle memory_ambiguous intent - clarify if user wants reminder or memory."""
    
    actions = ['memory_ambiguous']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Ask for clarification when "remember to X" is ambiguous."""
        memory_data = context.memory_data
        content = memory_data.get('content', '') if memory_data else ''
        
        answer = (
            f"I'm not sure what you mean by \"remember to {content}\".\n\n"
            f"Did you want me to:\n"
            f"1. **Set a reminder** - I'll notify you at a specific time\n"
            f"   Say: \"Remind me to {content} in 30 minutes\" or \"at 3pm\"\n\n"
            f"2. **Save to memory** - I'll remember this fact for future conversations\n"
            f"   Say: \"Remember that I need to {content}\" or \"Save this: {content}\""
        )
        
        return ChatResponse(
            session_id=context.session_id,
            message=context.message,
            answer=answer,
            is_final=True,
        )


class MemoryListHandler(IntentHandler):
    """Handle memory_list intent - list stored memories."""
    
    actions = ['memory_list']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """List all stored memories."""
        try:
            memory_store = MemoryStore()
            memories = memory_store.list_memories(limit=15)
            
            if memories:
                result = "Your memories:\n\n"
                for mem in memories:
                    content_preview = mem['content'][:80] + "..." if len(mem['content']) > 80 else mem['content']
                    result += f"- {content_preview}\n"
                    result += f"  (ID: {mem['id']})\n\n"
                answer = result
            else:
                answer = "I haven't stored any memories yet."
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_memory=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Memory list error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to list memories: {str(e)}")


class MemoryDeleteHandler(IntentHandler):
    """Handle memory_delete intent - delete/forget memories."""
    
    actions = ['memory_delete']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Delete a memory by search term."""
        memory_data = context.memory_data
        search_term = memory_data.get('content', '') if memory_data else ''
        
        if not search_term:
            return self._error_response(context, "Please specify which memory to delete.")
        
        try:
            memory_store = MemoryStore()
            memories = memory_store.search_memories(search_term, limit=5)
            
            if memories:
                # Delete the first matching memory
                mem_to_delete = memories[0]
                memory_store.delete_memory(mem_to_delete['id'])
                content_preview = mem_to_delete['content'][:100]
                answer = f"Deleted memory: \"{content_preview}...\""
            else:
                answer = f"No memory found matching: '{search_term}'"
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Memory delete error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to delete memory: {str(e)}")
