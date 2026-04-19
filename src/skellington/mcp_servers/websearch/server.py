"""
Web Search MCP Server 🔍

Thin stdio adapter over :mod:`skellington.mcp_servers.websearch.tools`. The
real Brave/Tavily logic lives in ``tools.py`` so SearchSubagent can call it
in-process; this server only exists for orthodox MCP integration.

Tools exposed:
- web_search: Search the web and return structured results
- fetch_url: Fetch and extract text content from a URL
"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.mcp_servers.websearch import tools

app = Server("skellington-websearch")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web and return top results with titles, URLs, and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_url",
            description="Fetch and extract the text content from a URL.",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "web_search":
        try:
            results = await tools.web_search(
                arguments["query"], arguments.get("num_results", 5)
            )
        except tools.SearchAPIError as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]
        except Exception as exc:  # noqa: BLE001 — surface any HTTP failure
            return [TextContent(type="text", text=f"Search error: {exc}")]
        formatted = (
            "\n\n".join(f"**{r['title']}**\n{r['url']}\n{r['snippet']}" for r in results)
            or "No results found"
        )
        return [TextContent(type="text", text=formatted)]

    if name == "fetch_url":
        try:
            text = await tools.fetch_url(arguments["url"])
            return [TextContent(type="text", text=text)]
        except Exception as exc:  # noqa: BLE001
            return [TextContent(type="text", text=f"Error fetching {arguments['url']}: {exc}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
