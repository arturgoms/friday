"""
Friday Agent - Complete replacement for npcpy-based implementation.

Simple, transparent, and powerful multi-turn tool calling agent.
"""

import logging
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import json

from src.core.config import get_config
from src.core.constants import BRT
from src.core.llm_client import LLMClient
from src.core.conversation_history import ConversationHistory
from src.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class FridayAgent:
    """Friday AI agent with multi-turn tool calling."""
    
    def __init__(self, tools: List[Callable]):
        """Initialize Friday agent.
        
        Args:
            tools: List of tool functions decorated with @friday_tool
        """
        config = get_config()
        
        # Initialize LLM client
        self.llm = LLMClient(
            base_url=config.llm.base_url,
            model_name=config.llm.model_name,
            timeout=60.0
        )
        
        # Initialize conversation history
        history_db = os.path.expanduser("~/friday_history.db")
        self.history = ConversationHistory(history_db)
        
        # Initialize vector store for RAG
        try:
            self.vector_store = get_vector_store()
            logger.info("[AGENT] Vector store initialized")
        except Exception as e:
            logger.warning(f"[AGENT] Failed to initialize vector store: {e}")
            self.vector_store = None
        
        # Store tools
        self.tools = tools
        self.tool_map = {tool.__name__: tool for tool in tools}
        
        # Convert tools to OpenAI format
        self.tool_definitions = self._build_tool_definitions()
        
        logger.info(f"[AGENT] Initialized with {len(self.tools)} tools")
    
    def _build_tool_definitions(self) -> List[Dict]:
        """Build OpenAI-format tool definitions from Python functions.
        
        Returns:
            List of tool definition dicts
        """
        definitions = []
        
        for tool in self.tools:
            # Extract info from function
            name = tool.__name__
            description = tool.__doc__ or f"Tool: {name}"
            
            # Get function signature
            import inspect
            sig = inspect.signature(tool)
            
            # Build parameters schema
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                param_type = "string"  # Default
                param_desc = f"Parameter: {param_name}"
                
                # Try to infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                
                properties[param_name] = {
                    "type": param_type,
                    "description": param_desc
                }
                
                # Check if required (no default value)
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            definition = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description.strip(),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }
            
            definitions.append(definition)
        
        return definitions
    
    def _get_rag_context(self, query: str, top_k: int = 5) -> str:
        """Retrieve relevant context from vector store.
        
        Args:
            query: User's query
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string or empty string
        """
        if self.vector_store is None:
            return ""
        
        try:
            results = self.vector_store.search(query, top_k=top_k)
            
            if not results:
                return ""
            
            context_parts = []
            for result in results:
                source = result.get('metadata', {}).get('source', 'unknown')
                text = result['text']
                score = result.get('score', 0)
                
                if score > 0.5:
                    context_parts.append(f"[{source}]\n{text}")
            
            if context_parts:
                logger.info(f"[AGENT] RAG: Found {len(context_parts)} relevant chunks")
                return "\n\n---\n\n".join(context_parts)
            
            return ""
        except Exception as e:
            logger.warning(f"[AGENT] RAG search failed: {e}")
            return ""
    
    def _build_system_prompt(self, rag_context: str = "") -> str:
        """Build system prompt with optional RAG context.
        
        Args:
            rag_context: Optional RAG context to include
            
        Returns:
            System prompt string
        """
        now = datetime.now(BRT)
        
        base_prompt = f"""You are Friday, an AI assistant running on a local Ubuntu server with an RTX 3090.

Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}
Timezone: America/Sao_Paulo (BRT, UTC-3)

The user is Artur, a runner and developer.

Use <think>...</think> tags to plan your approach before calling tools. After receiving tool results, provide a clear answer to the user."""
        
        if rag_context:
            return f"""{base_prompt}

## Relevant Context from Knowledge Base

{rag_context}

Use this context to inform your responses when relevant."""
        
        return base_prompt
    
    async def chat(
        self,
        message: str,
        session_id: str = "default",
        enable_rag: bool = True,
        max_turns: int = 10
    ) -> Dict[str, Any]:
        """Process a user message with multi-turn tool calling.
        
        Args:
            message: User's message
            session_id: Session identifier
            enable_rag: Whether to use RAG context
            max_turns: Maximum tool calling turns
            
        Returns:
            Dict with 'text', 'tool_calls', 'tool_results' keys
        """
        logger.info(f"[AGENT] Processing message in session: {session_id}")
        
        # Build system prompt with optional RAG
        rag_context = self._get_rag_context(message) if enable_rag else ""
        system_prompt = self._build_system_prompt(rag_context)
        
        # Build messages list
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        # Multi-turn tool calling loop
        turn = 0
        all_tool_results = []
        final_message = None
        plan_text = None  # Track the plan from first response
        
        while turn < max_turns:
            # Call LLM
            try:
                response = await self.llm.chat_completion(
                    messages=messages,
                    tools=self.tool_definitions,
                    tool_choice="auto",
                    temperature=0.6,
                    max_tokens=2048  # Reduced from 4096 to prevent context overflow
                )
            except Exception as e:
                logger.error(f"[AGENT] LLM call failed: {e}")
                return {
                    'text': f"Error: {str(e)}",
                    'tool_calls': [],
                    'tool_results': [],
                    'mode': 'error'
                }
            
            # Extract message
            assistant_message = self.llm.extract_message(response)
            tool_calls = assistant_message.get("tool_calls", [])
            
            # On first turn, extract plan from content if present
            if turn == 0 and assistant_message.get("content"):
                import re
                thinking_pattern = r'<think>(.*?)</think>'
                matches = re.findall(thinking_pattern, assistant_message["content"], re.DOTALL)
                if matches:
                    plan_text = matches[0].strip()
                    logger.info(f"[AGENT] Plan extracted: {plan_text[:100]}...")
            
            # If no tool calls, we're done
            if not tool_calls:
                final_message = assistant_message
                break
            
            turn += 1
            logger.info(f"[AGENT] Turn {turn}/{max_turns}: {len(tool_calls)} tool(s) called")
            
            # Add assistant message to history
            messages.append(assistant_message)
            
            # Execute tools
            tool_messages = []
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                tool_id = tool_call["id"]
                
                logger.info(f"[AGENT]   → {tool_name}({tool_args})")
                
                # Execute tool
                try:
                    tool_func = self.tool_map.get(tool_name)
                    if not tool_func:
                        result = f"Error: Tool '{tool_name}' not found"
                    else:
                        result = tool_func(**tool_args)
                        if not isinstance(result, str):
                            result = json.dumps(result)
                except Exception as e:
                    logger.error(f"[AGENT] Tool {tool_name} failed: {e}")
                    result = f"Error: {str(e)}"
                
                # Log result preview
                result_preview = result[:150]
                if len(result) > 150:
                    result_preview += "..."
                logger.info(f"[AGENT]   ← {result_preview}")
                
                # Add tool result message
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result
                })
                
                # Track for response
                all_tool_results.append({
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "result": result
                })
            
            # Add tool results to messages
            messages.extend(tool_messages)
        
        # Check if we hit max turns
        if turn >= max_turns:
            logger.warning(f"[AGENT] Reached max turns ({max_turns})")
            final_message = {"role": "assistant", "content": "I've completed multiple steps but need to continue. Please ask me to continue if needed."}
        
        # Ensure we have a final message
        if final_message is None:
            final_message = {"role": "assistant", "content": "Task completed."}
        
        # Save to conversation history
        self.history.add_message(session_id, "user", message, self.llm.model_name)
        self.history.add_message(session_id, "assistant", final_message.get("content", ""), self.llm.model_name)
        
        logger.info(f"[AGENT] Completed after {turn} turns, {len(all_tool_results)} tool calls")
        
        return {
            'text': final_message.get("content", ""),
            'tool_calls': [],  # Not needed in response
            'tool_results': all_tool_results,
            'plan': plan_text,  # Include the plan if extracted
            'mode': 'tool' if all_tool_results else 'chat'
        }
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session.
        
        Args:
            session_id: Session identifier to clear
        """
        self.history.clear_conversation(session_id)
        logger.info(f"[AGENT] Cleared conversation for session: {session_id}")
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dicts
        """
        return self.history.get_conversation(session_id)
