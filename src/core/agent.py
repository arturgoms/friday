"""
Friday Core Agent

Main AI agent using pydantic-ai with local LLM configuration.
"""

import asyncio
import functools
import logging
import sys
import uuid
import zoneinfo
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import logfire
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)

# Add parent directory to path to import settings
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings

# Configure logfire
logfire.configure()
logfire.instrument_pydantic_ai()


# ==========================================
# SETUP MODEL
# ==========================================


def create_provider() -> OpenAIProvider:
    """Create OpenAI provider with settings from config."""
    return OpenAIProvider(
        base_url=settings.LLM["base_url"],
        api_key="EMPTY",  # Local LLM doesn't need API key
    )


def create_model(provider: Optional[OpenAIProvider] = None) -> OpenAIChatModel:
    """Create OpenAI chat model with settings from config.

    Args:
        provider: Optional provider instance. Creates one if not provided.

    Returns:
        Configured OpenAIChatModel instance
    """
    if provider is None:
        provider = create_provider()

    return OpenAIChatModel(settings.LLM["model_name"], provider=provider)


# ==========================================
# DEFINE THE AGENT
# ==========================================


class AgentDeps:
    """Dependencies injected into agent tools."""
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id


def create_agent(
    model: Optional[OpenAIChatModel] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
) -> Agent:
    """Create Friday agent with configuration.

    Args:
        model: Optional model instance. Creates one if not provided.
        temperature: Optional temperature override. Uses settings default if not provided.
        system_prompt: Optional system prompt override. Uses default if not provided.

    Returns:
        Configured Agent instance
    """
    if model is None:
        model = create_model()

    if temperature is None:
        temperature = settings.LLM["temperature"]

    if system_prompt is None:
        today = date.today().strftime("%Y-%m-%d")
        user_name = settings.USER["name"]
        timezone = settings.USER["timezone"]

        system_prompt = (
            f"You are Friday, the personal AI assistant for {user_name}.\n"
            f"Today is {today}. User timezone: {timezone}.\n\n"
            
            "**YOUR CAPABILITIES:**\n"
            "You have access to tools when needed:\n"
            "- Calendar: View and manage events\n"
            "- Weather: Current conditions and forecasts\n"
            "- Health: Garmin fitness and sleep data\n"
            "- Investments: Portfolio tracking, operations history, dividends/earnings, tax reports (DARF/IRPF), performance analytics\n"
            "- System: Monitor disk, CPU, memory, Friday services\n"
            "- Sensors: Check external services, homelab hardware stats\n"
            "- Memory: Access conversation history\n"
            "- People: Contact information\n"
            "- Vault: Search Obsidian notes (contains user's personal knowledge, preferences, and information)\n"
            "- Web: Search the internet\n"
            "- Media: Control media playback, generate_speech for TTS (text-to-speech audio)\n"
            "- Time: Get current time in any timezone\n\n"
            
            "**WHEN TO USE TOOLS:**\n"
            "- Use tools ONLY when you need specific data or to perform an action\n"
            "- For simple conversation (greetings, questions, chat), respond naturally WITHOUT tools\n"
            "- Examples that DON'T need tools: 'hi', 'thanks', 'how are you'\n"
            "- Examples that DO need tools: 'what's the weather', 'check my calendar', 'answer with audio'\n"
            "- For questions about user preferences/info: Use vault_search_notes to search their knowledge base\n"
            "- When user asks for audio/voice response ONLY: Use generate_speech (don't use it for images)\n"
            "- When user asks for image: Use generate_image ONLY (don't also generate audio unless asked)\n\n"
            
            "**GUIDELINES:**\n"
            "1. **Be Natural**: Respond conversationally when appropriate\n"
            "2. **Use Tools Wisely**: Only call tools when you actually need information or to take action\n"
            "3. **One Tool Call Per Action**: Call each tool ONCE, then respond with the result - don't repeat calls\n"
            "4. **Search Knowledge First**: For personal info/preferences, search the vault before saying you don't know\n"
            "5. **Ask When Unclear**: If you're unsure what the user wants, ask for clarification\n"
            "6. **Be Concise**: Keep responses brief unless detail is requested\n"
            "7. **Stop After Success**: Once a tool succeeds, use its output and respond - don't call it again"
        )

    return Agent(
        model, 
        model_settings={"temperature": temperature}, 
        system_prompt=system_prompt,
        deps_type=AgentDeps
    )


# ==========================================
# DEFAULT AGENT INSTANCE
# ==========================================

# Create default agent instance for convenience
_base_agent = create_agent()


# ==========================================
# ENHANCED TOOL DECORATOR WITH AUTO-SNAPSHOT
# ==========================================

# Store the original decorator
_original_tool_plain = _base_agent.tool_plain


