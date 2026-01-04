"""
Friday 3.0 Extension Loader

Auto-discovers and loads tools and sensors from the src/tools and src/sensors
directories. This triggers the decorators and populates the registries.

Usage:
    from src.core.loader import load_extensions
    
    # Call at startup before using tools/sensors
    load_extensions()
"""

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def _discover_modules(package_path: Path, package_name: str) -> List[str]:
    """Discover all Python modules in a package directory.
    
    Args:
        package_path: Path to the package directory
        package_name: Fully qualified package name (e.g., 'src.tools')
        
    Returns:
        List of fully qualified module names
    """
    modules = []
    
    if not package_path.exists():
        logger.warning(f"Package path does not exist: {package_path}")
        return modules
    
    # Find all .py files (excluding __init__.py and __pycache__)
    for py_file in package_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        module_name = py_file.stem
        full_name = f"{package_name}.{module_name}"
        modules.append(full_name)
    
    # Also check subdirectories for nested modules
    for subdir in package_path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("_"):
            init_file = subdir / "__init__.py"
            if init_file.exists():
                # It's a package, recursively discover
                sub_modules = _discover_modules(
                    subdir, 
                    f"{package_name}.{subdir.name}"
                )
                modules.extend(sub_modules)
    
    return modules


def _import_module_safe(module_name: str) -> Tuple[bool, str]:
    """Safely import a module, catching any errors.
    
    Args:
        module_name: Fully qualified module name
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        importlib.import_module(module_name)
        return True, f"Loaded: {module_name}"
    except Exception as e:
        error_msg = f"Failed to load {module_name}: {e}"
        logger.error(error_msg)
        return False, error_msg


def load_tools(base_path: Path | None = None, only_modules: List[str] | None = None) -> List[str]:
    """Load all tool modules from src/tools.
    
    Args:
        base_path: Optional base path (defaults to project root)
        only_modules: Optional list of specific modules to load (e.g., ['people', 'memory'])
        
    Returns:
        List of successfully loaded module names
    """
    if base_path is None:
        # Default to project root (3 levels up from this file)
        base_path = Path(__file__).parent.parent.parent
    
    tools_path = base_path / "src" / "tools"
    package_name = "src.tools"
    
    modules = _discover_modules(tools_path, package_name)
    
    # Filter if only_modules is specified
    if only_modules:
        filtered = []
        for module in modules:
            module_name = module.split('.')[-1]  # Get last part (e.g., 'people' from 'src.tools.people')
            if module_name in only_modules:
                filtered.append(module)
        modules = filtered
        logger.info(f"Filtered to {len(modules)} modules: {only_modules}")
    
    loaded = []
    
    for module_name in modules:
        success, message = _import_module_safe(module_name)
        if success:
            loaded.append(module_name)
            logger.info(message)
        else:
            logger.warning(message)
    
    return loaded


def load_sensors(base_path: Path | None = None) -> List[str]:
    """Load all sensor modules from src/sensors.
    
    Args:
        base_path: Optional base path (defaults to project root)
        
    Returns:
        List of successfully loaded module names
    """
    if base_path is None:
        # Default to project root (3 levels up from this file)
        base_path = Path(__file__).parent.parent.parent
    
    sensors_path = base_path / "src" / "sensors"
    package_name = "src.sensors"
    
    modules = _discover_modules(sensors_path, package_name)
    loaded = []
    
    for module_name in modules:
        success, message = _import_module_safe(module_name)
        if success:
            loaded.append(module_name)
            logger.info(message)
        else:
            logger.warning(message)
    
    return loaded


def load_extensions(base_path: Path | None = None, only_tool_modules: List[str] | None = None) -> dict:
    """Load all extensions (tools and sensors).
    
    This should be called at application startup before using any
    tools or sensors. It triggers the decorators which populate
    the global registries.
    
    Args:
        base_path: Optional base path (defaults to project root)
        only_tool_modules: Optional list of specific tool modules to load (e.g., ['people', 'memory'])
        
    Returns:
        Dictionary with 'tools' and 'sensors' lists of loaded modules
    """
    logger.info("Loading Friday extensions...")
    
    tool_modules = load_tools(base_path, only_modules=only_tool_modules)
    sensor_modules = load_sensors(base_path)
    
    # Get actual counts from registries
    from .registry import get_tool_registry, get_sensor_registry
    tool_count = len(get_tool_registry())
    sensor_count = len(get_sensor_registry())
    
    logger.info(f"Loaded {tool_count} tools from {len(tool_modules)} modules, {sensor_count} sensors from {len(sensor_modules)} modules")
    
    return {
        "tools": tool_modules,
        "sensors": sensor_modules
    }


def reload_extensions(base_path: Path | None = None) -> dict:
    """Reload all extensions, clearing existing registries first.
    
    Useful for development/hot-reloading.
    
    Args:
        base_path: Optional base path (defaults to project root)
        
    Returns:
        Dictionary with 'tools' and 'sensors' lists of loaded modules
    """
    try:
        from src.core.registry import clear_registries
    except ImportError:
        from .registry import clear_registries
    
    logger.info("Reloading Friday extensions...")
    clear_registries()
    
    return load_extensions(base_path)
