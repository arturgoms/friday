"""
Friday 3.0 Agent - npcpy-based implementation with ChromaDB RAG

This module replaces the old agent.py and llm.py with a modern
npcpy-based implementation that provides:
- Native function calling via litellm
- Built-in conversation history (SQLite-backed)
- Automatic tool execution
- ChromaDB RAG integration for context retrieval
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from npcpy.npc_compiler import NPC
from sqlalchemy import create_engine

from src.core.config import get_config
from src.core.constants import BRT
from src.core.vector_store import get_vector_store

# Import all tools
from src.tools.calendar import (
    get_calendar_events,
    get_today_schedule,
    add_calendar_event,
    find_free_time,
    get_next_event,
    delete_calendar_event,
)
from src.tools.daily_briefing import (
    get_morning_report,
    get_evening_report,
)
from src.tools.health import (
    get_recent_runs,
    get_training_load,
    get_vo2max,
    get_sleep_summary,
    get_recovery_status,
    get_hrv_trend,
    get_weekly_health,
    get_stress_levels,
    get_heart_rate_summary,
    get_activity_summary,
    get_garmin_sync_status,
)
from src.tools.vault import (
    vault_read_note,
    vault_write_note,
    vault_list_directory,
    vault_search_notes,
    vault_get_frontmatter,
    vault_update_frontmatter,
    vault_manage_tags,
    vault_create_daily_note,
    vault_rename_note,
    vault_move_note,
    vault_delete_note,
)
from src.tools.weather import (
    get_current_weather,
    get_weather_forecast,
    will_it_rain,
)
from src.tools.system import (
    get_disk_usage,
    get_current_time,
    get_system_info,
    get_uptime,
    get_memory_usage,
    get_friday_logs,
    get_homelab_status,
    get_friday_status,
)
from src.tools.web import (
    web_search,
    web_fetch,
    web_news,
)
from src.tools.media import (
    generate_image,
    generate_speech,
)

logger = logging.getLogger(__name__)


class FridayAgent:
    """Friday agent powered by npcpy with ChromaDB RAG."""
    
    def __init__(self):
        """Initialize the Friday agent."""
        config = get_config()
        
        # Set environment for litellm (via npcpy)
        os.environ['OPENAI_API_KEY'] = os.getenv('FRIDAY_API_KEY', 'not-needed')
        os.environ['OPENAI_API_BASE'] = config.llm.base_url
        
        logger.info("[AGENT] Initializing Friday agent with npcpy")
        
        # Initialize RAG
        try:
            self.vector_store = get_vector_store()
            logger.info("[AGENT] ChromaDB vector store initialized")
        except Exception as e:
            logger.warning(f"[AGENT] Failed to initialize vector store: {e}")
            self.vector_store = None
        
        # Collect all tools
        self.tools = [
            # Calendar
            get_calendar_events,
            get_today_schedule,
            add_calendar_event,
            find_free_time,
            get_next_event,
            delete_calendar_event,
            # Daily Briefing
            get_morning_report,
            get_evening_report,
            # Health
            get_recent_runs,
            get_training_load,
            get_vo2max,
            get_sleep_summary,
            get_recovery_status,
            get_hrv_trend,
            get_weekly_health,
            get_stress_levels,
            get_heart_rate_summary,
            get_activity_summary,
            get_garmin_sync_status,
            # Vault
            vault_read_note,
            vault_write_note,
            vault_list_directory,
            vault_search_notes,
            vault_get_frontmatter,
            vault_update_frontmatter,
            vault_manage_tags,
            vault_create_daily_note,
            vault_rename_note,
            vault_move_note,
            vault_delete_note,
            # Weather
            get_current_weather,
            get_weather_forecast,
            will_it_rain,
            # System
            get_disk_usage,
            get_current_time,
            get_system_info,
            get_uptime,
            get_memory_usage,
            get_friday_logs,
            get_homelab_status,
            get_friday_status,
            # Web
            web_search,
            web_fetch,
            web_news,
            # Media
            generate_image,
            generate_speech,
        ]
        
        logger.info(f"[AGENT] Loaded {len(self.tools)} tools")
        
        # Create database engine for conversation history
        self.db_path = os.path.expanduser("~/friday_history.db")
        db_engine = create_engine(f"sqlite:///{self.db_path}")
        
        logger.info(f"[AGENT] Conversation history will be stored in: {self.db_path}")
        
        # Create NPC with database connection (enables automatic memory)
        try:
            self.npc = NPC(
                name='Friday',
                primary_directive=self._build_base_system_prompt(),
                model=f'openai/{config.llm.model_name}',
                provider='openai',
                tools=self.tools,
                db_conn=db_engine,
                use_global_jinxs=False,
            )
            
            # Configure memory
            self.npc.memory_length = 50  # Keep last 50 messages
            self.npc.memory_strategy = 'recent'
            
            logger.info(
                f"[AGENT] NPC initialized with model: {config.llm.model_name}, "
                f"memory: {self.npc.memory_length} messages"
            )
        except Exception as e:
            logger.error(f"[AGENT] Failed to initialize NPC: {e}")
            raise
    
    def _build_base_system_prompt(self) -> str:
        """Build the base system prompt (without RAG context)."""
        now = datetime.now(BRT)
        
        return f"""You are Friday, an AI assistant running on a local Ubuntu server with an RTX 3090.

Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}
Timezone: America/Sao_Paulo (BRT, UTC-3)

