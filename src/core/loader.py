"""
Tool loader for Friday.

Auto-discovers and loads tool modules from src/tools directory.
"""

import importlib
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def discover_tool_modules(tools_path: Path) -> List[str]:
    """Discover all Python modules in tools directory.
    
    Args:
        tools_path: Path to tools directory
        
    Returns:
        List of module names (e.g., ['src.tools.people', 'src.tools.weather'])
    """
    modules = []
    
    if not tools_path.exists():
        logger.warning(f"[LOADER] Tools directory not found: {tools_path}")
        return modules
    
    # Find all .py files (excluding __init__.py)
    for py_file in tools_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        module_name = f"src.tools.{py_file.stem}"
        modules.append(module_name)
    
    return modules


def load_tools() -> List[str]:
    """Load all tool modules from src/tools.
    
    Returns:
        List of loaded module names
    """
    project_root = Path(__file__).parent.parent.parent
    tools_path = project_root / "src" / "tools"
    
    modules = discover_tool_modules(tools_path)
    loaded = []
    
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            loaded.append(module_name)
            logger.info(f"[LOADER] Loaded: {module_name}")
        except Exception as e:
            logger.error(f"[LOADER] Failed to load {module_name}: {e}")
    
    return loaded
