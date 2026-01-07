"""
Friday CLI Commands

All CLI commands implemented using Typer.
Organized into:
- Tool execution (run any registered tool)
- Database operations (list/delete/add to any table)
- Channel delivery (send tool results to telegram/etc)
- Service management (status, logs, restart)
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from settings import settings
from src.core.database import Database
from src.core.agent import agent
from src.interfaces.cli.channel import CLIChannel

# Initialize
app = typer.Typer(
    name="friday",
    help="Friday AI Assistant CLI",
    add_completion=False
)
console = Console()
cli_channel = CLIChannel()

# Service definitions
SERVICES = ["friday-vllm", "friday-telegram", "friday-awareness"]


# =============================================================================
# Tool Execution Commands
# =============================================================================

@app.command()
def tool(
    tool_name: str = typer.Argument(..., help="Tool name to execute"),
    args: Optional[List[str]] = typer.Argument(None, help="Tool arguments as key=value"),
    send: Optional[str] = typer.Option(None, "--send", "-s", help="Send result to channel (telegram)"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw output without formatting")
):
    """
    Execute a Friday tool directly by name.
    
    Examples:
        friday tool create_daily_journal_thread
        friday tool create_daily_journal_thread --send telegram
        friday tool get_weather city=Curitiba
        friday tool generate_daily_note date=2026-01-06
    """
    try:
        # Parse arguments
        tool_args = {}
        if args:
            for arg in args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    tool_args[key] = value
                else:
                    console.print(f"[red]Invalid argument format: {arg}[/red]")
                    console.print("[dim]Use key=value format[/dim]")
                    raise typer.Exit(1)
        
        # Get the tool function
        tool_func = None
        tools_dict = agent._function_toolset.tools
        if tool_name in tools_dict:
            tool_func = tools_dict[tool_name].function
        else:
            tool_func = None
        
        if not tool_func:
            console.print(f"[red]Tool not found: {tool_name}[/red]")
            console.print("\n[dim]Use 'friday tools' to list available tools[/dim]")
            raise typer.Exit(1)
        
        # Execute tool
        console.print(f"[cyan]Executing tool:[/cyan] {tool_name}")
        if tool_args:
            console.print(f"[dim]Arguments:[/dim] {tool_args}")
        
        result = tool_func(**tool_args)
        
        # Display result
        if raw:
            print(result)
        else:
            console.print("\n[bold green]Result:[/bold green]")
            console.print(result)
        
        # Send to channel if requested
        if send:
            if send.lower() == "telegram":
                from src.awareness.delivery.channels import get_channel_registry
                from src.awareness.delivery.loader import initialize_channels
                
                # Initialize channels if not already done
                registry = get_channel_registry()
                if not registry.list_channels():
                    initialize_channels()
                
                telegram_channel = registry.get("telegram")
                
                if telegram_channel and telegram_channel.enabled:
                    # Create insight from result
                    from src.awareness.models import Insight, Priority, InsightType, Category
                    insight = Insight(
                        type=InsightType.DIGEST,
                        category=Category.SYSTEM,
                        priority=Priority.HIGH,
                        title=tool_name,
                        message=str(result),
                        confidence=1.0
                    )
                    
                    telegram_channel.send_insight_sync(insight)
                    console.print(f"\n[green]✓ Sent to Telegram[/green]")
                else:
                    console.print(f"\n[yellow]⚠ Telegram channel not available or disabled[/yellow]")
            else:
                console.print(f"\n[yellow]⚠ Unknown channel: {send}[/yellow]")
    
    except Exception as e:
        console.print(f"[red]Error executing tool: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def tools(
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search tools by name"),
    grouped: bool = typer.Option(True, "--grouped/--flat", "-g/-f", help="Group by module")
):
    """List all available tools."""
    tools_dict = agent._function_toolset.tools
    
    # Organize tools by module
    tools_by_module = {}
    for tool_name, tool in tools_dict.items():
        if search and search.lower() not in tool_name.lower():
            continue
        
        # Get module name from function
        module = "unknown"
        if hasattr(tool, 'function') and hasattr(tool.function, '__module__'):
            module_path = tool.function.__module__
            # Extract the last part after src.tools.
            if 'src.tools.' in module_path:
                module = module_path.split('src.tools.')[-1]
            else:
                module = module_path.split('.')[-1]
        
        if module not in tools_by_module:
            tools_by_module[module] = []
        
        desc = tool.description if hasattr(tool, 'description') else "No description"
        
        # Check if tool has parameters
        has_params = False
        if hasattr(tool, 'function_schema') and tool.function_schema:
            schema = tool.function_schema.json_schema
            if 'properties' in schema and schema['properties']:
                has_params = True
        
        tools_by_module[module].append((tool_name, desc or "No description", has_params))
    
    if grouped:
        # Print grouped by module
        total_tools = 0
        for module in sorted(tools_by_module.keys()):
            tools_list = sorted(tools_by_module[module])
            total_tools += len(tools_list)
            
            # Create table for this module
            table = Table(title=f"[bold cyan]{module}[/bold cyan] ({len(tools_list)} tools)", show_header=True)
            table.add_column("Name", style="cyan", width=40)
            table.add_column("Description", style="white", width=80)
            
            for name, desc, has_params in tools_list:
                # Clean up description - extract summary
                if '<summary>' in desc:
                    desc = desc.split('<summary>')[1].split('</summary>')[0].strip()
                
                # Add indicator for tools with parameters
                name_display = f"{name} [dim](params)[/dim]" if has_params else name
                table.add_row(name_display, desc[:80] + "..." if len(desc) > 80 else desc)
            
            console.print(table)
            console.print()
        
        console.print(f"[dim]Total: {total_tools} tools across {len(tools_by_module)} modules[/dim]")
        console.print(f"[dim]Tip: Use 'friday tool-info <name>' to see parameters and usage[/dim]")
    else:
        # Flat list
        table = Table(title="Friday Tools", show_header=True)
        table.add_column("Name", style="cyan", width=40)
        table.add_column("Module", style="yellow", width=20)
        table.add_column("Description", style="white")
        
        all_tools = []
        for module, tools_list in tools_by_module.items():
            for name, desc, has_params in tools_list:
                # Clean up description
                if '<summary>' in desc:
                    desc = desc.split('<summary>')[1].split('</summary>')[0].strip()
                
                # Add indicator for tools with parameters
                name_display = f"{name} (params)" if has_params else name
                all_tools.append((name_display, module, desc))
        
        all_tools.sort()
        
        for name, module, desc in all_tools:
            table.add_row(name, module, desc[:60] + "..." if len(desc) > 60 else desc)
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(all_tools)} tools[/dim]")
        console.print(f"[dim]Tip: Use 'friday tool-info <name>' to see parameters and usage[/dim]")


@app.command()
def tool_info(tool_name: str = typer.Argument(..., help="Tool name to inspect")):
    """
    Show detailed information about a specific tool including parameters.
    
    Examples:
        friday tool-info get_weather_forecast
        friday tool-info get_sleep_summary
    """
    tools_dict = agent._function_toolset.tools
    
    if tool_name not in tools_dict:
        console.print(f"[red]Tool not found: {tool_name}[/red]")
        console.print("\n[dim]Use 'friday tools' to list available tools[/dim]")
        raise typer.Exit(1)
    
    tool = tools_dict[tool_name]
    
    # Display tool information
    console.print(f"\n[bold cyan]Tool:[/bold cyan] {tool_name}")
    
    # Module
    if hasattr(tool, 'function') and hasattr(tool.function, '__module__'):
        module = tool.function.__module__
        console.print(f"[bold]Module:[/bold] {module}")
    
    # Description
    if hasattr(tool, 'description') and tool.description:
        desc = tool.description
        # Clean up XML tags
        if '<summary>' in desc:
            summary = desc.split('<summary>')[1].split('</summary>')[0].strip()
            console.print(f"\n[bold]Description:[/bold]")
            console.print(summary)
        else:
            console.print(f"\n[bold]Description:[/bold]")
            console.print(desc)
    
    # Parameters from JSON schema
    if hasattr(tool, 'function_schema') and tool.function_schema:
        schema = tool.function_schema.json_schema
        
        if 'properties' in schema and schema['properties']:
            console.print(f"\n[bold]Parameters:[/bold]")
            
            params_table = Table(show_header=True, box=None)
            params_table.add_column("Name", style="cyan")
            params_table.add_column("Type", style="yellow")
            params_table.add_column("Required", style="magenta")
            params_table.add_column("Default", style="green")
            params_table.add_column("Description", style="white")
            
            required_params = schema.get('required', [])
            
            for param_name, param_info in schema['properties'].items():
                param_type = param_info.get('type', 'any')
                is_required = "Yes" if param_name in required_params else "No"
                default = str(param_info.get('default', '-'))
                param_desc = param_info.get('description', '')
                
                params_table.add_row(
                    param_name,
                    param_type,
                    is_required,
                    default,
                    param_desc[:50] + "..." if len(param_desc) > 50 else param_desc
                )
            
            console.print(params_table)
        else:
            console.print(f"\n[dim]No parameters required[/dim]")
    
    # Usage example
    console.print(f"\n[bold]Usage:[/bold]")
    if hasattr(tool, 'function_schema') and tool.function_schema:
        schema = tool.function_schema.json_schema
        if 'properties' in schema and schema['properties']:
            # Generate example with parameters
            example_params = []
            for param_name, param_info in schema['properties'].items():
                if param_name in schema.get('required', []):
                    example_params.append(f"{param_name}=<value>")
            
            if example_params:
                console.print(f"  friday tool {tool_name} {' '.join(example_params)}")
            else:
                console.print(f"  friday tool {tool_name} [param=value ...]")
        else:
            console.print(f"  friday tool {tool_name}")
    else:
        console.print(f"  friday tool {tool_name}")
    
    console.print()


@app.command()
def chat():
    """
    Start an interactive chat session with Friday.
    
    Type your messages and Friday will respond using all available tools.
    Type 'quit' or 'exit' to end the session.
    Press Ctrl+C to exit.
    
    Examples:
        friday chat
    """
    console.print("[bold cyan]Friday Interactive Chat[/bold cyan]")
    console.print("[dim]Type 'quit' or 'exit' to end session, Ctrl+C to abort[/dim]\n")
    
    # Store conversation history
    history = []
    
    try:
        while True:
            # Get user input
            try:
                user_input = console.input("[bold green]You:[/bold green] ")
            except EOFError:
                break
            
            if not user_input.strip():
                continue
            
            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("\n[dim]Goodbye![/dim]")
                break
            
            # Run agent with history
            console.print("[dim]Friday is thinking...[/dim]")
            
            try:
                result = agent.run_sync(user_input, message_history=history)
                
                # Print response
                console.print(f"[bold cyan]Friday:[/bold cyan] {result.output}")
                
                # Update history - result.all_messages() contains full conversation
                history = result.all_messages()
                
                # Show usage stats
                if hasattr(result, 'usage') and result.usage():
                    usage = result.usage()
                    console.print(f"[dim]Tokens: {usage}[/dim]\n")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    except KeyboardInterrupt:
        console.print("\n\n[dim]Chat session ended[/dim]")


@app.command()
def run(query: str = typer.Argument(..., help="Natural language query for Friday")):
    """
    Run a natural language query through Friday's agent.
    
    Examples:
        friday run "create today's journal thread and send to telegram"
        friday run "what's the weather in Curitiba?"
        friday run "show me my portfolio"
    """
    try:
        console.print("[dim]→ Processing query with Friday's agent...[/dim]\n")
        
        result = agent.run_sync(query)
        
        # Display result
        console.print(str(result.output))
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Database Operations
# =============================================================================

@app.command()
def db_list(
    table: str = typer.Argument(..., help="Table name (journal_entries, journal_threads, snapshots, insights, etc)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Number of rows to show"),
    where: Optional[str] = typer.Option(None, "--where", "-w", help="WHERE clause (e.g., 'date=2026-01-06')"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Columns to show (comma-separated)")
):
    """
    List rows from any database table.
    
    Examples:
        friday db-list journal_entries --limit 10
        friday db-list journal_entries --where "date(timestamp)='2026-01-06'"
        friday db-list snapshots --columns "source,timestamp,data" --limit 5
        friday db-list insights --where "priority='high'" --limit 20
    """
    try:
        db = Database()
        
        # Build query
        cols = columns if columns else "*"
        query = f"SELECT {cols} FROM {table}"
        
        if where:
            query += f" WHERE {where}"
        
        query += f" LIMIT {limit}"
        
        console.print(f"[dim]Query:[/dim] {query}\n")
        
        # Execute
        rows = db.execute(query).fetchall()
        
        if not rows:
            console.print("[yellow]No rows found[/yellow]")
            return
        
        # Display as table
        result_table = Table(title=f"{table} ({len(rows)} rows)")
        
        # Add columns - get from first row
        if rows:
            # Convert SQLAlchemy Row to dict
            first_row_dict = dict(rows[0]._mapping)
            col_names = list(first_row_dict.keys())
            for col in col_names:
                result_table.add_column(col, style="cyan")
            
            # Add rows
            for row in rows:
                row_dict = dict(row._mapping)
                result_table.add_row(*[str(row_dict[col]) for col in col_names])
        
        console.print(result_table)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def db_delete(
    table: str = typer.Argument(..., help="Table name"),
    where: str = typer.Argument(..., help="WHERE clause (e.g., 'id=123' or 'date<2026-01-01')"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """
    Delete rows from any database table.
    
    Examples:
        friday db-delete journal_entries "date(timestamp)='2026-01-05'" --yes
        friday db-delete snapshots "source='test'" 
        friday db-delete insights "created_at<'2026-01-01'"
    """
    try:
        db = Database()
        
        # Count rows to delete
        count_query = f"SELECT COUNT(*) as count FROM {table} WHERE {where}"
        result = db.execute(count_query).fetchone()
        count = dict(result._mapping)['count']
        
        if count == 0:
            console.print("[yellow]No rows match the criteria[/yellow]")
            return
        
        # Confirm
        if not confirm:
            console.print(f"[yellow]This will delete {count} row(s) from {table}[/yellow]")
            console.print(f"[dim]WHERE {where}[/dim]")
            if not typer.confirm("\nAre you sure?"):
                console.print("Cancelled.")
                return
        
        # Delete
        delete_query = f"DELETE FROM {table} WHERE {where}"
        db.execute(delete_query)
        
        console.print(f"[green]✓ Deleted {count} row(s) from {table}[/green]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def db_query(
    sql: str = typer.Argument(..., help="SQL query to execute"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv")
):
    """
    Execute a raw SQL query.
    
    Examples:
        friday db-query "SELECT * FROM journal_entries WHERE date(timestamp)='2026-01-06'"
        friday db-query "SELECT date, COUNT(*) FROM journal_entries GROUP BY date" --format json
    """
    try:
        db = Database()
        rows = db.execute(sql).fetchall()
        
        if not rows:
            console.print("[yellow]No results[/yellow]")
            return
        
        if format == "json":
            print(json.dumps([dict(row) for row in rows], indent=2, default=str))
        elif format == "csv":
            col_names = rows[0].keys()
            print(",".join(col_names))
            for row in rows:
                print(",".join([str(row[col]) for col in col_names]))
        else:  # table
            result_table = Table(title=f"Query Results ({len(rows)} rows)")
            col_names = rows[0].keys()
            for col in col_names:
                result_table.add_column(col, style="cyan")
            for row in rows:
                result_table.add_row(*[str(row[col]) for col in col_names])
            console.print(result_table)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Scheduled Reports Management
# =============================================================================

@app.command()
def schedule_trigger(report_name: str = typer.Argument(..., help="Name of the scheduled report to trigger")):
    """
    Manually trigger a scheduled report.
    
    This executes the report through the same flow as the automatic scheduler,
    including all special handling (e.g., saving journal thread message_id).
    
    Examples:
        friday schedule-trigger journal_thread
        friday schedule-trigger morning_briefing
        friday schedule-trigger evening_report
    """
    try:
        from src.awareness.engine import AwarenessEngine
        
        console.print(f"[cyan]Triggering scheduled report:[/cyan] {report_name}")
        
        # Initialize awareness engine
        engine = AwarenessEngine()
        
        # Trigger the report
        success = engine.trigger_report(report_name)
        
        if success:
            console.print(f"[green]✓ Report '{report_name}' executed successfully[/green]")
        else:
            console.print(f"[red]✗ Failed to execute report '{report_name}'[/red]")
            console.print("[dim]Check logs for details[/dim]")
            raise typer.Exit(1)
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def schedule_list():
    """
    List all scheduled reports with their configuration.
    
    Examples:
        friday schedule-list
    """
    try:
        from src.awareness.engine import AwarenessEngine
        
        engine = AwarenessEngine()
        reports = engine.get_scheduled_reports()
        
        if not reports:
            console.print("[yellow]No scheduled reports configured[/yellow]")
            return
        
        table = Table(title="Scheduled Reports", show_header=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Schedule", style="yellow", width=15)
        table.add_column("Enabled", style="magenta", width=10)
        table.add_column("Channels", style="green", width=15)
        table.add_column("Description", style="white")
        
        for report in reports:
            name = report.get("name", "N/A")
            schedule = report.get("schedule", "N/A")
            enabled = "✓" if report.get("enabled", True) else "✗"
            channels = ", ".join(report.get("channels", []))
            if not channels:
                channels = "[dim]none[/dim]"
            description = report.get("description", "")
            
            table.add_row(name, schedule, enabled, channels, description[:50] + "..." if len(description) > 50 else description)
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(reports)} scheduled reports[/dim]")
        console.print(f"[dim]Tip: Use 'friday schedule-status <name>' for details[/dim]")
        console.print(f"[dim]Tip: Use 'friday schedule-trigger <name>' to run manually[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def schedule_status(report_name: str = typer.Argument(..., help="Name of the scheduled report")):
    """
    Show status and details for a specific scheduled report.
    
    Examples:
        friday schedule-status journal_thread
        friday schedule-status morning_briefing
    """
    try:
        from src.awareness.engine import AwarenessEngine
        
        engine = AwarenessEngine()
        status = engine.get_report_status(report_name)
        
        if "error" in status:
            console.print(f"[red]{status['error']}[/red]")
            raise typer.Exit(1)
        
        # Display status
        table = Table(title=f"Report Status: {report_name}", show_header=False, box=None)
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Name", status.get("name", "N/A"))
        table.add_row("Enabled", "✓ Yes" if status.get("enabled") else "✗ No")
        table.add_row("Schedule (cron)", status.get("schedule", "N/A"))
        table.add_row("Last Sent", status.get("last_sent", "[dim]Never[/dim]"))
        table.add_row("Next Run", status.get("next_run", "[dim]Not scheduled[/dim]"))
        
        channels = ", ".join(status.get("channels", []))
        table.add_row("Channels", channels if channels else "[dim]none[/dim]")
        table.add_row("Description", status.get("description", ""))
        
        console.print(table)
        console.print(f"\n[dim]Tip: Use 'friday schedule-trigger {report_name}' to run manually[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Service Management
# =============================================================================

def get_systemd_status(service: str) -> dict:
    """Get systemd service status."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", service, 
             "--property=ActiveState,SubState,MainPID,MemoryCurrent"],
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