You have access to tools for:
- Calendar management (Google Calendar read-only, Nextcloud CalDAV read-write)
- Health data from Garmin (via InfluxDB) - running, sleep, HRV, recovery
- Obsidian vault for notes and knowledge management
- Weather information for Curitiba
- System monitoring (homelab, services, resources)
- Web search and news retrieval
- Daily briefing generation
- Image generation (create images from text descriptions)
- Speech synthesis (convert text to voice audio in English or Portuguese)

CRITICAL: When the user requests an action that requires a tool, you MUST call the tool using function calling.
DO NOT describe what the tool would do or show JSON examples - ACTUALLY CALL THE TOOL.

Examples:
- User: "generate an image of a sunset" -> CALL generate_image() tool, don't describe it
- User: "what's the weather" -> CALL get_current_weather() tool
- User: "convert this to speech: hello" -> CALL generate_speech(text="hello", lang="en")
- User: "say in Portuguese: olá" -> CALL generate_speech(text="olá", lang="pt")
- User asks in Portuguese or wants Portuguese audio -> use lang="pt"

Always use the appropriate tool when the user asks for information or actions.
Be concise, helpful, and proactive. You know the user well - Artur, a runner and developer.

Important guidelines:
- When showing calendar events, format them clearly with times
- For health metrics, provide context and trends when relevant
- Always use BRT timezone for time-based queries
- Be direct and avoid unnecessary pleasantries

