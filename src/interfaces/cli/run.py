"""
Friday CLI Entry Point

Main entry point for the Friday CLI.
Run with: python -m src.interfaces.cli.run [command]
Or create a symlink: ln -s $(pwd)/src/interfaces/cli/run.py ~/bin/friday
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.interfaces.cli.commands import app

if __name__ == "__main__":
    app()
