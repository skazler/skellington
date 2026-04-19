"""
Pure web search tool functions.

These are the actual implementations — plain async functions that return plain
Python values. The MCP server in `server.py` is a thin adapter that wraps these
for the stdio protocol. SearchSubagent calls these directly so we don't pay the
subprocess cost when we don't need the isolation.

Backed by Brave Search (preferred) or Tavily, depending on which API key is set.
"""

from __future__ import annotations

import httpx

from skellington.core.config import get_settings


class SearchAPIError(RuntimeError):
    """No search API is configured, or the upstream call failed."""


async def web_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    """Search the web. Returns ``[{"title", "url", "snippet"}]``.

    Tries Brave first, then Tavily. Raises :class:`SearchAPIError` if neither
    is configured — Oogie/SearchSubagent treats that as "fall back to the LLM".
    """
    settings = get_settings()
    if settings.brave_search_api_key:
        return await _brave_search(query, num_results, settings.brave_search_api_key)
    if settings.tavily_api_key:
        return await _tavily_search(query, num_results, settings.tavily_api_key)
    raise SearchAPIError(
        "No search API key configured. Set BRAVE_SEARCH_API_KEY or TAVILY_API_KEY."
    )


async def fetch_url(url: str) -> str:
    """Fetch the first 10KB of text from ``url`` (no HTML stripping)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        response = await client.get(url, headers={"User-Agent": "Skellington/0.1"})
        return response.text[:10000]


async def _brave_search(query: str, num_results: int, api_key: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": num_results},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        )
        data = response.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in data.get("web", {}).get("results", [])
    ]


async def _tavily_search(query: str, num_results: int, api_key: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": num_results},
        )
        data = response.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": str(r.get("content", ""))[:500],
        }
        for r in data.get("results", [])
    ]
