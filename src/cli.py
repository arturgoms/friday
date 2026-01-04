"""
Friday 3.0 CLI

Command-line interface for managing Friday services and interacting
with the AI assistant.

Usage:
    friday status                     - Show service status
    friday start [service]            - Start service(s)
    friday stop [service]             - Stop service(s)
    friday logs [service]             - Tail service logs
    friday chat                       - Interactive chat mode
    friday run "query"                - Single query execution
    friday config [view|edit]         - View or edit configuration
    friday facts-list                 - List all saved facts
    friday facts-search <query>       - Search for facts
    friday facts-delete <topic> [-y]  - Delete a specific fact
    friday facts-delete-date <date>   - Delete facts from a date onwards
    friday facts-categories           - List fact categories
    friday facts-export [-o file]     - Export facts to JSON
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
        import time
        from datetime import datetime

        from src.core.constants import BRT
        from src.journal_handler import get_journal_handler

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
        from datetime import date as date_type
        from datetime import datetime

        from src.core.constants import BRT
        from src.insights.analyzers.daily_journal import DailyJournalAnalyzer
        from src.insights.config import InsightsConfig
        from src.insights.store import InsightsStore

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
# Knowledge Management Commands
# =============================================================================

@app.command()
def facts_list(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of facts to show")
):
    """List all saved facts."""
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found. No facts have been saved yet.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get latest fact for each topic with vault location
        if category:
            sql = """
                SELECT f1.topic, f1.value, f1.category, f1.created_at, f1.notes,
                       f1.vault_path, f1.vault_field, f1.vault_section
                FROM facts f1
                INNER JOIN (
                    SELECT topic, MAX(created_at) as max_date
                    FROM facts
                    WHERE category = ?
                    GROUP BY topic
                ) f2 ON f1.topic = f2.topic AND f1.created_at = f2.max_date
                ORDER BY f1.created_at DESC
                LIMIT ?
            """
            cursor.execute(sql, (category, limit))
        else:
            sql = """
                SELECT f1.topic, f1.value, f1.category, f1.created_at, f1.notes,
                       f1.vault_path, f1.vault_field, f1.vault_section
                FROM facts f1
                INNER JOIN (
                    SELECT topic, MAX(created_at) as max_date
                    FROM facts
                    GROUP BY topic
                ) f2 ON f1.topic = f2.topic AND f1.created_at = f2.max_date
                ORDER BY f1.created_at DESC
                LIMIT ?
            """
            cursor.execute(sql, (limit,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            console.print(f"[yellow]No facts found{f' in category {category}' if category else ''}[/yellow]")
            return

        # Display as table
        table = Table(title=f"Personal Facts{f' ({category})' if category else ''}", show_header=True)
        table.add_column("Topic", style="cyan", width=18)
        table.add_column("Value", style="green", width=22)
        table.add_column("Category", style="blue", width=11)
        table.add_column("Vault Location", style="magenta", width=25)
        table.add_column("Updated", style="yellow", width=16)

        for row in rows:
            topic, value, cat, created_at, notes, vault_path, vault_field, vault_section = row

            # Format vault location
            if vault_path:
                from pathlib import Path
                vault_file = Path(vault_path).stem  # Get filename without extension
                if vault_field:
                    location = f"{vault_file}:{vault_field}"
                elif vault_section:
                    # Get last part of section path
                    section_name = vault_section.split('/')[-1] if vault_section else "section"
                    location = f"{vault_file}§{section_name}"
                else:
                    location = vault_file
            else:
                location = "[dim]legacy[/dim]"

            table.add_row(
                topic,
                value[:40] + "..." if len(value) > 40 else value,
                cat or "",
                location,
                created_at
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(rows)} facts (use --limit to show more)[/dim]")
        console.print(f"[dim]Legend: filename:field (frontmatter) | filename§section (markdown section)[/dim]")

    except Exception as e:
        console.print(f"[red]Error listing facts: {e}[/red]")


@app.command()
def facts_search(
    query: str = typer.Argument(..., help="Search query"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")
):
    """Search for facts matching a query."""
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Search in topic, value, and notes
        if category:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE category = ?
                  AND (topic LIKE ? OR value LIKE ? OR notes LIKE ?)
                ORDER BY created_at DESC
            """
            params = (category, f"%{query}%", f"%{query}%", f"%{query}%")
        else:
            sql = """
                SELECT DISTINCT topic, value, category, created_at, notes
                FROM facts
                WHERE topic LIKE ? OR value LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
                LIMIT 50
            """
            params = (f"%{query}%", f"%{query}%", f"%{query}%")

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Get unique topics (latest only)
        unique = {}
        for topic, value, cat, created_at, notes in rows:
            if topic not in unique:
                unique[topic] = (value, cat, created_at, notes)

        conn.close()

        if not unique:
            console.print(f"[yellow]No facts found matching '{query}'[/yellow]")
            return

        console.print(f"\n[bold]Found {len(unique)} facts matching '{query}':[/bold]\n")

        for topic, (value, cat, created_at, notes) in unique.items():
            console.print(f"[cyan]• {topic}[/cyan]: [green]{value}[/green]")
            if cat:
                console.print(f"  Category: [blue]{cat}[/blue]")
            if notes:
                console.print(f"  Notes: {notes}")
            console.print(f"  Updated: [yellow]{created_at}[/yellow]\n")

    except Exception as e:
        console.print(f"[red]Error searching facts: {e}[/red]")


