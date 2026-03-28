"""
Docs MCP Server 📚

Fetches, parses, and chunks documentation for Oogie's research pipeline.

Learning goal: Building a RAG-ready document ingestion pipeline as an MCP server.

Tools exposed:
- fetch_docs: Fetch documentation from a URL and extract clean text
- search_pypi: Look up a package on PyPI
"""

from __future__ import annotations

import re

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("skellington-docs")


def _strip_html(html: str) -> str:
    """Very basic HTML tag stripper. Replace with html2text for production."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_docs",
            description="Fetch documentation from a URL and extract clean readable text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Documentation URL"},
                    "max_chars": {"type": "integer", "default": 8000},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="search_pypi",
            description="Search PyPI for a Python package and return its metadata.",
            inputSchema={
                "type": "object",
                "properties": {"package": {"type": "string"}},
                "required": ["package"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "fetch_docs":
        url = arguments["url"]
        max_chars = arguments.get("max_chars", 8000)
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                response = await client.get(url, headers={"User-Agent": "Skellington/0.1"})
                content_type = response.headers.get("content-type", "")
                if "html" in content_type:
                    text = _strip_html(response.text)
                else:
                    text = response.text
                return [TextContent(type="text", text=text[:max_chars])]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching docs: {e}")]

    if name == "search_pypi":
        package = arguments["package"]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"https://pypi.org/pypi/{package}/json")
                if response.status_code == 404:
                    return [TextContent(type="text", text=f"Package '{package}' not found on PyPI")]
                data = response.json()
                info = data["info"]
                result = (
                    f"**{info['name']}** v{info['version']}\n"
                    f"{info.get('summary', 'No summary')}\n\n"
                    f"Author: {info.get('author', 'Unknown')}\n"
                    f"License: {info.get('license', 'Unknown')}\n"
                    f"Homepage: {info.get('home_page', 'N/A')}\n"
                    f"Requires Python: {info.get('requires_python', 'N/A')}\n"
                )
                return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"PyPI error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
