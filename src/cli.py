"""
Friday 3.0 CLI

Command-line interface for managing Friday services and interacting
with the AI assistant.

Usage:
    friday status              - Show service status
    friday start [service]     - Start service(s)
    friday stop [service]      - Stop service(s)
    friday logs [service]      - Tail service logs
    friday chat                - Interactive chat mode
    friday run "query"         - Single query execution
    friday config [view|edit]  - View or edit configuration
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

# Initialize Typer app and Rich console
app = typer.Typer(
    name="friday",
    help="Friday 3.0 - Autonomous AI Platform CLI",
    add_completion=False
)
console = Console()

# Service definitions
SERVICES = ["friday-vllm", "friday-core", "friday-awareness", "friday-telegram"]

# Default API URL
DEFAULT_API_URL = "http://localhost:8080"


# =============================================================================
# Helper Functions
# =============================================================================

def get_api_url() -> str:
    """Get the API URL from environment or default."""
    return os.getenv("FRIDAY_API_URL", DEFAULT_API_URL)


def get_api_headers() -> dict:
    """Get headers for API requests including auth."""
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("FRIDAY_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def get_systemd_status(service: str) -> dict:
    """Get systemd service status."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", service, "--property=ActiveState,SubState,MainPID,MemoryCurrent"],
            capture_output=True,
            text=True,
            timeout=5
        )
        status = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                status[key] = value
        return status
    except Exception:
        return {"ActiveState": "unknown", "SubState": "unknown"}


async def api_request(
    method: str,
    endpoint: str,
    data: Optional[dict] = None,
    timeout: float = 120.0
) -> dict:
    """Make an API request to the core service."""
    url = f"{get_api_url()}{endpoint}"
    headers = get_api_headers()
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method.upper() == "GET":
            response = await client.get(url, headers=headers)
        else:
            response = await client.post(url, json=data or {}, headers=headers)
        
        response.raise_for_status()
        return response.json()


# =============================================================================
# Status Command
# =============================================================================

@app.command()
def status():
    """Show status of all Friday services."""
    table = Table(title="Friday 3.0 System Status", style="bold white")
    table.add_column("Service", style="cyan", width=20)
    table.add_column("State", style="magenta", width=12)
    table.add_column("PID", justify="right", width=8)
    table.add_column("Memory", justify="right", width=12)
    
    for service in SERVICES:
        status_info = get_systemd_status(service)
        
        state = status_info.get("ActiveState", "unknown")
        substate = status_info.get("SubState", "")
        pid = status_info.get("MainPID", "0")
        memory = status_info.get("MemoryCurrent", "0")
        
        # Format state with color
        if state == "active":
            state_display = f"[green]{state}[/green]"
        elif state == "inactive":
            state_display = f"[yellow]{state}[/yellow]"
        else:
            state_display = f"[red]{state}[/red]"
        
        # Format memory
        try:
            mem_bytes = int(memory)
            if mem_bytes > 1024 * 1024 * 1024:
                mem_display = f"{mem_bytes / (1024**3):.1f} GB"
            elif mem_bytes > 1024 * 1024:
                mem_display = f"{mem_bytes / (1024**2):.1f} MB"
            else:
                mem_display = f"{mem_bytes / 1024:.1f} KB"
        except (ValueError, TypeError):
            mem_display = "-"
        
        # PID display
        pid_display = pid if pid != "0" else "-"
        
        table.add_row(service, state_display, pid_display, mem_display)
    
    console.print(table)
    
    # Show API health if core is running
    try:
        response = asyncio.run(api_request("GET", "/health", timeout=5.0))
        console.print(f"\n[green]API Status:[/green] {response.get('status', 'unknown')}")
        console.print(f"[cyan]LLM Available:[/cyan] {response.get('llm_available', False)}")
        console.print(f"[cyan]Tools Loaded:[/cyan] {response.get('tools_loaded', 0)}")
        console.print(f"[cyan]Sensors Loaded:[/cyan] {response.get('sensors_loaded', 0)}")
    except Exception:
        console.print("\n[yellow]API not reachable[/yellow]")


# =============================================================================
# Service Management Commands
# =============================================================================

