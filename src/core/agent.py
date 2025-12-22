"""
Friday 3.0 Hybrid Agent

The central orchestration agent that implements the Hybrid Router pattern.
Routes between Tools, Code Interpreter, and Chat based on LLM decisions.

Usage:
    from src.core.agent import HybridAgent, get_agent
    
    agent = get_agent()
    response = await agent.run("Check disk space", user_id="user123")
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

from .config import get_config
from .interpreter import CodeInterpreter, ExecutionResult, get_interpreter
from .llm import LLMClient, LLMResponse, get_llm_client
from .registry import execute_tool, get_all_tool_schemas, get_tool_schemas_text

logger = logging.getLogger(__name__)

# Brazil timezone (UTC-3)
BRT = timezone(timedelta(hours=-3))


# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPT_TEMPLATE = """You are Friday, an AI assistant on an Ubuntu server.

{user_context}

## YOUR TOOLS
{tool_schemas}

## HOW TO USE TOOLS
When you need to perform an action (create/read/write/rename/delete notes, check system status, etc.), you MUST output ONLY this JSON format:
{{"tool": "tool_name", "args": {{"param": "value"}}}}

IMPORTANT: Output ONLY the JSON. No other text before or after. No markdown. No explanation.

## EXAMPLES
To create a note:
{{"tool": "vault_write_note", "args": {{"path": "2. Time/2.3 Meetings/Meeting Name.md", "content": "# Title\\n\\nContent here", "frontmatter": {{"tags": ["time/meeting", "area/work"], "date": "2025-12-22"}}}}}}

To search for a note:
{{"tool": "vault_search_notes", "args": {{"query": "meeting"}}}}

To read a note:
{{"tool": "vault_read_note", "args": {{"path": "folder/note.md"}}}}

## CRITICAL RULES
1. When user asks you to CREATE, SAVE, WRITE, or MAKE something - you MUST call a tool. Do NOT just describe what you would do.
2. NEVER say "I have created" or "The note has been created" unless you actually output a tool call JSON and it succeeded.
3. If you're having a conversation and building up content, when the user says to save/create it, OUTPUT THE TOOL CALL.
4. For vault operations, search first to find exact paths. Never guess paths.
5. If missing required info, ask the user.

