"""
Friday Core Agent

Main AI agent using pydantic-ai with local LLM configuration.
"""

import asyncio
import logging
import sys
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
            "- System: Monitor disk, CPU, memory, Friday services\n"
            "- Sensors: Check external services, homelab hardware stats\n"
            "- Memory: Access conversation history\n"
            "- People: Contact information\n"
            "- Vault: Search Obsidian notes (contains user's personal knowledge, preferences, and information)\n"
            "- Web: Search the internet\n"
            "- Media: Control media playback\n"
            "- Time: Get current time in any timezone\n\n"
            
            "**WHEN TO USE TOOLS:**\n"
            "- Use tools ONLY when you need specific data or to perform an action\n"
            "- For simple conversation (greetings, questions, chat), respond naturally WITHOUT tools\n"
            "- Examples that DON'T need tools: 'hi', 'thanks', 'how are you'\n"
            "- Examples that DO need tools: 'what's the weather', 'check my calendar', 'what's my favorite color'\n"
            "- For questions about user preferences/info: Use vault_search_notes to search their knowledge base\n\n"
            
            "**GUIDELINES:**\n"
            "1. **Be Natural**: Respond conversationally when appropriate\n"
            "2. **Use Tools Wisely**: Only call tools when you actually need information or to take action\n"
            "3. **Search Knowledge First**: For personal info/preferences, search the vault before saying you don't know\n"
            "4. **Ask When Unclear**: If you're unsure what the user wants, ask for clarification\n"
            "5. **Be Concise**: Keep responses brief unless detail is requested"
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
agent = create_agent()


# ==========================================
# REGISTER TOOLS
# ==========================================

# Import all tools to register them with the agent
# Tools use @agent.tool_plain decorator and auto-register on import
try:
    from src.tools import calendar
    from src.tools import daily_briefing
    from src.tools import health
    # from src.tools import knowledge  # TODO: Needs vault integration update
    from src.tools import media
    from src.tools import memory
    from src.tools import people
    from src.tools import sensors
    from src.tools import system
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