@app.command()
def start(service: str = typer.Argument("all", help="Service to start (or 'all')")):
    """Start Friday service(s)."""
    services_to_start = SERVICES if service == "all" else [service]
    
    for svc in services_to_start:
        console.print(f"Starting {svc}...", end=" ")
        try:
            subprocess.run(
                ["systemctl", "--user", "start", svc],
                check=True,
                capture_output=True
            )
            console.print("[green]OK[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]FAILED[/red]")
            console.print(f"  Error: {e.stderr.decode()}")


@app.command()
def stop(service: str = typer.Argument("all", help="Service to stop (or 'all')")):
    """Stop Friday service(s)."""
    services_to_stop = SERVICES if service == "all" else [service]
    
    for svc in services_to_stop:
        console.print(f"Stopping {svc}...", end=" ")
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", svc],
                check=True,
                capture_output=True
            )
            console.print("[green]OK[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]FAILED[/red]")
            console.print(f"  Error: {e.stderr.decode()}")


@app.command()
def restart(service: str = typer.Argument("all", help="Service to restart (or 'all')")):
    """Restart Friday service(s)."""
    services_to_restart = SERVICES if service == "all" else [service]
    
    for svc in services_to_restart:
        console.print(f"Restarting {svc}...", end=" ")
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", svc],
                check=True,
                capture_output=True
            )
            console.print("[green]OK[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]FAILED[/red]")
            console.print(f"  Error: {e.stderr.decode()}")


