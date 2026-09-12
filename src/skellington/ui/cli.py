"""
🎃 Skellington CLI — Rich/Typer terminal interface.

Learning goal: Building a polished CLI with Typer + Rich, including:
- Streaming agent output
- Spooky Halloween/Christmas theming
- Progress indicators
"""

from __future__ import annotations

import asyncio

import click
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typer.core import TyperGroup

from skellington.utils.logging import configure_logging
from skellington.utils.themes import BANNER, SKELLINGTON_THEME


class _DefaultToRun(TyperGroup):
    """Let a bare prompt work: `skellington "do a thing"` means `run "do a thing"`.

    The callback used to take the prompt as a positional argument, which meant
    click consumed the first token before it could resolve a subcommand — so
    `skellington agents` ran a *workflow* for the request "agents" and every
    subcommand was unreachable. Deciding here instead keeps both spellings.
    """

    def resolve_command(self, ctx: click.Context, args: list[str]):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["run", *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="skellington",
    cls=_DefaultToRun,
    help="🎃 Multi-agent AI orchestration with Halloween-ized Christmas characters.",
    rich_markup_mode="rich",
)

console = Console(theme=SKELLINGTON_THEME)


def _print_banner() -> None:
    console.print(BANNER)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """🎃 Multi-agent AI orchestration."""
    if ctx.invoked_subcommand is None:
        _print_banner()
        console.print("[info]Use [bold]skellington --help[/bold] to see commands.[/info]")


