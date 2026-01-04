"""
Tool registry for Friday.

Provides decorator to register tools and functions to retrieve them.
"""

import inspect
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


# Global tool registry
_TOOL_REGISTRY: Dict[str, Callable] = {}


def friday_tool(name: str = None): # type: ignore
    """Decorator to register a tool function.
    
    Usage:
        @friday_tool(name="get_time")
        def get_current_time(timezone: str = "UTC") -> str:
            '''Get current time in timezone.'''
            ...
    
    Args:
        name: Tool name (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        _TOOL_REGISTRY[tool_name] = func
        logger.info(f"[REGISTRY] Registered tool: {tool_name}")
        return func
    return decorator


def get_tool_registry() -> Dict[str, Callable]:
    """Get all registered tools.
    
    Returns:
        Dictionary of tool_name -> function
    """
    return _TOOL_REGISTRY.copy()


def get_tool(name: str) -> Callable:
    """Get a tool by name.
    
    Args:
        name: Tool name
        
    Returns:
        Tool function
        
    Raises:
        KeyError: If tool not found
    """
    return _TOOL_REGISTRY[name]


def clear_registry():
    """Clear all registered tools (for testing)."""
    global _TOOL_REGISTRY
    _TOOL_REGISTRY.clear()


def build_tool_definitions() -> List[Dict]:
    """Build OpenAI-format tool definitions from registered tools.
    
    Returns:
        List of tool definition dicts
    """
    definitions = []
    
    for name, func in _TOOL_REGISTRY.items():
        # Extract docstring
        description = func.__doc__ or f"Tool: {name}"
        description = description.strip()
        
        # Get function signature
        sig = inspect.signature(func)
        
        # Build parameters schema
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default
            param_desc = f"Parameter: {param_name}"
            
            # Infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
            
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
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        
        definitions.append(definition)
    
    return definitions