def enhanced_tool_plain(func):
    """Enhanced tool_plain decorator that auto-saves snapshots for data tool executions.
    
    Snapshots are saved for data/query tools (get_*, fetch_*, check_*, etc.).
    Snapshots are NOT saved for:
    - Report tools: Functions starting with 'report_'
    - Action tools: Functions with action prefixes (add_, create_, update_, delete_, send_, etc.)
    - Calculation tools: Functions starting with 'calc_' (ephemeral calculations)
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function with auto-snapshot capability
    """
    # Define action prefixes that indicate write/mutate operations
    ACTION_PREFIXES = ('add_', 'create_', 'update_', 'delete_', 'send_', 'remove_', 
                       'clear_', 'set_', 'save_', 'write_', 'edit_', 'insert_')
    
    # Check if this is a report, action, or calculation tool (skip snapshot saving)
    is_report = func.__name__.startswith('report_')
    is_action = func.__name__.startswith(ACTION_PREFIXES)
    is_calculation = func.__name__.startswith('calc_')
    
    # Create wrapper FIRST, then register with pydantic-ai
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        """Sync wrapper for snapshot saving."""
        result = func(*args, **kwargs)
        
        # Auto-save snapshot for data tools ONLY (skip reports, actions, and calculations)
        if not is_report and not is_action and not is_calculation:
            try:
                from src.awareness.store import InsightsStore
                from src.awareness.models import Snapshot
                
                # Convert result to dict if it's not already
                if isinstance(result, dict):
                    data = result
                else:
                    # Wrap non-dict results in a dict
                    data = {"result": result, "type": type(result).__name__}
                
                store = InsightsStore()
                snapshot = Snapshot(
                    id=str(uuid.uuid4()),
                    collector=func.__name__,
                    timestamp=datetime.now(settings.TIMEZONE),
                    data=data
                )
                store.save_snapshot(snapshot)
                logger.debug(f"[SNAPSHOT] Auto-saved snapshot for {func.__name__}")
            except Exception as e:
                # Don't break the tool if snapshot save fails
                logger.warning(f"[SNAPSHOT] Failed to save snapshot for {func.__name__}: {e}")
        
        return result
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        """Async wrapper for snapshot saving."""
        result = await func(*args, **kwargs)
        
        # Auto-save snapshot for data tools ONLY (skip reports, actions, and calculations)
        if not is_report and not is_action and not is_calculation:
            try:
                from src.awareness.store import InsightsStore
                from src.awareness.models import Snapshot
                
                # Convert result to dict if it's not already
                if isinstance(result, dict):
                    data = result
                else:
                    # Wrap non-dict results in a dict
                    data = {"result": result, "type": type(result).__name__}
                
                store = InsightsStore()
                snapshot = Snapshot(
                    id=str(uuid.uuid4()),
                    collector=func.__name__,
                    timestamp=datetime.now(settings.TIMEZONE),
                    data=data
                )
                store.save_snapshot(snapshot)
                logger.debug(f"[SNAPSHOT] Auto-saved snapshot for {func.__name__}")
            except Exception as e:
                # Don't break the tool if snapshot save fails
                logger.warning(f"[SNAPSHOT] Failed to save snapshot for {func.__name__}: {e}")
        
        return result
    
    # Choose the appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        wrapper = async_wrapper
    else:
        wrapper = sync_wrapper
    
    # NOW register the wrapper with pydantic-ai (not the original func)
    return _original_tool_plain(wrapper)


# Replace the agent's tool_plain with our enhanced version
_base_agent.tool_plain = enhanced_tool_plain
agent = _base_agent


# ==========================================
# REGISTER TOOLS
# ==========================================

# Import all tools to register them with the agent
# Tools use @agent.tool_plain decorator and auto-register on import
try:
    from src.tools import calendar
    from src.tools import daily_briefing
    from src.tools import health
    from src.tools import investments
    # Import specific journal tools (not generate_daily_note - that's scheduler-only)
    from src.tools.journal import create_daily_journal_thread
    # from src.tools import knowledge  # TODO: Needs vault integration update
    from src.tools import knowledge_indexer  # RAG indexing tools
    from src.tools import media
    from src.tools import memory
    from src.tools import people
    from src.tools import sensors
    from src.tools import system
    from src.tools import utils
    from src.tools import vault
    from src.tools import weather
    from src.tools import web
    logger.info("Tools loaded successfully")
except Exception as e:
    logger.warning(f"Error loading tools: {e}")


# ==========================================
# HELPER FUNCTIONS
# ==========================================


async def run_agent(prompt: str, agent_instance: Optional[Agent] = None) -> str:
    """Run the agent with a prompt.

    Args:
        prompt: User prompt/question
        agent_instance: Optional agent instance. Uses default if not provided.

    Returns:
        Agent response as string
    """
    if agent_instance is None:
        agent_instance = agent

    result = await agent_instance.run(prompt)
    return result.data


def run_agent_sync(prompt: str, agent_instance: Optional[Agent] = None) -> str:
    """Synchronous wrapper for run_agent.

    Args:
        prompt: User prompt/question
        agent_instance: Optional agent instance. Uses default if not provided.

    Returns:
        Agent response as string
    """
    return asyncio.run(run_agent(prompt, agent_instance))


