"""
Friday Tools Module

All tools use @agent.tool_plain decorator and are automatically
registered with the agent when imported.

To use tools, import them individually:
    from src.tools.web import web_search
    from src.tools.weather import get_current_weather
"""

__all__ = [
    "calendar",
    "daily_briefing",
    "health",
    "media",
    "memory",
    "people",
    "system",
    "vault",
    "weather",
    "web",
]
