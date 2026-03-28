"""
🎃 Skellington CLI — Rich/Typer terminal interface.

Learning goal: Building a polished CLI with Typer + Rich, including:
- Streaming agent output
- Spooky Halloween/Christmas theming
- Progress indicators
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from skellington.utils.logging import configure_logging
from skellington.utils.themes import AGENT_EMOJIS, BANNER, SKELLINGTON_THEME

app = typer.Typer(
    name="skellington",
    help="🎃 Multi-agent AI orchestration with Halloween-ized Christmas characters.",
    rich_markup_mode="rich",
)

console = Console(theme=SKELLINGTON_THEME)


def _print_banner() -> None:
    console.print(BANNER)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    request: str = typer.Argument(default=None, help="Request to send to Jack"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """
    Send a request to Skellington's multi-agent system.

    Example:
        skellington "research the top 5 Python async frameworks and build a demo"
    """
    if ctx.invoked_subcommand:
        return

    if not request:
        _print_banner()
        console.print("[info]Use [bold]skellington --help[/bold] to see commands.[/info]")
        raise typer.Exit()

    configure_logging()
    _print_banner()
    asyncio.run(_run_request(request, verbose=verbose))


async def _run_request(request: str, verbose: bool = False) -> None:
    """Run a request through the full agent pipeline."""
    from skellington.agents import Jack, Mayor, Oogie, Sally, Zero
    from skellington.core.orchestrator import AgentRegistry, Orchestrator

    # Register all agents
    for agent_class in [Jack, Sally, Oogie, Zero, Mayor]:
        AgentRegistry.register(agent_class())

    orchestrator = Orchestrator()

    console.print(
        Panel(
            Text(request, style="bold white"),
            title="[jack]🎃 Jack received your request[/jack]",
            border_style="bright_white",
        )
    )

    with console.status("[jack]Jack is orchestrating...[/jack]", spinner="bouncingBall"):
        state = await orchestrator.run(request)

    # Find the final result
    root_task = state.tasks[0] if state.tasks else None
    if root_task and root_task.result:
        console.print(
            Panel(
                root_task.result,
                title="[mayor]🎭 Mayor's Report[/mayor]",
                border_style="green",
            )
        )
    else:
        error = root_task.error if root_task else "Unknown error"
        console.print(f"[error]❌ Workflow failed: {error}[/error]")


@app.command()
def web(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(True, help="Enable auto-reload"),
) -> None:
    """Launch the Skellington web UI."""
    import uvicorn

    configure_logging()
    console.print("[info]🌐 Starting Skellington web UI...[/info]")
    uvicorn.run(
        "skellington.ui.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def agents() -> None:
    """List all available agents and their roles."""
    _print_banner()
    from rich.table import Table

    table = Table(title="🎃 Skellington Agents 🎄", border_style="bright_white")
    table.add_column("Character", style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Role")

    rows = [
        ("🎃👔 Jack Skellington", "jack", "Orchestrator — plans and delegates"),
        ("🧟‍♀️🎁 Sally Claus", "sally", "Builder — code generation & scaffolding"),
        ("🎰🎅 Oogie Boogie", "oogie", "Researcher — web search & RAG"),
        ("👻🔴 Zero", "zero", "Navigator — file system & codebase analysis"),
        ("👹 Lock", "lock", "Validator — logic correctness"),
        ("🔮👹 Shock", "shock", "Validator — style & maintainability"),
        ("💀👹 Barrel", "barrel", "Validator — security & robustness"),
        ("🎭📊 The Mayor", "mayor", "Reporter — results & formatting"),
    ]
    for char, agent, role in rows:
        table.add_row(char, agent, role)

    console.print(table)
