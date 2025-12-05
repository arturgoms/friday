"""Web search intent handler."""
from app.core.logging import logger
from app.services.chat.handlers.base import IntentHandler, ChatContext, ChatResponse
from app.services.web_search import web_search_service
from app.services.llm import llm_service
from app.core.config import settings
from datetime import datetime


class WebSearchHandler(IntentHandler):
    """Handle web_search intent - search the web and synthesize results."""
    
    actions = ['web_search']
    
    def handle(self, context: ChatContext) -> ChatResponse:
        """Search the web and use LLM to synthesize results."""
        try:
            # Perform web search
            logger.info(f"[WebSearchHandler] Searching web for: {context.message[:50]}...")
            search_results = web_search_service.search(context.message)
            
            if not search_results:
                return ChatResponse(
                    session_id=context.session_id,
                    message=context.message,
                    answer="I couldn't find any relevant web results for that query.",
                    used_web=True,
                    is_final=True,
                )
            
            # Generate system prompt for web search
            system_prompt = self._generate_system_prompt()
            
            # Build user content with search results
            user_content = f"User question:\n{context.message}\n\nWeb search results:\n{search_results}"
            
            # Call LLM to synthesize
            answer = llm_service.call(
                system_prompt=system_prompt,
                user_content=user_content,
                history=context.history,
                stream=False,
            )
            
            return ChatResponse(
                session_id=context.session_id,
                message=context.message,
                answer=answer,
                used_web=True,
                is_final=True,
            )
            
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return self._error_response(context, f"Failed to search the web: {str(e)}")
    
    def _generate_system_prompt(self) -> str:
        """Generate system prompt for web search synthesis."""
        user_tz = settings.user_timezone
        now = datetime.now(user_tz)
        today = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        
        return (
            f"Today is {today}, {current_time}.\n\n"
            f"You are Friday, a personal AI assistant for Artur Gomes ({settings.authorized_user}).\n\n"
            "Use the web search results provided to answer the user's question. "
            "Be direct, concise, and cite information from the results. "
            "Use Markdown formatting: *bold*, `code`, bullets."
        )
