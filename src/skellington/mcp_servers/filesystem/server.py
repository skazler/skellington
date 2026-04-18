"""
Filesystem MCP Server 📂

Thin MCP adapter over `tools.py`. All real logic — access control, reads,
writes, listing, searching — lives in `tools.py` so Python callers can use
it directly without the stdio transport. This server just:

  1. declares the MCP tool schemas
  2. dispatches calls to `tools.py`
  3. wraps return values in MCP `TextContent`

Learning goal: separate transport (MCP stdio) from behavior (plain Python
functions). Same pattern every other MCP server in this repo will follow.
"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.mcp_servers.filesystem import tools

app = Server("skellington-filesystem")


# ---------------------------------------------------------------------------
# Tool schemas — shared between the MCP server and any in-process clients
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[Tool] = [
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


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_SCHEMAS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "read_file":
            text = await tools.read_file(arguments["path"])
            return [TextContent(type="text", text=text)]

        if name == "write_file":
            written = await tools.write_file(arguments["path"], arguments["content"])
            return [TextContent(type="text", text=f"Written: {written}")]

        if name == "list_directory":
            entries = await tools.list_directory(
                arguments["path"],
                recursive=arguments.get("recursive", False),
            )
            return [TextContent(type="text", text="\n".join(entries))]

        if name == "search_files":
            matches = await tools.search_files(
                arguments["directory"],
                arguments["pattern"],
                file_glob=arguments.get("file_glob", "**/*"),
            )
            return [TextContent(type="text", text="\n".join(matches) or "No matches")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except tools.FilesystemAccessError as exc:
        return [TextContent(type="text", text=f"Error: {exc}")]
    except Exception as exc:  # noqa: BLE001 — MCP must never raise
        return [TextContent(type="text", text=f"Error: {exc}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
