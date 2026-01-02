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
import threading
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
    days_until_date,
    days_between_dates,
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
from src.tools.memory import (
    get_conversation_history,
    get_last_user_message,
    summarize_conversation,
)
from src.tools.knowledge import (
    save_fact,
    get_fact,
    search_facts,
    search_knowledge,
    list_fact_categories,
)

logger = logging.getLogger(__name__)

# Thread-local storage for current session context
_session_context = threading.local()


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
            # Memory (conversation history)
            get_conversation_history,
            get_last_user_message,
            summarize_conversation,
            # Knowledge (personal facts)
            save_fact,
            get_fact,
            search_facts,
            search_knowledge,
            list_fact_categories,
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
            days_until_date,
            days_between_dates,
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
- Conversation memory (search past messages, get last message, summarize conversations)
- Personal knowledge (save and retrieve facts about the user - preferences, personal info, etc.)
- Calendar management (Google Calendar read-only, Nextcloud CalDAV read-write)
- Health data from Garmin (via InfluxDB) - running, sleep, HRV, recovery
- Obsidian vault for notes and knowledge management
- Weather information for Curitiba
- System monitoring (homelab, services, resources)
- Web search and news retrieval
- Daily briefing generation
- Image generation (create images from text descriptions)
- Speech synthesis (convert text to voice audio in English or Portuguese)

IMPORTANT MEMORY PATTERNS:

1. **Conversation History** - NOT automatically loaded. If user asks about past messages:
   - "What did I say about X?" → call get_conversation_history(query="X")
   - "What was my last message?" → call get_last_user_message()

2. **Personal Facts** - Store and retrieve long-term information about the user:
   - When user tells you personal info → call save_fact(topic, value, category)
   - When you need to know something about user → call get_fact(topic) or search_knowledge(query)
   - If you don't know something → call search_knowledge(query) FIRST, then ask user if not found
   
3. **Auto-save Facts** - Automatically save when user shares personal information:
   - "My favorite color is blue" → save_fact("favorite_color", "blue", "preferences")
   - "I was born in June" → save_fact("birth_month", "June", "personal")
   - "My wife is Sarah" → save_fact("wife_name", "Sarah", "family")
   - "I support Cruzeiro" → save_fact("favorite_soccer_team", "Cruzeiro Esporte Clube", "hobbies")
   
4. **Fact Updates** - When user updates information, save the new value (we keep history):
   - User says "Actually, I prefer red now" → save_fact("favorite_color", "red", "preferences")
   - get_fact() always returns the LATEST value

5. **Resolving Personal References** - CRITICAL PATTERN for "my X" queries:
   STEP 1: Retrieve the personal information from facts
   STEP 2: Use that information to complete the actual request
   
   Examples:
   - "When is my team playing?" 
     → FIRST: search_knowledge(query="team") → finds "Cruzeiro Esporte Clube"
     → THEN: web_search(query="Cruzeiro Esporte Clube next match") → finds match schedule
   
   - "What's my favorite restaurant address?"
     → FIRST: get_fact(topic="favorite_restaurant") → finds "Restaurante ABC"
     → THEN: web_search(query="Restaurante ABC address") → finds address
   
   - "Schedule meeting with my wife"
     → FIRST: get_fact(topic="wife_name") → finds "Sarah"
     → THEN: add_event(title="Meeting with Sarah", ...) → creates event
   
   - NEVER assume or guess personal information - ALWAYS retrieve from facts first, THEN act on it

6. **Choosing the Right Tool for Information**:
   - For REAL-TIME/CURRENT information (weather, news, match schedules, scores, etc.) → use web_search()
   - For PERSONAL notes/knowledge → use vault_read_note() or search_knowledge()
   - For FACTUAL information about the user → use get_fact() or search_facts()
   - For DATE CALCULATIONS (days until, time between dates) → ALWAYS use days_until_date() or days_between_dates(), NEVER calculate manually
   
   CRITICAL: DO NOT calculate date math yourself - you WILL get it wrong. ALWAYS use date tools:
   - "How many days until X?" → days_until_date()
   - "What's the difference between X and Y?" → days_between_dates()
   IMPORTANT: When parsing dates like "12/12", the format is MM/DD (month/day), so 12/12 = December 12th
   
   Examples:
   - "When is Cruzeiro's next match?" → web_search (real-time sports schedule)
   - "What was the last match score?" → web_search (recent sports result)
   - "What's the weather?" → get_current_weather (real-time weather data)
   - "What did I write about work?" → vault_read_note (personal notes)
   - "How many days until my birthday?" → get_fact("birthday") THEN days_until_date(month=12, day=15)