@app.command()
def run(
    request: str = typer.Argument(..., help="Request to send to Jack"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """
    Send a request to Skellington's multi-agent system.

    The `run` is optional, so both of these work:

        skellington "research the top 5 Python async frameworks and build a demo"
        skellington run "research the top 5 Python async frameworks and build a demo"
    """
    configure_logging()
    _print_banner()
    asyncio.run(_run_request(request, verbose=verbose))


async def _run_request(request: str, verbose: bool = False) -> None:
    """Run a request through the full agent pipeline."""
    from skellington.agents import default_agents
    from skellington.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(agents=default_agents())

    console.print(
        Panel(
            Text(request, style="bold white"),
            title="[jack]🎃 Jack received your request[/jack]",
            border_style="bright_white",
        )
    )

    with console.status("[jack]Jack is orchestrating...[/jack]", spinner="bouncingBall"):
        state = await orchestrator.run(request)

    if state.final_output:
        console.print(
            Panel(
                state.final_output,
                title="[mayor]🎭 Mayor's Report[/mayor]",
                border_style="green",
            )
        )
    else:
        console.print(f"[error]❌ Workflow failed: {state.error}[/error]")


@app.command("eval")
def eval_command(
    path: str = typer.Argument("evalsets", help="An .evalset.json file, or a directory of them"),
    case: list[str] = typer.Option(None, "--case", "-c", help="Run only these case ids"),
    temperature: float = typer.Option(0.0, help="Pinned for every call in every run"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List the cases without running them"),
    json_out: bool = typer.Option(False, "--json", help="Emit the report as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Score the agent system against declarative eval cases.

    Each case runs a real workflow, so this spends tokens. --dry-run lists
    what would run without calling anything.

        skellington eval
        skellington eval evalsets/routing.evalset.json --case build-only
    """
    from pathlib import Path

    from skellington.eval import EvalSet

    if verbose:
        configure_logging()

    target = Path(path)
    if not target.exists():
        console.print(f"[error]No such path: {path}[/error]")
        raise typer.Exit(code=2)

    try:
        sets = [EvalSet.from_file(target)] if target.is_file() else EvalSet.from_dir(target)
    except Exception as exc:  # noqa: BLE001 — a bad case file is a user error, not a crash
        console.print(f"[error]Could not load eval cases: {exc}[/error]")
        raise typer.Exit(code=2) from exc

    if not sets:
        console.print(f"[error]No *.evalset.json files under {path}[/error]")
        raise typer.Exit(code=2)

    if dry_run:
        _print_dry_run(sets, case or None)
        return

    # Pre-flight: every case would otherwise fail with the same construction
    # error, which reads like three bugs instead of one missing variable.
    from skellington.core.config import get_settings

    if not get_settings().anthropic_api_key:
        console.print("[error]ANTHROPIC_API_KEY is not set — eval cases run real workflows.[/error]")
        console.print("[info]Set it, or use --dry-run to list the cases without calling out.[/info]")
        raise typer.Exit(code=2)

    ok = asyncio.run(_run_eval(sets, case or None, temperature, json_out))
    raise typer.Exit(code=0 if ok else 1)


def _print_dry_run(sets: list, only: list[str] | None) -> None:
    from rich.table import Table

    table = Table(title="🎃 Eval cases", border_style="bright_white")
    table.add_column("Set", style="cyan")
    table.add_column("Case", style="bold")
    table.add_column("Expects")

    count = 0
    for eval_set in sets:
        for c in eval_set.cases:
            if only and c.id not in only:
                continue
            count += 1
            expects = []
            if c.expect.agents is not None:
                expects.append(" → ".join(c.expect.agents))
            if c.expect.succeeded is not None:
                expects.append(f"succeeded={c.expect.succeeded}")
            if c.expect.contains:
                expects.append(f"contains {c.expect.contains}")
            if c.expect.max_llm_calls is not None:
                expects.append(f"≤{c.expect.max_llm_calls} calls")
            table.add_row(eval_set.name, c.id, ", ".join(expects))

    console.print(table)
    console.print(f"[info]{count} case(s) would run. No LLM calls were made.[/info]")


async def _run_eval(sets: list, only: list[str] | None, temperature: float, json_out: bool) -> bool:
    import json as json_module

    from skellington.eval import run_set

    reports = []
    all_passed = True

    for eval_set in sets:
        if only and not any(c.id in only for c in eval_set.cases):
            continue

        if not json_out:
            console.print(f"\n[bold]{eval_set.name}[/bold] — {len(eval_set.cases)} case(s)")

        def report_one(result) -> None:
            if json_out:
                return
            mark = "[green]PASS[/green]" if result.passed else "[error]FAIL[/error]"
            score_text = (
                f" traj={result.trajectory_score:.2f}"
                if result.trajectory_score is not None
                else ""
            )
            console.print(
                f"  {mark} {result.case_id}{score_text} "
                f"[dim]{result.usage.calls} calls, "
                f"{result.usage.total_tokens} tok, {result.duration_s:.1f}s[/dim]"
            )
            if result.error:
                console.print(f"        [error]{result.error}[/error]")
            for check in result.checks:
                if not check.passed:
                    console.print(f"        [error]✗ {check.name}[/error]: {check.detail}")

        try:
            report = await run_set(
                eval_set, temperature=temperature, only=only, on_result=report_one
            )
        except KeyError as exc:
            console.print(f"[error]{exc}[/error]")
            return False

        reports.append(report)
        all_passed = all_passed and report.all_passed

    if json_out:
        console.print_json(
            json_module.dumps([r.model_dump(mode="json") for r in reports], default=str)
        )
        return all_passed

    _print_summary(reports)
    return all_passed


def _print_summary(reports: list) -> None:
    from rich.table import Table

    table = Table(title="🎄 Summary", border_style="bright_white")
    table.add_column("Set", style="cyan")
    table.add_column("Passed")
    table.add_column("Trajectory avg")
    table.add_column("Calls")
    table.add_column("Tokens")

    for report in reports:
        avg = report.trajectory_avg
        style = "green" if report.all_passed else "error"
        table.add_row(
            report.set_name,
            f"[{style}]{report.passed}/{report.total}[/{style}]",
            f"{avg:.2f}" if avg is not None else "—",
            str(report.usage.calls),
            str(report.usage.total_tokens),
        )

    console.print()
    console.print(table)


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
