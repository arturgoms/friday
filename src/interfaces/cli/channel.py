"""
CLI Channel Implementation

Provides a command-line interface using the Channel architecture.
This allows the CLI to integrate with Friday's agent and delivery systems.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.markdown import Markdown

from src.interfaces.base import (
    Channel,
    Message,
    MessageType,
    MessagePriority,
    DeliveryResult,
)

console = Console()


class CLIChannel(Channel):
    """
    CLI Channel for command-line interaction with Friday.
    
    This channel provides a synchronous interface for CLI commands,
    while still integrating with Friday's agent and delivery systems.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(channel_id="cli", config=config)
        self._is_running = False
    
    async def send(self, message: Message) -> DeliveryResult:
        """
        Send a message to the CLI (print to console).
        
        Args:
            message: Message to display
            
        Returns:
            DeliveryResult indicating success
        """
        try:
            if message.type == MessageType.TEXT:
                # Render as markdown for nice formatting
                if message.content:
                    md = Markdown(message.content)
                    console.print(md)
                else:
                    console.print("[dim]No content[/dim]")
            else:
                console.print(message.content)
            
            return DeliveryResult(
                success=True,
                message_id=f"cli_{datetime.now().timestamp()}",
                timestamp=datetime.now()
            )
        except Exception as e:
            return DeliveryResult(
                success=False,
                error=str(e),
                timestamp=datetime.now()
            )
    
    def send_sync(self, content: str, render_markdown: bool = True) -> DeliveryResult:
        """
        Synchronous send for CLI convenience.
        
        Args:
            content: Text content to display
            render_markdown: Whether to render as markdown
            
        Returns:
            DeliveryResult indicating success
        """
        try:
            if render_markdown:
                md = Markdown(content)
                console.print(md)
            else:
                console.print(content)
            
            return DeliveryResult(
                success=True,
                message_id=f"cli_{datetime.now().timestamp()}",
                timestamp=datetime.now()
            )
        except Exception as e:
            return DeliveryResult(
                success=False,
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def start(self):
        """Start the CLI channel (no-op for CLI)."""
        self._is_running = True
        self.logger.info("CLI channel started")
    
    async def stop(self):
        """Stop the CLI channel (no-op for CLI)."""
        self._is_running = False
        self.logger.info("CLI channel stopped")
    
    def is_available(self) -> bool:
        """CLI is always available."""
        return True
    
    def supports_message_type(self, message_type: MessageType) -> bool:
        """CLI primarily supports text messages."""
        return message_type == MessageType.TEXT
    
    def print_success(self, message: str):
        """Print a success message."""
        console.print(f"[green]✓[/green] {message}")
    
    def print_error(self, message: str):
        """Print an error message."""
        console.print(f"[red]✗[/red] {message}")
    
    def print_warning(self, message: str):
        """Print a warning message."""
        console.print(f"[yellow]⚠[/yellow] {message}")
    
    def print_info(self, message: str):
        """Print an info message."""
        console.print(f"[cyan]ℹ[/cyan] {message}")