CRITICAL: When the user requests an action that requires a tool, you MUST call the tool using function calling.
DO NOT describe what the tool would do or show JSON examples - ACTUALLY CALL THE TOOL.
NEVER return JSON in markdown blocks - use native function calling instead.

Examples:
- User: "generate an image of a sunset" → CALL generate_image() tool
- User: "what's the weather" → CALL get_current_weather() tool
- User: "what's the weather and my next meeting?" → CALL get_current_weather() AND get_next_event() tools
- User: "what did I say about weather yesterday?" → CALL get_conversation_history(query="weather")
- User: "what was my last message?" → CALL get_last_user_message()
- User: "My favorite color is blue" → CALL save_fact(topic="favorite_color", value="blue", category="preferences") then acknowledge
- User: "What's my favorite color?" → CALL search_knowledge(query="favorite color") OR get_fact(topic="favorite_color")
- User: "Tell me about my family" → CALL search_facts(query="family") OR search_knowledge(query="family")
- User: "When is my team playing?" → FIRST call search_knowledge(query="team"), THEN (after getting team name) call web_search(query="[team_name] next match")
- User: "What's the score of my team's last game?" → FIRST call search_knowledge(query="team"), THEN call web_search(query="[team_name] latest result")
- User: "When is my wife's birthday? How many days left?" → FIRST call get_fact(topic="wife_birthday") which returns "12/12", THEN call days_until_date(month=12, day=12) [parse MM/DD format]
- User: "What's the difference between my birthday and my wife's birthday?" → FIRST call get_fact(topic="birthday") and get_fact(topic="wife_birthday"), THEN call days_between_dates(month1=3, day1=30, month2=12, day2=12)
- User: "convert this to speech: hello" → CALL generate_speech(text="hello", lang="en")
- User asks in Portuguese or wants Portuguese audio → use lang="pt"

When multiple pieces of information are requested, call ALL necessary tools in one response.
Always use the appropriate tool when the user asks for information or actions.