async def run_with_context(
    user_message: str,
    message_history=None,
    deps=None,
    agent_instance: Optional[Agent] = None,
    enable_background: bool = True,
    enable_rag: bool = True
):
    """
    Run agent with automatic context injection (Auto-Context RAG).
    
    Injects two tiers of context:
    - Tier 1 (Background): User profile from Artur Gomes.md
    - Tier 2 (RAG): Semantic search results (conditional)
    
    Args:
        user_message: User's input message
        message_history: Optional message history for conversation context
        deps: Optional dependencies to inject into agent tools
        agent_instance: Optional agent instance. Uses default if not provided.
        enable_background: Whether to inject background context (default: True)
        enable_rag: Whether to enable RAG context (default: True)
        
    Returns:
        Agent run result (same as agent.run())
    """
    from src.core.context_engine import (
        should_retrieve_context,
        get_background_context,
        get_rag_context,
        build_enhanced_prompt
    )
    
    if agent_instance is None:
        agent_instance = agent
    
    # Get background context (Tier 1)
    background_context = None
    if enable_background:
        background_context = get_background_context()
        if background_context:
            logger.debug("Background context retrieved")
    
    # Get RAG context (Tier 2) if needed
    rag_context = None
    if enable_rag and should_retrieve_context(user_message):
        rag_context = get_rag_context(user_message)
        if rag_context:
            logger.debug("RAG context retrieved")
    
    # Build enhanced system prompt
    # Generate the default system prompt (same logic as create_agent)
    today = date.today().strftime("%Y-%m-%d")
    user_name = settings.USER["name"]
    timezone = settings.USER["timezone"]
    
    original_prompt = (
        f"You are Friday, the personal AI assistant for {user_name}.\n"
        f"Today is {today}. User timezone: {timezone}.\n\n"
        "**YOUR CAPABILITIES:**\n"
        "You have access to tools when needed:\n"
        "- Calendar: View and manage events\n"
        "- Weather: Current conditions and forecasts\n"
        "- Health: Garmin fitness and sleep data\n"
        "- Investments: Portfolio tracking, operations history, dividends/earnings, tax reports (DARF/IRPF), performance analytics\n"
        "- System: Monitor disk, CPU, memory, Friday services\n"
        "- Sensors: Check external services, homelab hardware stats\n"
        "- Memory: Access conversation history\n"
        "- People: Contact information\n"
        "- Vault: Search Obsidian notes (contains user's personal knowledge, preferences, and information)\n"
        "- Web: Search the internet\n"
        "- Media: Control media playback, generate_speech for TTS (text-to-speech audio)\n"
        "- Time: Get current time in any timezone\n\n"
        "**WHEN TO USE TOOLS:**\n"
        "- Use tools proactively when they would provide helpful, accurate information\n"
        "- Don't apologize for using tools - just use them naturally\n"
        "- You can call multiple tools if needed to answer comprehensively\n"
        "- For quick facts you know confidently, you can answer directly\n\n"
        "**COMMUNICATION STYLE:**\n"
        "- Be concise and direct\n"
        "- Use natural, conversational language\n"
        "- Show personality - be warm, helpful, and occasionally witty\n"
        "- Use emojis sparingly for emphasis (1-2 per message max)\n"
        "- Format responses with markdown when helpful (lists, bold, etc.)\n"
        "- For technical topics, be precise but accessible\n\n"
        "**IMPORTANT GUIDELINES:**\n"
        "- Always be honest - if you don't know something, say so\n"
        "- Respect privacy - only access data when relevant to the request\n"
        "- Be proactive - suggest related information or actions when helpful\n"
        "- Remember: You're a personal assistant, not just an information retrieval system\n"
        "- Focus on being genuinely useful, not just technically correct"
    )
    
    enhanced_prompt = build_enhanced_prompt(
        original_prompt,
        background_context,
        rag_context
    )
    
    # Create temporary agent with enhanced prompt
    enhanced_agent = create_agent(system_prompt=enhanced_prompt)
    
    # Run with enhanced context, passing through history and deps
    result = await enhanced_agent.run(user_message, message_history=message_history, deps=deps)
    return result


def run_with_context_sync(
    user_message: str,
    message_history=None,
    deps=None,
    agent_instance: Optional[Agent] = None,
    enable_background: bool = True,
    enable_rag: bool = True
):
    """
    Synchronous wrapper for run_with_context.
    
    Args:
        user_message: User's input message
        message_history: Optional message history for conversation context
        deps: Optional dependencies to inject into agent tools
        agent_instance: Optional agent instance. Uses default if not provided.
        enable_background: Whether to inject background context (default: True)
        enable_rag: Whether to enable RAG context (default: True)
        
    Returns:
        Agent run result (same as agent.run())
    """
    return asyncio.run(run_with_context(
        user_message,
        message_history=message_history,
        deps=deps,
        agent_instance=agent_instance,
        enable_background=enable_background,
        enable_rag=enable_rag
    ))


# ==========================================
# EXAMPLE USAGE
# ==========================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"User: {prompt}")
        print(f"Friday: {run_agent_sync(prompt)}")
    else:
        print("Friday Agent initialized successfully!")
        print(f"Model: {settings.LLM['model_name']}")
        print(f"Base URL: {settings.LLM['base_url']}")
        print(f"Temperature: {settings.LLM['temperature']}")
        print("\nUsage: python -m src.core.agent <your question>")
