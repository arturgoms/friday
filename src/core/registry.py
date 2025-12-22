"""
Friday 3.0 Registry System

Provides decorator-based registration for tools and sensors with automatic
JSON Schema generation for LLM function calling.

Usage:
    from src.core.registry import friday_tool, friday_sensor, get_tool_registry, get_sensor_registry

    @friday_tool(name="my_tool")
    def my_tool(arg1: str, arg2: int = 10) -> str:
        '''Tool description for the LLM.'''
        return "result"

    @friday_sensor(name="my_sensor", interval_seconds=60)
    def my_sensor() -> dict:
        '''Sensor description.'''
        return {"value": 42}
"""

import inspect
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints

# =============================================================================
# Type to JSON Schema Mapping
# =============================================================================

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def python_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Convert a Python type hint to a JSON Schema type definition.
    
    Args:
        py_type: A Python type or typing annotation
        
    Returns:
        JSON Schema type definition dict
    """
    # Handle None
    if py_type is None or py_type is type(None):
        return {"type": "null"}
    
    # Handle basic types
    if py_type in TYPE_MAP:
        return {"type": TYPE_MAP[py_type]}
    
    # Handle Optional (Union with None)
    origin = getattr(py_type, "__origin__", None)
    args = getattr(py_type, "__args__", ())
    
    if origin is Union:
        # Filter out NoneType for Optional
        non_none_types = [t for t in args if t is not type(None)]
        if len(non_none_types) == 1:
            # This is Optional[X] -> just return X's schema
            return python_type_to_json_schema(non_none_types[0])
        else:
            # Multiple types - use anyOf
            return {"anyOf": [python_type_to_json_schema(t) for t in non_none_types]}
    
    # Handle List[X]
    if origin is list:
        if args:
            return {"type": "array", "items": python_type_to_json_schema(args[0])}
        return {"type": "array"}
    
    # Handle Dict[K, V]
    if origin is dict:
        return {"type": "object"}
    
    # Fallback to string for unknown types
    return {"type": "string"}


def parse_docstring(docstring: Optional[str]) -> Dict[str, Any]:
    """Parse a Google-style docstring to extract description and argument docs.
    
    Args:
        docstring: The function's docstring
        
    Returns:
        Dict with 'description' (str) and 'args' (dict of arg name -> description)
    """
    if not docstring:
        return {"description": "", "args": {}}
    
    lines = docstring.strip().split("\n")
    description_lines = []
    args_section = False
    current_arg = None
    args = {}
    
    for line in lines:
        stripped = line.strip()
        
        # Check for Args: section
        if stripped.lower() in ("args:", "arguments:", "parameters:"):
            args_section = True
            continue
        
        # Check for other sections that end Args
        if stripped.lower() in ("returns:", "return:", "raises:", "example:", "examples:"):
            args_section = False
            current_arg = None
            continue
        
        if args_section:
            # Check if this is a new argument definition
            if ":" in stripped and not stripped.startswith(" "):
                parts = stripped.split(":", 1)
                arg_name = parts[0].strip()
                arg_desc = parts[1].strip() if len(parts) > 1 else ""
                current_arg = arg_name
                args[current_arg] = arg_desc
            elif current_arg and stripped:
                # Continuation of previous arg description
                args[current_arg] += " " + stripped
        else:
            # Part of main description
            if stripped:
                description_lines.append(stripped)
    
    return {
        "description": " ".join(description_lines),
        "args": args
    }


def generate_function_schema(func: Callable, name: Optional[str] = None) -> Dict[str, Any]:
    """Generate OpenAI function calling schema from a Python function.
    
    Args:
        func: The function to generate schema for
        name: Optional override for function name
        
    Returns:
        OpenAI function calling schema dict
    """
    func_name = name or func.__name__
    sig = inspect.signature(func)
    
    # Get type hints
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    
    # Parse docstring
    doc_info = parse_docstring(func.__doc__)
    
    # Build parameters schema
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        
        # Get type
        param_type = hints.get(param_name, str)
        type_schema = python_type_to_json_schema(param_type)
        
        # Add description from docstring if available
        if param_name in doc_info["args"]:
            type_schema["description"] = doc_info["args"][param_name]
        
        properties[param_name] = type_schema
        
        # Check if required (no default value)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "type": "function",
        "function": {
            "name": func_name,
            "description": doc_info["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


# =============================================================================
# Registry Data Structures
# =============================================================================

@dataclass
class ToolEntry:
    """Registered tool entry."""
    name: str
    func: Callable
    schema: Dict[str, Any]
    description: str
    is_async: bool = False


@dataclass
class SensorEntry:
    """Registered sensor entry."""
    name: str
    func: Callable
    interval_seconds: int
    description: str
    is_async: bool = False
    enabled: bool = True


# Global registries
_TOOL_REGISTRY: Dict[str, ToolEntry] = {}
_SENSOR_REGISTRY: Dict[str, SensorEntry] = {}


# =============================================================================
# Decorators
# =============================================================================

def friday_tool(
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Callable:
    """Decorator to register a function as a Friday tool.
    
    The decorated function will be available for the LLM to call via
    function calling. Type hints and docstrings are used to generate
    the JSON schema automatically.
    
    Args:
        name: Optional override for tool name (defaults to function name)
        description: Optional override for description (defaults to docstring)
        
    Returns:
        Decorator function
        
    Example:
        @friday_tool(name="get_weather")
        def get_weather(city: str, unit: str = "celsius") -> str:
            '''Get current weather for a city.
            
            Args:
                city: The city name to get weather for
                unit: Temperature unit (celsius or fahrenheit)
            '''
            return f"Weather in {city}: 22{unit[0].upper()}"
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        schema = generate_function_schema(func, tool_name)
        
        # Override description if provided
        if description:
            schema["function"]["description"] = description
        
        # Check if async
        is_async = inspect.iscoroutinefunction(func)
        
        # Create entry
        entry = ToolEntry(
            name=tool_name,
            func=func,
            schema=schema,
            description=schema["function"]["description"],
            is_async=is_async
        )
        
        # Register
        _TOOL_REGISTRY[tool_name] = entry
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        return async_wrapper if is_async else wrapper
    
    return decorator


