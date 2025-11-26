"""LLM service."""
from typing import List, Optional, Dict
from openai import OpenAI
from fastapi import HTTPException
from app.core.config import settings
from app.core.logging import logger


class LLMService:
    """Service for LLM interactions."""
    
    def __init__(self):
        """Initialize LLM client."""
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key="not-needed",
        )
        logger.info(f"LLM client initialized: {settings.llm_base_url}")
    
    def call(
        self,
        system_prompt: str,
        user_content: str,
        history: Optional[List[Dict]] = None,
        stream: bool = False,
    ):
        """Call LLM with optional conversation history."""
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": user_content})
        
        try:
            resp = self.client.chat.completions.create(
                model=settings.llm_model_name,
                messages=messages,
                temperature=settings.llm_temperature,
                stream=stream,
            )
            
            if stream:
                return resp
            else:
                return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"LLM service unavailable: {str(e)}"
            )
    
    def health_check(self) -> str:
        """Check LLM service health."""
        try:
            self.client.models.list()
            return "healthy"
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return f"unhealthy: {str(e)}"


# Singleton instance
llm_service = LLMService()