When displaying information from vault notes or RAG results:
- Present the text content naturally and clearly
- Do NOT wrap responses in JSON or structured formats
- Just show the relevant text from the note
- If multiple sections are relevant, separate them with clear headings"""
    
    def _get_rag_context(self, query: str, top_k: int = 5) -> str:
        """Retrieve relevant context from vector store.
        
        Args:
            query: User's query
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string or empty string if no results
        """
        if self.vector_store is None:
            return ""
        
        try:
            results = self.vector_store.search(query, top_k=top_k)
            
            if not results:
                return ""
            
            # Format context
            context_parts = []
            for result in results:
                source = result.get('metadata', {}).get('source', 'unknown')
                text = result['text']
                score = result.get('score', 0)
                
                # Only include high-quality matches (>0.5 similarity)
                if score > 0.5:
                    context_parts.append(f"[{source}]\n{text}")
            
            if context_parts:
                logger.info(f"[AGENT] RAG: Found {len(context_parts)} relevant chunks")
                return "\n\n---\n\n".join(context_parts)
            
            return ""
        except Exception as e:
            logger.warning(f"[AGENT] RAG search failed: {e}")
            return ""
    
    def chat(
        self,
        message: str,
        session_id: str = "default",
        user_id: str = "default",
        enable_rag: bool = True
    ) -> dict:
        """Process a user message and return response.
        
        Args:
            message: User's message
            session_id: Session identifier (maps to conversation_id in DB)
            user_id: User identifier
            enable_rag: Whether to use RAG context (default: True)
            
        Returns:
            Dict with 'text', 'tool_calls', 'tool_results', 'mode' keys
        """
        logger.info(f"[AGENT] Processing message from session: {session_id}")
        
        # Build system prompt with optional RAG context
        base_prompt = self._build_base_system_prompt()
        
        if enable_rag:
            rag_context = self._get_rag_context(message)
            if rag_context:
                enhanced_prompt = f"""{base_prompt}

## Relevant Context from Knowledge Base

{rag_context}

