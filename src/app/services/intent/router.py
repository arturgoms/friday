"""Intent Router - Stage 1 LLM that determines what to do with user query."""
import json
from typing import Dict, Any
from app.services.llm import llm_service
from app.core.logging import logger


class IntentRouter:
    """Routes user queries to appropriate actions and data sources."""
    
    def __init__(self):
        """Initialize intent router."""
        self.system_prompt = """You are an intent classification assistant. Analyze the user's query and determine what actions/data are needed.

Your job is to output a JSON object with the following structure:
{
    "action": "web_search" | "health_query" | "time_query" | "calendar_query" | "reminder_query" | "reminder_create" | "reminder_delete" | "general",
    "use_rag": true/false,
    "use_memory": true/false,
    "tool": "current_time" | "calendar_today" | "calendar_tomorrow" | "calendar_week" | "calendar_next" | "reminder_list" | "reminder_next" | null,
    "reminder_data": {"message": "...", "time_spec": "..."} | null,
    "reminder_index": null | int
}

IMPORTANT: For vague follow-up questions like "what about yesterday's?" or "and today?", look for context clues:
- If asking about time periods (yesterday/today/tomorrow) AND no other context, assume it's continuing the previous topic
- "yesterday's workout" = health_query, NOT calendar
- "tomorrow's calendar" = calendar_query
- When in doubt about vague queries, use "general" action

RULES:

1. **web_search**: Use when asking about current events, news, facts not in personal notes
   - Examples: "what's the weather?", "who won the game?", "when is stranger things releasing?"
   - Set use_rag=false, use_memory=false

2. **health_query**: Use when asking about workouts, runs, sleep, fitness, Garmin data, daily health
   - Examples: "when was my last run?", "how did I sleep?", "latest pilates session?", "daily health data", "health summary", "yesterday's workout"
   - Keywords: health, workout, run, sleep, pilates, fitness, activity, Garmin, yesterday's (workout context), today's (health context)
   - Set use_rag=false, use_memory=false

3. **time_query**: Use when asking "what time is it" or "current time"
   - Set tool="current_time"
   - Set use_rag=false, use_memory=false

4. **calendar_query**: Use when asking about calendar/events/schedule
   - Examples: "what's on my calendar?", "do I have meetings today?"
   - Set tool="calendar_today" | "calendar_tomorrow" | "calendar_week" | "calendar_next"
   - Set use_rag=false, use_memory=false

5. **reminder_query**: Use when asking about existing reminders
   - Examples: "do I have reminders?", "what are my reminders?", "next reminder?"
   - Set tool="reminder_list" or "reminder_next"
   - Set use_rag=false, use_memory=false

6. **reminder_create**: Use when user asks to be reminded of something
   - Examples: "remind me to call mom in 30 minutes", "set reminder for 3pm"
   - Extract message and time specification to reminder_data
   - Set use_rag=false, use_memory=false

7. **reminder_delete**: Use when user wants to delete/remove/cancel reminders
   - Examples: "delete reminder 3", "cancel the second reminder", "remove first reminder", "delete all reminders"
   - Extract the reminder number/index to reminder_index (1-based, convert to 0-based)
   - For "delete all", set reminder_index to -999 (special value meaning "all")
   - Set use_rag=false, use_memory=false

8. **general**: Use for everything else (greetings, questions about notes, personal info)
   - Set use_rag=true, use_memory=true

Examples:

USER: "when is stranger things season 5 coming out?"
OUTPUT: {"action": "web_search", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null}

USER: "when was my latest pilates session?"
OUTPUT: {"action": "health_query", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null}

USER: "can you tell me my daily health data for today?"
OUTPUT: {"action": "health_query", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null}

USER: "what about yesterday's?" (after health question)
OUTPUT: {"action": "health_query", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null}

USER: "what time is it?"
OUTPUT: {"action": "time_query", "use_rag": false, "use_memory": false, "tool": "current_time", "reminder_data": null}

USER: "what's on my calendar today?"
OUTPUT: {"action": "calendar_query", "use_rag": false, "use_memory": false, "tool": "calendar_today", "reminder_data": null}

USER: "do I have any reminders?"
OUTPUT: {"action": "reminder_query", "use_rag": false, "use_memory": false, "tool": "reminder_list", "reminder_data": null}

USER: "remind me to take out trash in 30 minutes"
OUTPUT: {"action": "reminder_create", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": {"message": "take out trash", "time_spec": "30 minutes"}, "reminder_index": null}

USER: "delete reminder 2"
OUTPUT: {"action": "reminder_delete", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null, "reminder_index": 1}

USER: "cancel the first reminder"
OUTPUT: {"action": "reminder_delete", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null, "reminder_index": 0}

USER: "delete all reminders"
OUTPUT: {"action": "reminder_delete", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null, "reminder_index": -999}

USER: "what did I write about machine learning?"
OUTPUT: {"action": "general", "use_rag": true, "use_memory": true, "tool": null, "reminder_data": null, "reminder_index": null}

USER: "hello"
OUTPUT: {"action": "general", "use_rag": false, "use_memory": false, "tool": null, "reminder_data": null, "reminder_index": null}

Respond ONLY with valid JSON. No explanations."""
    
    def route(self, message: str, last_message: str = "") -> Dict[str, Any]:
        """
        Route user message to appropriate action.
        
        Args:
            message: Current user message
            last_message: Previous user message for context (optional)
        
        Returns:
            Dict with keys:
                - action: str
                - use_rag: bool
                - use_memory: bool
                - tool: str | None
                - reminder_data: dict | None
        """
        response = ""
        try:
            # Add context from previous message if available
            if last_message:
                user_content = f"PREVIOUS: {last_message}\nCURRENT: {message}\nOUTPUT:"
            else:
                user_content = f"USER: {message}\nOUTPUT:"
            
            # Call LLM for intent classification
            response = llm_service.call(
                system_prompt=self.system_prompt,
                user_content=user_content,
                history=[],
                stream=False
            )
            
            # Parse JSON response
            response = response.strip()
            
            # Sometimes LLM adds markdown code blocks, strip them
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            intent = json.loads(response.strip())
            
            logger.info(f"Intent routing: {message[:50]}... => {intent['action']} (tool={intent.get('tool')})")
            
            return intent
            
        except json.JSONDecodeError as e:
            logger.error(f"Intent routing JSON parse error: {e}, response was: {response[:200] if response else 'empty'}")
            # Fallback to general action
            return {
                "action": "general",
                "use_rag": True,
                "use_memory": True,
                "tool": None,
                "reminder_data": None
            }
        except Exception as e:
            logger.error(f"Intent routing error: {e}")
            # Fallback to general action
            return {
                "action": "general",
                "use_rag": True,
                "use_memory": True,
                "tool": None,
                "reminder_data": None
            }


# Singleton
intent_router = IntentRouter()