@app.command()
def logs(
    service: str = typer.Argument("all", help="Service to tail logs for (or 'all')"),
    lines: int = typer.Option(50, "-n", "--lines", help="Number of lines to show"),
    follow: bool = typer.Option(True, "-f", "--follow/--no-follow", help="Follow log output")
):
    """Tail logs for a Friday service."""
    # Get logs directory
    logs_dir = Path(__file__).parent.parent / "logs"
    
    if service == "all":
        # Show combined logs from all log files
        console.print(f"[cyan]Tailing logs for all Friday services...[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        
        # Build tail command for all log files
        log_files = []
        for svc in SERVICES:
            log_file = logs_dir / f"{svc}.log"
            if log_file.exists():
                log_files.append(str(log_file))
        
        if not log_files:
            console.print("[yellow]No log files found[/yellow]")
            return
        
        # Use tail with multiple files (shows file markers and combines output)
        cmd = ["tail", f"-n", str(lines)]
        if follow:
            cmd.append("-f")
        cmd.extend(log_files)
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
    else:
        console.print(f"[cyan]Tailing logs for {service}...[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        
        log_file = logs_dir / f"{service}.log"
        if not log_file.exists():
            console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
            return
        
        cmd = ["tail", f"-n", str(lines)]
        if follow:
            cmd.append("-f")
        cmd.append(str(log_file))
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass


# =============================================================================
# Chat Commands
# =============================================================================

@app.command()
def chat():
    """Start interactive chat session with Friday."""
    console.print("[bold green]Friday 3.0 Terminal Interface[/bold green]")
    console.print(f"Connected to {get_api_url()}")
    console.print("[dim]Type 'exit' or 'quit' to end the session[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold blue]You > [/bold blue]")
            
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            
            if not user_input.strip():
                continue
            
            # Show thinking indicator
            with console.status("[yellow]Thinking...[/yellow]", spinner="dots"):
                try:
                    response = asyncio.run(api_request(
                        "POST", "/chat",
                        {"text": user_input}
                    ))
                except httpx.ConnectError:
                    console.print("[red]Error: Cannot connect to Friday. Is the service running?[/red]")
                    continue
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    continue
            
            # Display response
            console.print("[bold green]Friday > [/bold green]")
            
            text = response.get("text", "")
            if text:
                # Render as markdown for nice formatting
                md = Markdown(text)
                console.print(md)
            else:
                console.print("[dim]No response[/dim]")
            
            # Show mode indicator
            mode = response.get("mode", "chat")
            if mode != "chat":
                console.print(f"[dim]Mode: {mode}[/dim]")
            
            console.print()  # Blank line
            
        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
        except EOFError:
            break


@app.command()
def run(query: str = typer.Argument(..., help="Query to send to Friday")):
    """Execute a single query and print the result."""
    # Check for piped input
    if not sys.stdin.isatty():
        piped_data = sys.stdin.read()
        query = f"{query}\n\nContext:\n{piped_data}"
    
    try:
        # Use fresh=True to clear conversation history for single queries
        response = asyncio.run(api_request("POST", "/chat", {"text": query, "fresh": True}))
        print(response.get("text", ""))
    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to Friday. Is the service running?[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Configuration Commands
# =============================================================================

@app.command()
def config(
    action: str = typer.Argument("view", help="Action: view or edit")
):
    """View or edit the configuration file."""
    # Find config file
    config_path = Path(__file__).parent.parent / "config.yml"
    
    if not config_path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    if action == "edit":
        editor = os.getenv("EDITOR", "nano")
        subprocess.run([editor, str(config_path)])
    else:
        # View with syntax highlighting
        with open(config_path) as f:
            content = f.read()
        
        syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)


# =============================================================================
# Tool Commands
# =============================================================================

@app.command()
def tools():
    """List available tools."""
    try:
        response = asyncio.run(api_request("GET", "/tools"))
        
        table = Table(title="Registered Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        
        for tool in response.get("tools", []):
            table.add_row(tool["name"], tool["description"])
        
        console.print(table)
        console.print(f"\n[dim]Total: {response.get('count', 0)} tools[/dim]")
        
    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to Friday API[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def sensors():
    """List available sensors."""
    try:
        response = asyncio.run(api_request("GET", "/sensors"))
        
        table = Table(title="Registered Sensors")
        table.add_column("Name", style="cyan")
        table.add_column("Interval", justify="right")
        table.add_column("Enabled", justify="center")
        table.add_column("Description")
        
        for sensor in response.get("sensors", []):
            interval = f"{sensor['interval_seconds']}s"
            enabled = "[green]Yes[/green]" if sensor["enabled"] else "[red]No[/red]"
            table.add_row(sensor["name"], interval, enabled, sensor["description"])
        
        console.print(table)
        console.print(f"\n[dim]Total: {response.get('count', 0)} sensors[/dim]")
        
    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to Friday API[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# =============================================================================
# Journal Commands
# =============================================================================

@app.command()
def journal_thread():
    """Send the morning journal thread to Telegram."""
    try:
        from datetime import datetime
        from src.core.constants import BRT
        from src.journal_handler import get_journal_handler
        
        # Get environment variables
        user_id_str = os.getenv('TELEGRAM_USER_ID')
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not user_id_str or not bot_token:
            console.print("[red]Error: TELEGRAM_USER_ID and TELEGRAM_BOT_TOKEN must be set[/red]")
            raise typer.Exit(1)
        
        user_id = int(user_id_str)
        
        # Get journal handler and generate message
        handler = get_journal_handler()
        message_text = handler.get_morning_thread_message()
        
        console.print(f"[cyan]Sending journal thread to user {user_id}...[/cyan]")
        console.print(f'[dim]Message: "{message_text}"[/dim]\n')
        
        # Send via Telegram API
        async def send_message():
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "chat_id": user_id,
                    "text": message_text
                })
                return response.json()
        
        result = asyncio.run(send_message())
        
        if result.get('ok'):
            message_id = result['result']['message_id']
            console.print(f"[green]✓[/green] Message sent! Message ID: [cyan]{message_id}[/cyan]")
            
            # Save the thread message ID
            today = datetime.now(BRT).strftime('%Y-%m-%d')
            success = handler.save_thread_message(today, message_id)
            
            if success:
                console.print(f"[green]✓[/green] Thread saved for {today}")
            else:
                console.print(f"[yellow]⚠[/yellow] Thread for {today} already exists (skipped)")
            
            console.print(f"\n[bold green]📱 Now reply to that message in Telegram to add journal entries![/bold green]")
        else:
            console.print(f"[red]✗ Failed to send message: {result}[/red]")
            raise typer.Exit(1)
            
    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def journal_entries(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date to view entries for (YYYY-MM-DD, default: today)"),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow mode - refresh every 5 seconds")
):
    """View journal entries for a date."""
    try:
        from datetime import datetime
        from src.core.constants import BRT
        from src.journal_handler import get_journal_handler
        import time
        
        # Parse date
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
                target_date = date
            except ValueError:
                console.print(f"[red]Error: Invalid date format. Use YYYY-MM-DD[/red]")
                raise typer.Exit(1)
        else:
            target_date = datetime.now(BRT).strftime('%Y-%m-%d')
        
        handler = get_journal_handler()
        
        def display_entries():
            console.clear()
            entries = handler.get_entries_for_date(target_date)
            
            console.print(f"[bold cyan]Journal Entries for {target_date}[/bold cyan]\n")
            
            if not entries:
                console.print("[yellow]No entries yet for this date[/yellow]")
                return
            
            # Create table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Time", style="cyan", width=8)
            table.add_column("Type", style="yellow", width=8)
            table.add_column("Thread ID", style="dim", width=10)
            table.add_column("Content", style="white")
            
            for entry in entries:
                timestamp = entry["timestamp"].strftime("%H:%M")
                entry_type = entry["entry_type"]
                content = entry["content"]
                thread_id = entry.get("thread_message_id", "-")
                
                # Truncate long entries
                if len(content) > 70:
                    content = content[:67] + "..."
                
                # Color code by type
                type_display = f"[green]{entry_type}[/green]" if entry_type == "text" else f"[blue]{entry_type}[/blue]"
                
                # Format thread ID
                thread_display = str(thread_id) if thread_id else "-"
                
                table.add_row(timestamp, type_display, thread_display, content)
            
            console.print(table)
            console.print(f"\n[dim]Total: {len(entries)} entries[/dim]")
        
        if follow:
            console.print("[dim]Follow mode - Press Ctrl+C to exit[/dim]\n")
            try:
                while True:
                    display_entries()
                    time.sleep(5)
            except KeyboardInterrupt:
                console.print("\n[dim]Stopped following[/dim]")
        else:
            display_entries()
            
    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def journal_note(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date to generate note for (YYYY-MM-DD, default: today)")
):
    """Generate the daily journal note."""
    try:
        from datetime import datetime, date as date_type
        from src.core.constants import BRT
        from src.insights.config import InsightsConfig
        from src.insights.store import InsightsStore
        from src.insights.analyzers.daily_journal import DailyJournalAnalyzer
        
        # Parse date
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                console.print(f"[red]Error: Invalid date format. Use YYYY-MM-DD[/red]")
                raise typer.Exit(1)
        else:
            target_date = datetime.now(BRT).date()
        
        console.print(f"[cyan]Generating daily journal note for {target_date}...[/cyan]\n")
        
        # Initialize
        config = InsightsConfig.load()
        store = InsightsStore()
        analyzer = DailyJournalAnalyzer(config, store)
        
        # Collect and generate
        with console.status("[yellow]Collecting data...[/yellow]", spinner="dots"):
            # Temporarily override the collect method to use our target date
            from src.insights.collectors.journal import JournalCollector
            collector = JournalCollector(store)
            journal_data = collector.collect(target_date=target_date)
        
        if not journal_data:
            console.print("[yellow]⚠ No data collected for this date[/yellow]")
            raise typer.Exit(1)
        
        entry_count = journal_data.get("entry_count", 0)
        event_count = journal_data.get("event_count", 0)
        
        console.print(f"[green]✓[/green] Collected {entry_count} journal entries, {event_count} calendar events")
        
        # Generate note
        with console.status("[yellow]Generating note with LLM...[/yellow]", spinner="dots"):
            result = analyzer.run({"target_date": target_date})
        
        if result.success and result.insights:
            insight = result.insights[0]
            console.print(f"\n[green]✓ Daily note created![/green]\n")
            console.print("[bold]Notification:[/bold]")
            console.print(insight.message)
            
            note_path = insight.data.get("path", "")
            if note_path:
                console.print(f"\n[cyan]Note location:[/cyan] {note_path}")
        else:
            error_msg = result.error if hasattr(result, 'error') and result.error else "Unknown error"
            console.print(f"[red]✗ Failed to generate note: {error_msg}[/red]")
            raise typer.Exit(1)
            
    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


# =============================================================================
# Version Command
# =============================================================================

@app.command()
def version():
    """Show Friday version."""
    console.print("[bold]Friday 3.0[/bold]")
    console.print("Autonomous AI Platform")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