def friday_sensor(
    name: Optional[str] = None,
    interval_seconds: int = 300,
    description: Optional[str] = None,
    enabled: bool = True
) -> Callable:
    """Decorator to register a function as a Friday sensor.
    
    Sensors are passive data collectors that run on a schedule.
    They are used by the awareness daemon for monitoring.
    
    Args:
        name: Optional override for sensor name (defaults to function name)
        interval_seconds: How often to poll this sensor (default 5 minutes)
        description: Optional override for description (defaults to docstring)
        enabled: Whether this sensor is enabled by default
        
    Returns:
        Decorator function
        
    Example:
        @friday_sensor(name="disk_usage", interval_seconds=60)
        def check_disk_usage() -> dict:
            '''Check disk usage on root partition.'''
            import shutil
            total, used, free = shutil.disk_usage("/")
            return {
                "total_gb": total // (1024**3),
                "used_gb": used // (1024**3),
                "percent": (used / total) * 100
            }
    """
    def decorator(func: Callable) -> Callable:
        sensor_name = name or func.__name__
        doc_info = parse_docstring(func.__doc__)
        
        # Check if async
        is_async = inspect.iscoroutinefunction(func)
        
        # Create entry
        entry = SensorEntry(
            name=sensor_name,
            func=func,
            interval_seconds=interval_seconds,
            description=description or doc_info["description"],
            is_async=is_async,
            enabled=enabled
        )
        
        # Register
        _SENSOR_REGISTRY[sensor_name] = entry
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        return async_wrapper if is_async else wrapper
    
    return decorator


# =============================================================================
# Registry Access Functions
# =============================================================================

def get_tool_registry() -> Dict[str, ToolEntry]:
    """Get the global tool registry.
    
    Returns:
        Dictionary mapping tool names to ToolEntry objects
    """
    return _TOOL_REGISTRY


def get_sensor_registry() -> Dict[str, SensorEntry]:
    """Get the global sensor registry.
    
    Returns:
        Dictionary mapping sensor names to SensorEntry objects
    """
    return _SENSOR_REGISTRY


def get_tool(name: str) -> Optional[ToolEntry]:
    """Get a specific tool by name.
    
    Args:
        name: Tool name
        
    Returns:
        ToolEntry if found, None otherwise
    """
    return _TOOL_REGISTRY.get(name)


def get_sensor(name: str) -> Optional[SensorEntry]:
    """Get a specific sensor by name.
    
    Args:
        name: Sensor name
        
    Returns:
        SensorEntry if found, None otherwise
    """
    return _SENSOR_REGISTRY.get(name)


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    """Get OpenAI function calling schemas for all registered tools.
    
    Returns:
        List of function schemas ready for LLM consumption
    """
    return [entry.schema for entry in _TOOL_REGISTRY.values()]


def get_tool_schemas_text() -> str:
    """Get a formatted text representation of all tool schemas.
    
    Useful for injecting into system prompts.
    
    Returns:
        Formatted string with tool information
    """
    if not _TOOL_REGISTRY:
        return "No tools available."
    
    lines = []
    for name, entry in _TOOL_REGISTRY.items():
        schema = entry.schema["function"]
        params = schema["parameters"]["properties"]
        required = schema["parameters"].get("required", [])
        
        # Build parameter string
        param_strs = []
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "any")
            req = "(required)" if pname in required else "(optional)"
            desc = pinfo.get("description", "")
            param_strs.append(f"    - {pname}: {ptype} {req} - {desc}")
        
        lines.append(f"- {name}: {schema['description']}")
        if param_strs:
            lines.extend(param_strs)
    
    return "\n".join(lines)


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute a registered tool by name.
    
    Args:
        name: Tool name
        args: Arguments to pass to the tool
        
    Returns:
        Tool return value
        
    Raises:
        KeyError: If tool not found
        Exception: Any exception from tool execution
    """
    entry = _TOOL_REGISTRY.get(name)
    if not entry:
        raise KeyError(f"Tool '{name}' not found in registry")
    
    if entry.is_async:
        return await entry.func(**args)
    else:
        return entry.func(**args)


async def execute_sensor(name: str) -> Any:
    """Execute a registered sensor by name.
    
    Args:
        name: Sensor name
        
    Returns:
        Sensor return value
        
    Raises:
        KeyError: If sensor not found
    """
    entry = _SENSOR_REGISTRY.get(name)
    if not entry:
        raise KeyError(f"Sensor '{name}' not found in registry")
    
    if entry.is_async:
        return await entry.func()
    else:
        return entry.func()


def clear_registries():
    """Clear all registries. Useful for testing."""
    _TOOL_REGISTRY.clear()
    _SENSOR_REGISTRY.clear()
