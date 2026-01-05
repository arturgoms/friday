"""
Friday Core Agent

Main AI agent using pydantic-ai with local LLM configuration.
"""

import asyncio
import sys
import zoneinfo
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import logfire
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

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
            f"You are Friday, the personal assistant of {user_name}.\n"
            f"Today is {today}. The user's timezone is {timezone}.\n"
            "Use available tools to answer questions.\n\n"
            "**EXECUTION PROTOCOL:**\n"
            "1. **Internal Discovery**: If a tool requires a specific argument that you do not have, "
            "you MUST first attempt to find that information using other available tools.\n"
            "2. **External Input**: You should only ask the user for information if it is impossible "
            "to retrieve it using your tools.\n"
            "3. **Strict Sequencing**: Do not call a tool until you have successfully obtained its "
            "required arguments from a previous step.\n"
            "4. **No Guessing**: Never invent or hallucinate parameter values.\n"
            "5. **Be Concise**: Keep responses brief and to the point unless detail is requested."
        )

    return Agent(
        model, model_settings={"temperature": temperature}, system_prompt=system_prompt
    )


# ==========================================
# DEFAULT AGENT INSTANCE
# ==========================================

# Create default agent instance for convenience
agent = create_agent()


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