MULTI-STEP QUERIES: For queries requiring personal info lookup + action:
- Make the FIRST tool call to retrieve personal info
- After getting the result, make a SECOND tool call with the retrieved information
- Do NOT stop after just retrieving the fact - complete the full user request
- EXAMPLE: "how many days until X?" → get_fact → parse the date from result → days_until_date(month, day)

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
        
        # Store session_id in thread-local storage so memory tools can access it
        _session_context.session_id = session_id
        
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
        
        # Conversation history is now a TOOL, not loaded into context
        # This prevents history from interfering with function calling
        # The model can access history via get_conversation_history() tool when needed
        messages_history = []
        
        # DISABLED: Old history loading approach
        if False:
            try:
                conversations = self.npc.command_history.get_conversations_by_id(session_id)
                # Convert to OpenAI message format and limit to most recent messages
                all_messages = []
                for conv in conversations:
                    content = conv.get("content", "")
                    role = conv.get("role", "user")
                    
                    # FILTER STRATEGY: Only keep truly conversational messages
                    # Skip both tool results AND tool-request questions
                    
                    # Skip user messages that are clearly tool requests (contain "what", "show", "get", etc.)
                    if role == "user":
                        tool_request_indicators = [
                            "what's the", "what is the", "show me", "get ",
                            "check ", "how was my", "do i have", "will it"
                        ]
                        if any(indicator in content.lower() for indicator in tool_request_indicators):
                            logger.info(f"[AGENT] Filtered tool-request user message from history")
                            continue
                    
                    # Skip assistant messages that look like tool results or tool calls
                    if role == "assistant":
                        # Skip if contains tool call XML
                        if "<tool_call>" in content or "```json" in content:
                            logger.info(f"[AGENT] Filtered tool call XML/JSON from history")
                            continue
                        
                        # Skip if contains tool result patterns
                        skip_patterns = [
                            "Weather in ", "Your sleep", "Your next", "========",
                            "get_current_weather:", "get_next_event:", "get_sleep_summary:",
                            "The weather", "The disk usage", "currently", "temperature"
                        ]
                        if any(pattern in content for pattern in skip_patterns):
                            logger.info(f"[AGENT] Filtered tool result from history")
                            continue
                    
                    all_messages.append({
                        "role": role,
                        "content": content
                    })
                
                # Keep only the most recent messages
                if len(all_messages) > MAX_HISTORY_MESSAGES:
                    messages_history = all_messages[-MAX_HISTORY_MESSAGES:]
                    logger.info(f"[AGENT] Loaded {len(messages_history)} messages from history (limited from {len(all_messages)}, with filtering)")
                else:
                    messages_history = all_messages
                    if messages_history:
                        logger.info(f"[AGENT] Loaded {len(messages_history)} messages from history (with filtering)")
            except Exception as e:
                logger.warning(f"[AGENT] Failed to load conversation history: {e}")

        
        # DEBUG: Log history content to understand what breaks tool calling
        if messages_history:
            logger.info(f"[AGENT] DEBUG: Sending {len(messages_history)} history messages:")
            for i, msg in enumerate(messages_history):
                content_preview = msg['content'][:100] if msg['content'] else ''
                logger.info(f"[AGENT] DEBUG:   [{i}] {msg['role']}: {content_preview}...")
        
        try:
            # Multi-turn tool calling: Keep calling LLM until it stops making tool calls
            # This enables multi-step reasoning like "get team from facts, then search web"
            max_turns = 3  # Prevent infinite loops
            turn = 0
            accumulated_tool_results = []
            response = None
            
            current_message = message
            turn_messages = messages_history.copy()
            
            while turn < max_turns:
                turn += 1
                logger.info(f"[AGENT] Tool calling turn {turn}/{max_turns}")
                
                # Call npcpy with conversation history
                logger.info("[AGENT] Calling NPC.get_llm_response()")
                response = self.npc.get_llm_response(
                    current_message,
                    messages=turn_messages,
                    auto_process_tool_calls=True,
                    tool_choice='auto',  # Enable automatic tool selection
                    parallel_tool_calls=True,  # Re-enabled - need to handle vLLM parser issues
                )
                
                # Check if any tools were called
                tool_calls = response.get('tool_calls', [])
                tool_results = response.get('tool_results', [])
                
                # Log tool calls and results
                if tool_calls:
                    logger.info(f"[AGENT] Turn {turn} - {len(tool_calls)} tool(s) called:")
                    for tc in tool_calls:
                        # Extract tool name from different formats
                        if isinstance(tc, dict):
                            tc_name = tc.get('function', {}).get('name', 'unknown')
                        elif hasattr(tc, 'function') and hasattr(tc.function, 'name'):
                            tc_name = tc.function.name
                        else:
                            tc_name = 'unknown'
                        logger.info(f"[AGENT]   → {tc_name}")
                
                if tool_results:
                    logger.info(f"[AGENT] Turn {turn} - {len(tool_results)} tool result(s):")
                    for tr in tool_results:
                        tool_name = tr.get('tool_name', 'unknown')
                        result_preview = str(tr.get('result', ''))[:150]
                        if len(str(tr.get('result', ''))) > 150:
                            result_preview += '...'
                        logger.info(f"[AGENT]   ← {tool_name}: {result_preview}")
                    accumulated_tool_results.extend(tool_results)
                
                # If no tool calls, we're done
                if not tool_calls:
                    logger.info(f"[AGENT] No more tool calls after turn {turn}, finishing")
                    break
                
                # Check if we should continue or stop
                # "Lookup" tools that retrieve info that needs to be used for another action
                # Most tools should allow one more turn for the model to process results
                terminal_only_tools = {
                    'save_fact', 'add_event', 'update_event', 'delete_event',  # Write operations
                    'generate_image', 'generate_speech',  # Generation complete
                }
                
                # Check if ALL tool calls were terminal-only
                all_terminal = True
                for tc in tool_calls:
                    tc_name = tc.get('function', {}).get('name') if isinstance(tc, dict) else getattr(tc.function, 'name', '') if hasattr(tc, 'function') else ''
                    if tc_name not in terminal_only_tools:
                        all_terminal = False
                        break
                
                # If ALL tool calls were terminal-only, stop here
                if all_terminal:
                    logger.info(f"[AGENT] Turn {turn} made {len(tool_calls)} terminal-only tool calls, finishing")
                    break
                
                # Otherwise, continue to let model process results
                logger.info(f"[AGENT] Turn {turn} made {len(tool_calls)} tool calls (at least one requires processing), continuing...")
                
                # Add this turn's exchange to the message history for next turn
                # Add assistant's tool call message
                turn_messages.append({
                    "role": "assistant",
                    "content": response.get('response', ''),
                })
                
                # Add tool results as a system/tool message
                if tool_results:
                    results_text = "\n".join([f"{tr.get('tool_name', 'tool')}: {tr.get('result', '')}" for tr in tool_results])
                    turn_messages.append({
                        "role": "user",  # npcpy expects tool results as user messages
                        "content": f"Tool results from previous call:\n{results_text}\n\nNow continue with the user's original request: {message}"
                    })
                
                # Set current_message for next iteration
                # Remind the model of the original request
                current_message = f"Based on the tool results above, please answer the user's original question: '{message}'"
            
            # Ensure we have a response
            if response is None:
                raise RuntimeError("No response generated after tool calling loop")
                
            # Update accumulated tool results
            if accumulated_tool_results:
                response['tool_results'] = accumulated_tool_results
            
            logger.info(f"[AGENT] Completed after {turn} turns with {len(accumulated_tool_results)} total tool calls")
            
            # Log final summary of all tools called
            if accumulated_tool_results:
                logger.info("[AGENT] === Tool Execution Summary ===")
                for i, tr in enumerate(accumulated_tool_results, 1):
                    tool_name = tr.get('tool_name', 'unknown')
                    args = tr.get('arguments', {})
                    result_preview = str(tr.get('result', ''))[:100]
                    if len(str(tr.get('result', ''))) > 100:
                        result_preview += '...'
                    logger.info(f"[AGENT] {i}. {tool_name}({args})")
                    logger.info(f"[AGENT]    → {result_preview}")
                logger.info("[AGENT] ===================================")
            
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
            
            # DEBUG: Log what the model actually returned
            if not tool_calls:
                logger.info(f"[AGENT] DEBUG: No tool_calls in response. Response text: {response_text[:300]}")
            
            # FALLBACK: If model described a tool call but didn't actually call it,
            # parse the JSON/XML and execute the tool manually
            # NOTE: This should rarely happen - indicates model isn't using function calling properly
            # Support both JSON markdown and Hermes XML format
            if not tool_calls and ('```json' in response_text or '<tool_call>' in response_text):
                import re
                import json
                
                logger.warning("[AGENT] FALLBACK: Model returned JSON/XML instead of function calls - this indicates improper function calling behavior")
                logger.info("[AGENT] Attempting to parse tool call from response text")
                
                tool_results = []
                
                # Check for Hermes XML format first
                if '<tool_call>' in response_text:
                    logger.info("[AGENT] Detected Hermes XML tool call format")
                    # Extract JSON from inside <tool_call> tags
                    # Also handle malformed closing tag (<tool_call> instead of </tool_call>)
                    xml_match = re.search(r'<tool_call>\s*(.+?)\s*(?:</tool_call>|<tool_call>)', response_text, re.DOTALL)
                    if xml_match:
                        logger.info(f"[AGENT] Extracted tool call content: {xml_match.group(1)[:100]}...")
                        json_content = xml_match.group(1).strip()
                        # Split by newlines to get individual JSON objects
                        json_lines = [line.strip() for line in json_content.split('\n') if line.strip()]
                        for json_line in json_lines:
                            try:
                                tool_desc = json.loads(json_line)
                                tool_name = tool_desc.get('name')
                                tool_args = tool_desc.get('arguments', {})
                                
                                if tool_name:
                                    logger.info(f"[AGENT] Manually executing tool from XML: {tool_name} with args: {tool_args}")
                                    
                                    # Find and execute the tool
                                    tool_func = None
                                    for tool in self.tools:
                                        if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                                            tool_func = tool
                                            break
                                    
                                    if tool_func:
                                        try:
                                            tool_result = tool_func(**tool_args)
                                            tool_results.append(f"{tool_name}: {tool_result}")
                                            logger.info(f"[AGENT] Tool executed successfully: {tool_name}")
                                        except Exception as e:
                                            logger.error(f"[AGENT] Tool execution failed: {tool_name}: {e}")
                                            tool_results.append(f"{tool_name}: Error - {str(e)}")
                                    else:
                                        logger.warning(f"[AGENT] Tool not found: {tool_name}. Available tools: {[t.__name__ for t in self.tools if hasattr(t, '__name__')][:10]}")
                            except Exception as e:
                                logger.error(f"[AGENT] Failed to parse/execute tool from XML: {e}")
                
                # Also check for JSON markdown blocks
                json_blocks = re.findall(r'```json\s*({[^`]+})\s*```', response_text, re.DOTALL)
                
                for json_block in json_blocks:
                    try:
                        tool_desc = json.loads(json_block)
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
                                    voice_val = tool_args.pop('voice', 'default')
                                    if voice_val not in ['male', 'female', 'default']:
                                        tool_args['lang'] = voice_val
                                    elif 'lang' not in tool_args:
                                        tool_args['lang'] = 'en'
                                
                                tool_result = tool_func(**tool_args)
                                tool_results.append(f"{tool_name}: {tool_result}")
                                logger.info(f"[AGENT] Tool executed successfully: {tool_name}")
                            else:
                                logger.warning(f"[AGENT] Tool not found: {tool_name}")
                    except Exception as e:
                        logger.error(f"[AGENT] Failed to parse/execute tool from JSON: {e}")
                
                # Combine all tool results
                if tool_results:
                    response_text = "\n\n".join(tool_results)
                    mode = 'tool'
            
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