def get_gpu_memory():
    """Get GPU memory usage using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                used, total = lines[0].split(",")
                return int(used.strip()), int(total.strip())
    except Exception:
        pass
    return None, None


@app.command()
def status():
    """Show status of all Friday services, GPU, and tools."""
    # Services table
    table = Table(title="Friday System Status", style="bold white")
    table.add_column("Service", style="cyan", width=25)
    table.add_column("State", style="magenta", width=12)
    table.add_column("PID", justify="right", width=8)
    table.add_column("Memory", justify="right", width=12)
    
    for service in SERVICES:
        status_info = get_systemd_status(service)
        
        state = status_info.get("ActiveState", "unknown")
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
        
        pid_display = pid if pid != "0" else "-"
        
        table.add_row(service, state_display, pid_display, mem_display)
    
    console.print(table)
    
    # System info table
    info_table = Table(title="System Info", show_header=False, style="bold white")
    info_table.add_column("Metric", style="cyan", width=20)
    info_table.add_column("Value", style="white")
    
    # Get GPU memory
    gpu_used, gpu_total = get_gpu_memory()
    if gpu_used is not None and gpu_total is not None:
        gpu_percent = (gpu_used / gpu_total) * 100
        gpu_display = f"{gpu_used} MB / {gpu_total} MB ({gpu_percent:.1f}%)"
        info_table.add_row("GPU Memory", gpu_display)
    else:
        info_table.add_row("GPU Memory", "[dim]unavailable[/dim]")
    
    # Get tool count
    tools_dict = agent._function_toolset.tools
    tool_count = len(tools_dict)
    info_table.add_row("Registered Tools", str(tool_count))
    
    console.print()
    console.print(info_table)


@app.command()
def logs(
    service: str = typer.Argument("all", help="Service to tail logs for (or 'all')"),
    lines: int = typer.Option(50, "-n", "--lines", help="Number of lines to show"),
    follow: bool = typer.Option(True, "-f", "--follow/--no-follow", help="Follow log output")
):
    """
    Tail logs for Friday services.
    
    Examples:
        friday logs
        friday logs friday-telegram -n 100
        friday logs all --no-follow
    """
    logs_dir = Path(__file__).parent.parent.parent.parent / "logs"
    
    if service == "all":
        console.print("[cyan]Tailing logs for all Friday services...[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        
        log_files = []
        for svc in SERVICES:
            log_file = logs_dir / f"{svc}.log"
            if log_file.exists():
                log_files.append(str(log_file))
        
        if not log_files:
            console.print("[yellow]No log files found[/yellow]")
            return
        
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


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    app()