Current time: {current_time}
"""


# =============================================================================
# Agent Response
# =============================================================================

@dataclass
class AgentResponse:
    """Response from the agent."""
    text: str
    mode: str  # "tool", "code", "chat"
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    code_results: List[ExecutionResult] = field(default_factory=list)
    iterations: int = 1
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "text": self.text,
            "mode": self.mode,
            "tool_results": self.tool_results,
            "code_results": [
                {
                    "success": r.success,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                    "exception": r.exception
                }
                for r in self.code_results
            ],
            "iterations": self.iterations,
            "error": self.error
        }


# =============================================================================
# Conversation Message
# =============================================================================

@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "system", "user", "assistant"
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


# =============================================================================
# Hybrid Agent
# =============================================================================

class HybridAgent:
    """The core agent that orchestrates tools, code execution, and chat."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        interpreter: Optional[CodeInterpreter] = None,
        max_iterations: int = 5,
        context_builder: Optional[Callable[[str, str], str]] = None
    ):
        """Initialize the agent.
        
        Args:
            llm_client: LLM client instance (defaults to global)
            interpreter: Code interpreter instance (defaults to global)
            max_iterations: Maximum ReAct loop iterations
            context_builder: Optional function to build user context
        """
        self.llm = llm_client or get_llm_client()
        self.interpreter = interpreter or get_interpreter()
        self.max_iterations = max_iterations
        self.context_builder = context_builder
        
        # Conversation history per session
        self._conversations: Dict[str, List[Message]] = {}
        
        # Confirmation callback for code execution
        self._confirmation_callback: Optional[Callable[[str, List[str]], bool]] = None
    
    def set_confirmation_callback(self, callback: Callable[[str, List[str]], bool]):
        """Set the callback for user confirmation of dangerous operations.
        
        Args:
            callback: Function that takes (code, operations) and returns True to proceed
        """
        self._confirmation_callback = callback
        self.interpreter.set_confirmation_callback(callback)
    
    def _get_conversation(self, session_id: str) -> List[Message]:
        """Get or create conversation history for a session."""
        if session_id not in self._conversations:
            self._conversations[session_id] = []
        return self._conversations[session_id]
    
    def _build_system_prompt(self, user_id: str, user_input: str) -> str:
        """Build the system prompt with context and tool schemas."""
        # Get user context if available
        user_context = ""
        if self.context_builder:
            try:
                user_context = self.context_builder(user_id, user_input)
            except Exception as e:
                logger.warning(f"Failed to build user context: {e}")
        
        # Get tool schemas
        tool_schemas = get_tool_schemas_text()
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            user_context=user_context,
            tool_schemas=tool_schemas,
            current_time=datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S")
        )
    
    def _build_messages(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str
    ) -> List[Dict[str, str]]:
        """Build the messages list for the LLM."""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        conversation = self._get_conversation(session_id)
        for msg in conversation[-10:]:  # Keep last 10 messages for context
            messages.append(msg.to_dict())
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    async def _execute_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        try:
            result = await execute_tool(tool_name, tool_args)
            return {
                "tool": tool_name,
                "success": True,
                "result": str(result)
            }
        except KeyError as e:
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Tool not found: {e}"
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "success": False,
                "error": str(e)
            }
    
    async def _execute_code(
        self,
        code: str,
        session_id: str
    ) -> ExecutionResult:
        """Execute code in the interpreter."""
        return await self.interpreter.execute(code, session_id)
    
    async def run(
        self,
        user_input: str,
        user_id: str = "default",
        session_id: Optional[str] = None
    ) -> AgentResponse:
        """Run the agent with user input.
        
        Implements the ReAct loop:
        1. Generate LLM response
        2. Check for tool calls or code blocks
        3. Execute and feed results back to LLM
        4. Repeat until done or max iterations
        
        Args:
            user_input: User's message
            user_id: User identifier for context
            session_id: Session identifier (defaults to user_id)
            
        Returns:
            AgentResponse with final text and execution results
        """
        session_id = session_id or user_id
        
        # Build system prompt
        system_prompt = self._build_system_prompt(user_id, user_input)
        
        # Initialize tracking
        tool_results: List[Dict[str, Any]] = []
        code_results: List[ExecutionResult] = []
        mode = "chat"
        iterations = 0
        final_text = ""
        
        # Build initial messages
        messages = self._build_messages(session_id, user_input, system_prompt)
        
        # ReAct loop
        while iterations < self.max_iterations:
            iterations += 1
            
            try:
                # Get LLM response (always include tools for multi-step workflows)
                response = await self.llm.generate(
                    prompt="",  # Not used when messages provided
                    messages=messages,
                    tools=get_all_tool_schemas()
                )
                
                # Check for tool calls
                if response.has_tool_call():
                    mode = "tool"
                    current_results = []
                    tool_names = []
                    for tc in response.tool_calls:
                        logger.info(f"[AGENT] Calling tool: {tc.name} with args: {tc.arguments}")
                        result = await self._execute_tool_call(tc.name, tc.arguments)
                        current_results.append(result)
                        tool_results.append(result)
                        tool_names.append(tc.name)
                        logger.info(f"[AGENT] Tool {tc.name} returned: success={result.get('success')}")
                    
                    result_text = "\n".join(r.get("result", "") for r in current_results)
                    
                    # Check if user wants raw content (read/show/display requests with read tools)
                    user_wants_raw = any(word in user_input.lower() for word in 
                        ["show", "display", "content", "read", "raw", "full text", "entire"])
                    last_tool_is_read = any(name in ["vault_read_note", "get_friday_logs"] 
                        for name in tool_names)
                    
                    # If user wants raw content and we just read something, return directly
                    if user_wants_raw and last_tool_is_read and all(r.get("success") for r in current_results):
                        logger.info(f"[AGENT] User wants raw content, returning tool output directly")
                        final_text = result_text
                        break
                    
                    # Otherwise, feed results back to LLM for processing
                    messages.append({
                        "role": "assistant",
                        "content": response.text or f"Called tool: {', '.join(tool_names)}"
                    })
                    messages.append({
                        "role": "user", 
                        "content": f"Tool result:\n{result_text}\n\nBased on this result, either call another tool if needed, or provide your final response to the user."
                    })
                    
                    logger.info(f"[AGENT] Tool results fed back to LLM (iteration {iterations})")
                    continue
                
                # Check for code blocks
                elif response.has_code():
                    mode = "code"
                    for block in response.code_blocks:
                        if block.language.lower() in ("python", "py", ""):
                            code_preview = block.code[:100].replace('\n', ' ')
                            logger.info(f"[AGENT] Executing code: {code_preview}...")
                            result = await self._execute_code(block.code, session_id)
                            code_results.append(result)
                            logger.info(f"[AGENT] Code execution: success={result.success}")
                            
                            # Add code result to messages
                            messages.append({
                                "role": "assistant",
                                "content": response.text
                            })
                            messages.append({
                                "role": "user",
                                "content": f"Code execution result:\n{result.to_llm_context()}"
                            })
                    
                    # If this is the last iteration, synthesize a response from results
                    if iterations >= self.max_iterations - 1:
                        # Build final response from code results
                        output_parts = []
                        for r in code_results:
                            if r.stdout:
                                output_parts.append(r.stdout)
                            elif r.return_value is not None:
                                output_parts.append(str(r.return_value))
                            elif r.exception:
                                output_parts.append(f"Error: {r.exception}")
                        final_text = "\n".join(output_parts) if output_parts else "Code executed successfully."
                        break
                    
                    # Continue to let LLM process results (success or error)
                    continue
                
                # Pure chat response
                else:
                    mode = "chat" if not tool_results and not code_results else mode
                    final_text = response.text
                    logger.info(f"[AGENT] Chat response, ending loop")
                    break
                    
            except Exception as e:
                logger.error(f"[AGENT] Error in iteration {iterations}: {e}", exc_info=True)
                return AgentResponse(
                    text=f"I encountered an error: {str(e)}",
                    mode="error",
                    error=str(e),
                    iterations=iterations
                )
        
        # Store conversation
        conversation = self._get_conversation(session_id)
        conversation.append(Message(role="user", content=user_input))
        conversation.append(Message(role="assistant", content=final_text))
        
        # Trim conversation if too long
        if len(conversation) > 50:
            self._conversations[session_id] = conversation[-40:]
        
        return AgentResponse(
            text=final_text,
            mode=mode,
            tool_results=tool_results,
            code_results=code_results,
            iterations=iterations
        )
    
    async def run_stream(
        self,
        user_input: str,
        user_id: str = "default",
        session_id: Optional[str] = None
    ):
        """Run the agent with streaming output.
        
        Note: Streaming is only for the final chat response.
        Tool/code execution happens before streaming.
        
        Args:
            user_input: User's message
            user_id: User identifier
            session_id: Session identifier
            
        Yields:
            Text chunks as they arrive
        """
        session_id = session_id or user_id
        
        # For now, just run normally and yield the result
        # TODO: Implement proper streaming with intermediate results
        response = await self.run(user_input, user_id, session_id)
        yield response.text
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self._conversations:
            del self._conversations[session_id]
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dictionaries
        """
        conversation = self._get_conversation(session_id)
        return [msg.to_dict() for msg in conversation]


# =============================================================================
# Global Agent Instance
# =============================================================================

_agent: Optional[HybridAgent] = None


def get_agent() -> HybridAgent:
    """Get the global agent instance.
    
    Returns:
        HybridAgent instance
    """
    global _agent
    
    if _agent is None:
        config = get_config()
        _agent = HybridAgent(
            max_iterations=config.interpreter.max_iterations
        )
    
    return _agent


async def close_agent():
    """Close the global agent and its resources."""
    global _agent
    if _agent:
        # Close LLM client
        await _agent.llm.close()
        _agent = None
