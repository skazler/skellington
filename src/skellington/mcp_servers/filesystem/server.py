"""
Filesystem MCP Server 📂

Provides file system tools to Skellington agents via the Model Context Protocol.

Tools exposed:
- read_file: Read the contents of a file
- write_file: Write content to a file
- list_directory: List files in a directory
- search_files: Search for files matching<write_to_file>
<path>src/skellington/mcp_servers/filesystem/server.py</path>
<content>
"""
Filesystem MCP Server 📂

Provides file system tools to agents via the Model Context Protocol.

Learning goal: Build an MCP server from scratch using the Python MCP SDK.
This is the foundation — once you understand this pattern, all other
MCP servers follow the same structure.

Tools exposed:
- read_file: Read the contents of a file
- write_file: Write content to a file
- list_directory: List files in a directory
- search_files: Regex search across files
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.core.config import get_settings

app = Server("skellington-filesystem")


def _is_allowed(path: Path) -> bool:
    """Check if a path is within an allowed root."""
    settings = get_settings()
    for allowed in settings.filesystem_allowed_paths:
        try:
            path.resolve().relative_to(Path(allowed).resolve())
            return True
        except ValueError:
            continue
    return False


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="Read the contents of a file at the given path.",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file, creating it if it doesn't exist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
        Tool(
            name="list_directory",
            description="List files and directories at a given path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="search_files",
            description="Search for a regex pattern across files in a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string"},
                    "pattern": {"type": "string"},
                    "file_glob": {"type": "string", "default": "**/*"},
                },
                "required": ["directory", "pattern"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "read_file":
        p = Path(arguments["path"])
        if not _is_allowed(p):
            return [TextContent(type="text", text=f"Error: path not in allowed roots")]
        try:
            return [TextContent(type="text", text=p.read_text(encoding="utf-8"))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    if name == "write_file":
        p = Path(arguments["path"])
        if not _is_allowed(p):
            return [TextContent(type="text", text="Error: path not in allowed roots")]
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(arguments["content"], encoding="utf-8")
            return [TextContent(type="text", text=f"Written: {p}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    if name == "list_directory":
        p = Path(arguments["path"])
        recursive = arguments.get("recursive", False)
        try:
            pattern = "**/*" if recursive else "*"
            entries = sorted(str(f.relative_to(p)) for f in p.glob(pattern))
            return [TextContent(type="text", text="\n".join(entries))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    if name == "search_files":
        directory = Path(arguments["directory"])
        pattern = arguments["pattern"]
        glob = arguments.get("file_glob", "**/*")
        results: list[str] = []
        try:
            rx = re.compile(pattern)
            for filepath in directory.glob(glob):
                if filepath.is_file():
                    try:
                        for i, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
                            if rx.search(line):
                                results.append(f"{filepath}:{i}: {line}")
                    except Exception:
                        continue
            return [TextContent(type="text", text="\n".join(results) or "No matches")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())