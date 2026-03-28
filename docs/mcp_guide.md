# MCP Server Development Guide

## What is MCP?

The **Model Context Protocol (MCP)** is an open protocol that standardizes how
AI applications connect to external tools and data sources. Think of it like
USB-C for AI tools — any MCP client (like Claude Desktop, Cline, or Skellington)
can connect to any MCP server.

## How MCP Servers Work

An MCP server is a process that:
1. Exposes a list of **tools** (functions the LLM can call)
2. Optionally exposes **resources** (data the LLM can read)
3. Communicates via **stdio** or **SSE** transport

```
LLM/Agent  ←→  MCP Client  ←→  [stdio]  ←→  MCP Server
```

## Anatomy of a Skellington MCP Server

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("my-server-name")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="my_tool",
            description="What this tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "A parameter"}
                },
                "required": ["param"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "my_tool":
        result = do_something(arguments["param"])
        return [TextContent(type="text", text=result)]
    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## The Six Skellington MCP Servers

| Server | Module | Tools |
|--------|--------|-------|
| **filesystem** | `mcp_servers/filesystem/` | read_file, write_file, list_directory, search_files |
| **websearch** | `mcp_servers/websearch/` | web_search, fetch_url |
| **git_server** | `mcp_servers/git_server/` | git_status, git_log, git_diff |
| **code_exec** | `mcp_servers/code_exec/` | execute_python, run_pytest |
| **database** | `mcp_servers/database/` | db_set, db_get, db_list_keys |
| **docs** | `mcp_servers/docs/` | fetch_docs, search_pypi |

## Connecting an MCP Server to an Agent

```python
# In an agent's __init__ or setup method:
async def setup_tools(self):
    # Start the MCP server as a subprocess
    # Use mcp.client.stdio to connect
    # Register each tool with self.register_tool()
    pass
```

The full MCP client integration is a Phase 3+ implementation goal.
See `docs/learning_guide.md` Phase 3 for step-by-step instructions.

## Tool Schema Best Practices

1. **Be specific** in descriptions — the LLM reads them to decide when to use the tool
2. **Use enums** for parameters with fixed options
3. **Mark required vs optional** accurately
4. **Return errors as text** (not exceptions) so the LLM can handle them gracefully

```python
# Good: specific, enum-constrained
Tool(
    name="read_file",
    description="Read the exact contents of a file. Use for source code, config files, and text.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "encoding": {"type": "string", "enum": ["utf-8", "latin-1"], "default": "utf-8"},
        },
        "required": ["path"],
    },
)
```

## Testing MCP Servers

Test your MCP server tools directly before connecting to agents:

```python
# tests/test_mcp_servers/test_filesystem.py
from skellington.mcp_servers.filesystem.server import call_tool

async def test_read_file(tmp_path):
    (tmp_path / "test.txt").write_text("hello")
    result = await call_tool("read_file", {"path": str(tmp_path / "test.txt")})
    assert "hello" in result[0].text