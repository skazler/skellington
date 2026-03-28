"""
Web Search MCP Server 🔍

Provides web search tools to Oogie and other research agents.

Learning goal: Integrating external APIs into an MCP server.
Supports Brave Search API and Tavily API, falling back gracefully.

Tools exposed:
- web_search: Search the web and return structured results
- fetch_url: Fetch and extract text content from a URL
"""

from __future__ import annotations

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.core.config import get_settings

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
    settings = get_settings()

    if name == "web_search":
        query = arguments["query"]
        num_results = arguments.get("num_results", 5)

        # Try Brave first, then Tavily
        if settings.brave_search_api_key:
            return await _brave_search(query, num_results, settings.brave_search_api_key)
        elif settings.tavily_api_key:
            return await _tavily_search(query, num_results, settings.tavily_api_key)
        else:
            return [
                TextContent(
                    type="text",
                    text="Error: No search API key configured. Set BRAVE_SEARCH_API_KEY or TAVILY_API_KEY.",
                )
            ]

    if name == "fetch_url":
        url = arguments["url"]
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                response = await client.get(url, headers={"User-Agent": "Skellington/0.1"})
                # Basic text extraction — replace with BeautifulSoup for better results
                text = response.text[:10000]
                return [TextContent(type="text", text=text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching {url}: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _brave_search(query: str, num_results: int, api_key: str) -> list[TextContent]:
    """Search using the Brave Search API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": num_results},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
            data = response.json()
            results = data.get("web", {}).get("results", [])
            formatted = "\n\n".join(
                f"**{r.get('title')}**\n{r.get('url')}\n{r.get('description', '')}" for r in results
            )
            return [TextContent(type="text", text=formatted or "No results found")]
    except Exception as e:
        return [TextContent(type="text", text=f"Brave search error: {e}")]


async def _tavily_search(query: str, num_results: int, api_key: str) -> list[TextContent]:
    """Search using the Tavily API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": num_results},
            )
            data = response.json()
            results = data.get("results", [])
            formatted = "\n\n".join(
                f"**{r.get('title')}**\n{r.get('url')}\n{r.get('content', '')[:200]}"
                for r in results
            )
            return [TextContent(type="text", text=formatted or "No results found")]
    except Exception as e:
        return [TextContent(type="text", text=f"Tavily search error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