Use this context to inform your responses when relevant."""
                logger.info("[AGENT] RAG context added to system prompt")
            else:
                enhanced_prompt = base_prompt
        else:
            enhanced_prompt = base_prompt
        
        # Update NPC directive
        self.npc.primary_directive = enhanced_prompt
        
        # Load conversation history from database
        messages_history = []
        if self.npc.command_history:
            try:
                conversations = self.npc.command_history.get_conversations_by_id(session_id)
                # Convert to OpenAI message format
                for conv in conversations:
                    messages_history.append({
                        "role": conv.get("role", "user"),
                        "content": conv.get("content", "")
                    })
                if messages_history:
                    logger.info(f"[AGENT] Loaded {len(messages_history)} messages from history")
            except Exception as e:
                logger.warning(f"[AGENT] Failed to load conversation history: {e}")
        
        try:
            # Call npcpy with conversation history
            logger.info("[AGENT] Calling NPC.get_llm_response()")
            response = self.npc.get_llm_response(
                message,
                messages=messages_history,
                auto_process_tool_calls=True,
            )
            
            # Store conversation in CommandHistory with session_id
            if self.npc.command_history:
                import uuid
                from datetime import datetime
                
                # User message
                self.npc.command_history.add_conversation(
                    message_id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    role='user',
                    content=message,
                    conversation_id=session_id,
                    directory_path=os.getcwd(),
                    model=self.npc.model,
                    provider=self.npc.provider,
                    npc=self.npc.name,
                )
                # Assistant response
                self.npc.command_history.add_conversation(
                    message_id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    role='assistant',
                    content=response.get('response', ''),
                    conversation_id=session_id,
                    directory_path=os.getcwd(),
                    model=self.npc.model,
                    provider=self.npc.provider,
                    npc=self.npc.name,
                )
            
            tool_calls = response.get('tool_calls', [])
            mode = 'tool' if tool_calls else 'chat'
            response_text = response.get('response', '')
            
            # FALLBACK: If model described a tool call but didn't actually call it,
            # parse the JSON and execute the tool manually
            if not tool_calls and '```json' in response_text:
                import re
                import json
                
                logger.info("[AGENT] Attempting to parse tool call from response text")
                
                # Extract JSON block
                json_match = re.search(r'```json\s*({[^`]+})\s*```', response_text, re.DOTALL)
                if json_match:
                    try:
                        tool_desc = json.loads(json_match.group(1))
                        tool_name = tool_desc.get('name')
                        tool_args = tool_desc.get('arguments', {})
                        
                        if tool_name:
                            logger.info(f"[AGENT] Manually executing tool: {tool_name}")
                            
                            # Find and execute the tool
                            tool_func = None
                            for tool in self.tools:
                                if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                                    tool_func = tool
                                    break
                            
                            if tool_func:
                                # SPECIAL CASE: Map old 'voice' parameter to 'lang' for generate_speech
                                if tool_name == 'generate_speech' and 'voice' in tool_args:
                                    # Infer language from voice or default to 'pt' if not English
                                    voice_val = tool_args.pop('voice', 'default')
                                    # If voice isn't "male/female/default", treat it as language
                                    if voice_val not in ['male', 'female', 'default']:
                                        tool_args['lang'] = voice_val
                                    elif 'lang' not in tool_args:
                                        tool_args['lang'] = 'en'  # Default to English
                                
                                tool_result = tool_func(**tool_args)
                                response_text = tool_result
                                mode = 'tool'
                                logger.info(f"[AGENT] Tool executed successfully: {tool_name}")
                            else:
                                logger.warning(f"[AGENT] Tool not found: {tool_name}")
                    except Exception as e:
                        logger.error(f"[AGENT] Failed to parse/execute tool from JSON: {e}")
            
            # AUTO-CONVERT to audio if user explicitly asks for audio response
            import re
            audio_request_pattern = r'\b(respond|answer|reply|say|tell me)\s+(with|in|as|using)?\s*(audio|voice|speech)\b'
            if re.search(audio_request_pattern, message, re.IGNORECASE):
                if '[AUDIO:' not in response_text and '[IMAGE:' not in response_text:
                    logger.info("[AGENT] User requested audio response - converting text to speech")
                    # Find generate_speech tool
                    for tool in self.tools:
                        if hasattr(tool, '__name__') and tool.__name__ == 'generate_speech':
                            # Clean response text for speech (remove markdown, code blocks, etc)
                            clean_text = re.sub(r'```[^`]*```', '', response_text)  # Remove code blocks
                            clean_text = re.sub(r'\[.*?\]\(.*?\)', '', clean_text)  # Remove markdown links
                            clean_text = re.sub(r'[#*_`]', '', clean_text)  # Remove markdown formatting
                            clean_text = clean_text.strip()
                            
                            if clean_text and len(clean_text) < 500:  # Only for reasonable length
                                try:
                                    audio_result = tool(clean_text[:500])  # Limit to 500 chars
                                    response_text = audio_result
                                    mode = 'tool'
                                    logger.info("[AGENT] Auto-converted response to audio")
                                except Exception as e:
                                    logger.error(f"[AGENT] Failed to auto-convert to audio: {e}")
                            break
            
            logger.info(
                f"[AGENT] Response generated - mode: {mode}, "
                f"tools called: {len(tool_calls)}"
            )
            
            return {
                'text': response_text,
                'tool_calls': tool_calls,
                'tool_results': response.get('tool_results', []),
                'mode': mode,
            }
        except Exception as e:
            logger.error(f"[AGENT] Error during chat: {e}", exc_info=True)
            return {
                'text': f"I encountered an error processing your request: {str(e)}",
                'tool_calls': [],
                'tool_results': [],
                'mode': 'error',
            }
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session.
        
        Args:
            session_id: Session identifier to clear
        """
        logger.info(f"[AGENT] Clearing conversation history for session: {session_id}")
        # npcpy loads from DB, so we just reset memory
        if self.npc.memory:
            self.npc.memory = []
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dicts with 'role', 'content', 'timestamp'
        """
        if self.npc.command_history:
            try:
                conversations = self.npc.command_history.get_conversations_by_id(session_id)
                return [
                    {
                        'role': msg['role'],
                        'content': msg['content'],
                        'timestamp': msg['timestamp']
                    }
                    for msg in conversations
                ]
            except Exception as e:
                logger.error(f"[AGENT] Error retrieving conversation history: {e}")
                return []
        return []


# =============================================================================
# Global Instance
# =============================================================================

_agent: Optional[FridayAgent] = None


def get_agent() -> FridayAgent:
    """Get the global Friday agent instance.
    
    Returns:
        FridayAgent instance
    """
    global _agent
    if _agent is None:
        _agent = FridayAgent()
    return _agent
