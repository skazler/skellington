"""
Git MCP Server 🌿

Provides git operations to Zero (Navigator) and Mayor (Reporter).

Learning goal: Wrapping CLI tools (git) as MCP server tools.

Tools exposed:
- git_status: Get working tree status
- git_log: Get commit history
- git_diff: Get diff between refs or working tree
- git_show: Show a specific commit
"""

from __future__ import annotations

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("skellington-git")


async def _run_git(args: list[str], cwd: str = ".") -> str:
    """Run a git command and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return f"git error: {stderr.decode().strip()}"
    return stdout.decode().strip()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="git_status",
            description="Get the current git working tree status.",
            inputSchema={
                "type": "object",
                "properties": {"repo_path": {"type": "string", "default": "."}},
            },
        ),
        Tool(
            name="git_log",
            description="Get recent commit history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "default": "."},
                    "max_count": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="git_diff",
            description="Get a diff. Omit ref1/ref2 for working tree diff.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "default": "."},
                    "ref1": {"type": "string"},
                    "ref2": {"type": "string"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    repo = arguments.get("repo_path", ".")

    if name == "git_status":
        result = await _run_git(["status", "--short"], cwd=repo)
        return [TextContent(type="text", text=result or "Working tree clean")]

    if name == "git_log":
        n = arguments.get("max_count", 10)
        result = await _run_git(["log", f"-{n}", "--oneline", "--decorate"], cwd=repo)
        return [TextContent(type="text", text=result)]

    if name == "git_diff":
        args = ["diff"]
        if arguments.get("ref1"):
            args.append(arguments["ref1"])
        if arguments.get("ref2"):
            args.append(arguments["ref2"])
        result = await _run_git(args, cwd=repo)
        return [TextContent(type="text", text=result or "No differences")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