@app.command()
def facts_delete(
    topic: str = typer.Argument(..., help="Topic to delete"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Delete a specific fact (all versions)."""
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if topic exists
        cursor.execute("SELECT COUNT(*) FROM facts WHERE topic = ?", (topic,))
        count = cursor.fetchone()[0]

        if count == 0:
            console.print(f"[yellow]No facts found for topic '{topic}'[/yellow]")
            conn.close()
            return

        # Confirm deletion
        if not confirm:
            console.print(f"[yellow]This will delete {count} fact(s) for topic '{topic}'[/yellow]")
            if not typer.confirm("Are you sure?"):
                console.print("Cancelled.")
                conn.close()
                return

        # Delete
        cursor.execute("DELETE FROM facts WHERE topic = ?", (topic,))
        conn.commit()
        conn.close()

        console.print(f"[green]✓ Deleted {count} fact(s) for topic '{topic}'[/green]")

    except Exception as e:
        console.print(f"[red]Error deleting fact: {e}[/red]")


@app.command()
def facts_delete_date(
    date: str = typer.Argument(..., help="Date (YYYY-MM-DD) - delete facts from this date"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Delete facts created on or after a specific date."""
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found.[/yellow]")
        return

    try:
        # Validate date format
        from datetime import datetime
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print(f"[red]Invalid date format. Use YYYY-MM-DD (e.g., 2026-01-02)[/red]")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check how many facts will be deleted
        cursor.execute("SELECT COUNT(*) FROM facts WHERE DATE(created_at) >= ?", (date,))
        count = cursor.fetchone()[0]

        if count == 0:
            console.print(f"[yellow]No facts found on or after {date}[/yellow]")
            conn.close()
            return

        # Show facts to be deleted
        cursor.execute("""
            SELECT topic, value, created_at
            FROM facts
            WHERE DATE(created_at) >= ?
            ORDER BY created_at DESC
        """, (date,))
        facts = cursor.fetchall()

        console.print(f"\n[yellow]Facts to be deleted ({count} total):[/yellow]")
        for topic, value, created_at in facts[:10]:  # Show first 10
            console.print(f"  • {topic}: {value[:50]}... ({created_at})")
        if count > 10:
            console.print(f"  ... and {count - 10} more")

        # Confirm deletion
        if not confirm:
            console.print(f"\n[yellow]This will delete {count} fact(s) from {date} onwards[/yellow]")
            if not typer.confirm("Are you sure?"):
                console.print("Cancelled.")
                conn.close()
                return

        # Delete
        cursor.execute("DELETE FROM facts WHERE DATE(created_at) >= ?", (date,))
        conn.commit()
        conn.close()

        console.print(f"[green]✓ Deleted {count} fact(s) from {date} onwards[/green]")

    except Exception as e:
        console.print(f"[red]Error deleting facts: {e}[/red]")


@app.command()
def facts_categories():
    """List all fact categories with counts."""
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category, COUNT(DISTINCT topic) as topic_count, COUNT(*) as total_records
            FROM facts
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY topic_count DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            console.print("[yellow]No categorized facts yet.[/yellow]")
            return

        table = Table(title="Fact Categories", show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Unique Topics", style="green", justify="right")
        table.add_column("Total Records", style="blue", justify="right")

        for category, topics, records in rows:
            table.add_row(category, str(topics), str(records))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing categories: {e}[/red]")


@app.command()
def facts_export(
    output: str = typer.Option("facts_export.json", "--output", "-o", help="Output file path")
):
    """Export all facts to JSON."""
    import json
    import sqlite3

    db_path = os.path.expanduser("~/friday_facts.db")
    if not os.path.exists(db_path):
        console.print("[yellow]No facts database found.[/yellow]")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT topic, value, category, confidence, created_at, source, notes
            FROM facts
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        facts = []
        for row in rows:
            facts.append({
                "topic": row[0],
                "value": row[1],
                "category": row[2],
                "confidence": row[3],
                "created_at": row[4],
                "source": row[5],
                "notes": row[6]
            })

        with open(output, 'w') as f:
            json.dump(facts, f, indent=2)

        console.print(f"[green]✓ Exported {len(facts)} facts to {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error exporting facts: {e}[/red]")


@app.command("facts-history")
def facts_history(
    topic: str = typer.Argument(..., help="Topic to show history for"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of versions to show"),
):
    """Show the history of changes for a specific fact.

    Displays all versions of a fact over time, showing when it was created/updated
    and what the value was at each point.

    Example:
        ./friday facts-history favorite_color
        ./friday facts-history wife_birthday --limit 5
    """
    try:
        import sqlite3
        from datetime import datetime

        db_path = os.path.expanduser("~/friday_facts.db")

        if not os.path.exists(db_path):
            console.print("[yellow]No facts database found. Start chatting with Friday to create facts.[/yellow]")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all versions of this fact, ordered by creation time (newest first)
        cursor.execute("""
            SELECT value, category, confidence, created_at, source, notes
            FROM facts
            WHERE topic = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (topic, limit))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            console.print(f"[yellow]No history found for topic: {topic}[/yellow]")
            console.print("\n[dim]Tip: Use './friday facts-list' to see all available topics[/dim]")
            return

        # Display header
        console.print(f"\n[bold cyan]History for '{topic}':[/bold cyan]")
        console.print(f"[dim]Showing {len(rows)} version(s)[/dim]\n")

        # Display each version
        for i, row in enumerate(rows, 1):
            value, category, confidence, created_at, source, notes = row

            # Parse timestamp
            try:
                dt = datetime.fromisoformat(created_at)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = created_at

            # Current value marker
            is_current = (i == 1)
            marker = "[bold green]CURRENT[/bold green]" if is_current else f"[dim]Version {len(rows) - i + 1}[/dim]"

            console.print(f"{marker}")
            console.print(f"  [bold]Value:[/bold] {value}")
            console.print(f"  [dim]Category:[/dim] {category or 'none'}")
            console.print(f"  [dim]Confidence:[/dim] {confidence}")
            console.print(f"  [dim]Updated:[/dim] {time_str}")
            console.print(f"  [dim]Source:[/dim] {source}")

            if notes:
                console.print(f"  [dim]Notes:[/dim] {notes}")

            if i < len(rows):
                console.print()  # Empty line between versions

        console.print()

    except Exception as e:
        console.print(f"[red]Error viewing fact history: {e}[/red]")


@app.command("facts-reindex")
def facts_reindex(
    force: bool = typer.Option(False, "--force", "-f", help="Reindex all facts, even if they have embeddings")
):
    """Generate embeddings for facts to enable semantic search.

    This creates vector embeddings for all facts in the database, enabling
    semantic search capabilities. Run this after importing facts or to update embeddings.

    Example:
        ./friday facts-reindex                # Index facts without embeddings
        ./friday facts-reindex --force        # Reindex all facts
    """
    try:
        import sqlite3

        import numpy as np

        from src.core.embeddings import get_embeddings

        console.print("[cyan]Initializing embeddings model...[/cyan]")
        embeddings_model = get_embeddings()

        db_path = os.path.expanduser("~/friday_facts.db")
        if not os.path.exists(db_path):
            console.print("[yellow]No facts database found.[/yellow]")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get facts that need indexing
        if force:
            cursor.execute("SELECT id, topic, value FROM facts")
            console.print("[yellow]Reindexing ALL facts...[/yellow]")
        else:
            cursor.execute("SELECT id, topic, value FROM facts WHERE embedding IS NULL")
            console.print("[cyan]Indexing facts without embeddings...[/cyan]")

        facts = cursor.fetchall()

        if not facts:
            console.print("[green]✓ All facts already have embeddings![/green]")
            conn.close()
            return

        console.print(f"Found {len(facts)} facts to index\n")

        # Generate embeddings in batch
        with console.status("[bold cyan]Generating embeddings...") as status:
            for i, (fact_id, topic, value) in enumerate(facts, 1):
                try:
                    # Generate embedding
                    text = f"{topic}: {value}"
                    embedding = embeddings_model.encode(text, normalize=True)
                    embedding_blob = embedding.tobytes()

                    # Update database
                    cursor.execute(
                        "UPDATE facts SET embedding = ? WHERE id = ?",
                        (embedding_blob, fact_id)
                    )

                    if i % 10 == 0:
                        status.update(f"[bold cyan]Processed {i}/{len(facts)} facts...")
                        conn.commit()

                except Exception as e:
                    console.print(f"[yellow]⚠ Error indexing '{topic}': {e}[/yellow]")

        conn.commit()
        conn.close()

        console.print(f"\n[green]✓ Successfully indexed {len(facts)} facts![/green]")
        console.print("[dim]Semantic search is now enabled for these facts.[/dim]")

    except Exception as e:
        console.print(f"[red]Error indexing facts: {e}[/red]")


@app.command()
def facts_sync(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be synced without making changes"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-sync all facts even if already indexed")
):
    """Sync facts from Obsidian vault to database index.

    Scans your vault notes and indexes any facts that aren't already in the database.
    This allows manual vault edits to become searchable.

    Example:
        ./friday facts-sync                # Sync new facts
        ./friday facts-sync --dry-run      # Preview what would be synced
        ./friday facts-sync --force        # Re-sync everything
    """
    try:
        import sqlite3
        from datetime import datetime
        from pathlib import Path

        from src.core.constants import BRT
        from src.core.embeddings import get_embeddings
        from src.core.vault import (
            FRIDAY_NOTE,
            NOTES_DIR,
            USER_ATTRIBUTES,
            USER_NOTE,
            parse_frontmatter,
            read_vault_file,
        )

        console.print("[cyan]Scanning Obsidian vault for facts...[/cyan]\n")

        db_path = os.path.expanduser("~/friday_facts.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get existing facts
        cursor.execute("SELECT topic, vault_path, vault_field FROM facts")
        existing = {(row[0], row[1], row[2]) for row in cursor.fetchall()}

        facts_to_sync = []

        # 1. Scan user note (Artur Gomes.md) for user attributes
        console.print(f"📄 Scanning {USER_NOTE.name}...")
        if USER_NOTE.exists():
            content = read_vault_file(USER_NOTE)
            frontmatter, _ = parse_frontmatter(content)

            for field, value in frontmatter.items():
                # Check if it's a user attribute
                if field.lower() in USER_ATTRIBUTES or field.startswith('favorite_'):
                    topic = field.lower()
                    vault_path = str(USER_NOTE)

                    # Skip if already indexed (unless force)
                    if not force and (topic, vault_path, field) in existing:
                        continue

                    facts_to_sync.append({
                        'topic': topic,
                        'value': str(value),
                        'category': 'preferences' if field.startswith('favorite_') else 'personal',
                        'vault_path': vault_path,
                        'vault_field': field,
                        'vault_section': None
                    })
                    console.print(f"  → Found: {topic} = {value}")

        # 2. Scan person notes for facts about people
        console.print(f"\n📄 Scanning person notes...")
        if NOTES_DIR.exists():
            for note_file in NOTES_DIR.glob("*.md"):
                # Skip special notes
                if note_file.stem in ['Friday', 'Artur Gomes']:
                    continue

                content = read_vault_file(note_file)
                frontmatter, _ = parse_frontmatter(content)

                # Check if it's a person note
                tags = frontmatter.get('tags', [])
                if not any('person/' in str(tag) for tag in tags):
                    continue

                console.print(f"  📝 {note_file.stem}")

                # Index relevant fields
                person_name = note_file.stem.lower().replace(' ', '_')
                for field in ['birthday', 'email', 'phone', 'relationship']:
                    if field in frontmatter:
                        value = frontmatter[field]
                        topic = f"{person_name}_{field}"
                        vault_path = str(note_file)

                        if not force and (topic, vault_path, field) in existing:
                            continue

                        facts_to_sync.append({
                            'topic': topic,
                            'value': str(value),
                            'category': 'family' if 'family' in str(tags) else 'contacts',
                            'vault_path': vault_path,
                            'vault_field': field,
                            'vault_section': None
                        })
                        console.print(f"    → Found: {topic} = {value}")

        conn.close()

        # Summary
        console.print(f"\n{'='*60}")
        console.print(f"Found {len(facts_to_sync)} facts to sync")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No changes made[/yellow]")
            if facts_to_sync:
                console.print("\nWould sync:")
                for fact in facts_to_sync[:10]:  # Show first 10
                    console.print(f"  • {fact['topic']}: {fact['value']}")
                if len(facts_to_sync) > 10:
                    console.print(f"  ... and {len(facts_to_sync) - 10} more")
            return

        if not facts_to_sync:
            console.print("[green]✓ All vault facts are already indexed![/green]")
            return

        # Confirm sync
        if not typer.confirm(f"\nSync {len(facts_to_sync)} facts to database?"):
            console.print("[yellow]Sync cancelled.[/yellow]")
            return

        # Perform sync
        console.print("\n[cyan]Syncing facts to database...[/cyan]")
        embeddings_model = get_embeddings()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        synced = 0
        for fact in facts_to_sync:
            try:
                # Generate embedding
                text = f"{fact['topic']}: {fact['value']}"
                embedding = embeddings_model.encode(text, normalize=True)
                embedding_blob = embedding.tobytes()

                # Insert or update
                cursor.execute("""
                    INSERT INTO facts (
                        topic, value, category, confidence, source,
                        vault_path, vault_field, vault_section,
                        embedding, last_synced, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fact['topic'],
                    fact['value'],
                    fact['category'],
                    1.0,
                    'vault_sync',
                    fact['vault_path'],
                    fact['vault_field'],
                    fact['vault_section'],
                    embedding_blob,
                    datetime.now(BRT).isoformat(),
                    datetime.now(BRT).isoformat()
                ))
                synced += 1

            except Exception as e:
                console.print(f"[red]  ✗ Failed to sync {fact['topic']}: {e}[/red]")

        conn.commit()
        conn.close()

        console.print(f"\n[green]✓ Successfully synced {synced}/{len(facts_to_sync)} facts![/green]")
        console.print("[dim]Your vault facts are now searchable with semantic search.[/dim]")

    except Exception as e:
        console.print(f"[red]Error syncing facts: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


# =============================================================================
# Shared vLLM Tools (used by vllm_query and vllm_chat)
# =============================================================================

def get_vllm_tool_definitions():
    """Get tool definitions for vLLM commands."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current date and time in a specific timezone. Defaults to Brazil/Sao_Paulo (BRT, UTC-3) if no timezone is specified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "Timezone name (e.g., 'America/Sao_Paulo', 'UTC', 'America/New_York', 'Europe/London'). Optional, defaults to 'America/Sao_Paulo'."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform mathematical calculations. Supports basic operations: +, -, *, /, ** (power), sqrt, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The mathematical expression to evaluate (e.g., '2+2', '10*5', 'sqrt(16)')"
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "user_data",
                "description": "Get information about the user (Artur). Returns name, birthday, email, and other personal details.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "person_data",
                "description": "Get information about a specific person by name. Returns their email, birthday, and relationship to the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The person's name (e.g., 'Camila Santos', 'Sofia Menezes')"
                        }
                    },
                    "required": ["name"]
                }
            }
        }
    ]


def execute_vllm_tool(tool_call):
    """Execute a vLLM tool call and return result."""
    import json
    from datetime import datetime

    func = tool_call["function"]
    args = json.loads(func["arguments"])

    if func["name"] == "get_current_time":
        timezone_name = args.get("timezone", "America/Sao_Paulo")
        try:
            import pytz
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            return f"Error: {str(e)}"

    elif func["name"] == "calculate":
        expression = args.get("expression", "")
        try:
            import math
            allowed_names = {
                "sqrt": math.sqrt, "pow": math.pow, "abs": abs,
                "round": round, "min": min, "max": max, "sum": sum
            }
            return str(eval(expression, {"__builtins__": {}}, allowed_names))
        except Exception as e:
            return f"Error: {str(e)}"

    elif func["name"] == "user_data":
        user_info = {
            "name": "Artur Gomes",
            "birthday": "1996-03-30",
            "email": ["contato@arturgomes.com.br"],
            "phone": "+55 41 12345438",
            "company": "Counterpart",
            "favorite_color": "black",
            "favorite_food": "pizza"
        }
        return json.dumps(user_info)

    elif func["name"] == "person_data":
        person_name = args.get("name", "").lower()

        # Hardcoded person database
        people_db = {
            "camila santos": {
                "name": "Camila Santos",
                "birthday": "1995-12-12",
                "email": "camila@example.com",
                "relationship": "wife"
            },
            "sofia menezes": {
                "name": "Sofia Menezes",
                "birthday": "2018-06-15",
                "email": None,
                "relationship": "sister"
            },
            "giulia menezes": {
                "name": "Giulia Menezes",
                "birthday": "2020-03-22",
                "email": None,
                "relationship": "sister"
            },
            "sayonara aparecida": {
                "name": "Sayonara Aparecida",
                "birthday": "1970-08-10",
                "email": "sayonara@example.com",
                "relationship": "mother"
            },
            "jose roberto": {
                "name": "Jose Roberto",
                "birthday": "1968-05-20",
                "email": "jose@example.com",
                "relationship": "father"
            }
        }

        person_info = people_db.get(person_name)
        if person_info:
            return json.dumps(person_info)
        else:
            return json.dumps({"error": f"Person '{args.get('name')}' not found in database"})

    return "Unknown tool"


@app.command()
def vllm_query(
    query: str = typer.Argument(..., help="Query to send to vLLM"),
    temperature: float = typer.Option(0.6, "--temp", "-t", help="Temperature (0.0-2.0)"),
    max_tokens: int = typer.Option(512, "--max", "-m", help="Max tokens to generate"),
    reasoning: bool = typer.Option(False, "--reasoning", help="Enable reasoning mode (<think> tags)"),
    no_tools: bool = typer.Option(False, "--no-tools", help="Disable tool calling"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw JSON response")
):
    """Send a query directly to vLLM (bypasses Friday).

    Tools are enabled by default. The model will decide whether to use them.
    Available tools: get_current_time(), calculate(), user_data(), person_data(name)
    """
    import json
    from datetime import datetime

    vllm_url = "http://localhost:8000/v1/chat/completions"

    messages = []

    # Add system prompt
    if reasoning:
        system_content = """You are a helpful AI assistant with access to tools.

CRITICAL: When the user's query requires information from a tool, CALL THE TOOL immediately using function calling. DO NOT explain what you will do - JUST DO IT.

You can use <think> tags for complex reasoning when needed."""
    else:
        system_content = """You are a helpful AI assistant with access to tools.

CRITICAL: When the user's query requires information from a tool, CALL THE TOOL immediately using function calling. DO NOT explain what you will do - JUST DO IT."""

    messages.append({
        "role": "system",
        "content": system_content
    })

    messages.append({"role": "user", "content": query})

    # Get shared tool definitions
    tool_definitions = get_vllm_tool_definitions()

    payload = {
        "model": "NousResearch/Hermes-4-14B",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    # Add tools unless disabled
    if not no_tools:
        payload["tools"] = tool_definitions
        payload["tool_choice"] = "auto"  # Let model decide

    try:
        console.print(f"[dim]→ Querying vLLM (tools: {'disabled' if no_tools else 'auto'})...[/dim]")

        async def make_request(payload):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(vllm_url, json=payload)
                response.raise_for_status()
                return response.json()

        # TURN 1: Initial query
        response1 = asyncio.run(make_request(payload))

        choice = response1["choices"][0]
        message = choice["message"]

        response_final = response1  # Track final response

        # Check if tool was called
        if "tool_calls" in message and message["tool_calls"]:
            console.print("[green]✓ Tool called![/green]\n")

            if raw:
                console.print("[bold]Turn 1 Response (Tool Call):[/bold]")
                console.print(json.dumps(response1, indent=2))
                console.print()

            # Execute tools
            tool_results = []
            for tool_call in message["tool_calls"]:
                func = tool_call["function"]
                args = json.loads(func["arguments"])
                console.print(f"[bold cyan]Tool:[/bold cyan] {func['name']}")
                console.print(f"[dim]Args:[/dim] {args if args else '(none)'}")

                # Execute the tool using shared function
                result = execute_vllm_tool(tool_call)
                console.print(f"[dim]Result:[/dim] {result}\n")

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result
                })

            # TURN 2: Send tool results back
            if tool_results:
                console.print("[dim]→ Sending tool results back to model...[/dim]")
                messages_turn2 = messages.copy()
                messages_turn2.append(message)  # Add assistant's tool call message
                messages_turn2.extend(tool_results)

                payload_turn2 = {
                    "model": "NousResearch/Hermes-4-14B",
                    "messages": messages_turn2,
                    "temperature": temperature,
                    "max_tokens": 256
                }

                response2 = asyncio.run(make_request(payload_turn2))
                message = response2["choices"][0]["message"]
                response_final = response2

                if raw:
                    console.print("\n[bold]Turn 2 Response (Final Answer):[/bold]")

        # Display response
        if raw:
            console.print(json.dumps(response_final, indent=2))
        else:
            content = message.get("content", "")
            console.print("\n[bold cyan]Response:[/bold cyan]")
            console.print(content)

            # Show stats
            usage = response_final.get("usage", {})
            console.print(f"\n[dim]Tokens: {usage.get('prompt_tokens', '?')} prompt + {usage.get('completion_tokens', '?')} completion = {usage.get('total_tokens', '?')} total[/dim]")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to vLLM (http://localhost:8000)[/red]")
        console.print("[dim]Make sure friday-vllm service is running: systemctl --user status friday-vllm[/dim]")
    except httpx.TimeoutException:
        console.print("[red]Error: Request timed out (>60s)[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@app.command()
def vllm_models():
    """List models available in vLLM."""
    vllm_url = "http://localhost:8000/v1/models"

    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(vllm_url)
                response.raise_for_status()
                return response.json()

        response = asyncio.run(make_request())

        console.print("\n[bold cyan]vLLM Models:[/bold cyan]")
        for model in response.get("data", []):
            console.print(f"  • {model['id']}")
            console.print(f"    Max tokens: {model.get('max_model_len', 'unknown')}")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to vLLM (http://localhost:8000)[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# =============================================================================
# Main Entry Point
@app.command()
def vllm_chat(
    reasoning: bool = typer.Option(False, "--reasoning", help="Enable reasoning mode (<think> tags)")
):
    """Interactive chat mode with vLLM (multi-turn conversation)."""
    import json
    from datetime import datetime

    # Fetch available model from vLLM
    try:
        async def get_model():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:8000/v1/models")
                response.raise_for_status()
                models = response.json().get("data", [])
                if not models:
                    raise RuntimeError("No models available in vLLM")
                return models[0]["id"]

        model_name = asyncio.run(get_model())
    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to vLLM (http://localhost:8000)[/red]")
        console.print("[dim]Make sure friday-vllm service is running: systemctl --user status friday-vllm[/dim]")
        return
    except Exception as e:
        console.print(f"[red]Error fetching model: {e}[/red]")
        return

    console.print("[bold cyan]vLLM Interactive Chat[/bold cyan]")
    console.print(f"[dim]Model: {model_name}[/dim]")
    if reasoning:
        console.print("[dim]Mode: Reasoning enabled (<think> tags)[/dim]")
    console.print("[dim]Type 'exit' or 'quit' to end the conversation[/dim]")
    console.print("[dim]Tools available: get_current_time(), calculate(), user_data(), person_data(name)[/dim]\n")

    vllm_url = "http://localhost:8000/v1/chat/completions"

    # Initialize conversation with system prompt
    if reasoning:
        system_content = """You are a helpful AI assistant with access to tools.

CRITICAL: When the user's query requires information from a tool, CALL THE TOOL immediately using function calling. DO NOT explain what you will do - JUST DO IT.

You can use <think> tags for complex reasoning when needed."""
    else:
        system_content = """You are a helpful AI assistant with access to tools.

CRITICAL: When the user's query requires information from a tool, CALL THE TOOL immediately using function calling. DO NOT explain what you will do - JUST DO IT."""

    messages = [{
        "role": "system",
        "content": system_content
    }]

    # Get shared tool definitions
    tool_definitions = get_vllm_tool_definitions()

    async def make_request(payload):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(vllm_url, json=payload)
            response.raise_for_status()
            return response.json()

    # Chat loop
    try:
        while True:
            # Get user input
            user_input = console.input("[bold green]You:[/bold green] ").strip()

            if user_input.lower() in ['exit', 'quit', 'bye']:
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Prepare payload
            payload = {
                "model": model_name,
                "messages": messages,
                "tools": tool_definitions,
                "tool_choice": "auto",
                "temperature": 0.6,
                "max_tokens": 256
            }

            # Get response
            response = asyncio.run(make_request(payload))
            message = response["choices"][0]["message"]

            # Check for tool calls
            if "tool_calls" in message and message["tool_calls"]:
                console.print("[dim]→ Using tools...[/dim]")

                # Add assistant message with tool calls
                messages.append(message)

                # Execute all tools
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    result = execute_vllm_tool(tool_call)

                    console.print(f"[dim]  • {func_name}() → {result}[/dim]")

                    # Add tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })

                # Get final response with tool results
                payload["messages"] = messages
                # Keep tools available for potential follow-up calls
                response = asyncio.run(make_request(payload))
                message = response["choices"][0]["message"]

            # Display assistant response
            content = message.get("content", "")

            # Extract thinking tags if present
            import re
            thinking_pattern = r'<think>(.*?)</think>'
            thinking_matches = re.findall(thinking_pattern, content, re.DOTALL)

            if thinking_matches:
                # Display thinking content first
                for think_content in thinking_matches:
                    console.print(f"[bold yellow]Thinking:[/bold yellow] [dim]{think_content.strip()}[/dim]\n")

                # Remove thinking tags from final response
                clean_content = re.sub(thinking_pattern, '', content, flags=re.DOTALL).strip()
                if clean_content:
                    console.print(f"[bold cyan]Assistant:[/bold cyan] {clean_content}\n")
            else:
                console.print(f"[bold cyan]Assistant:[/bold cyan] {content}\n")

            # Add to conversation history
            messages.append(message)

    except KeyboardInterrupt:
        console.print("\n\n[dim]Chat interrupted. Goodbye![/dim]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
